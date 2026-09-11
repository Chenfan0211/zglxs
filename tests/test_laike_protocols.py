from __future__ import annotations

import hashlib
import hmac
import inspect

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder, LaikeWebhookEvent
from app.laike.client import (
    HmacLaikeClient,
    HttpLaikeClient,
    LaikeClientError,
    LaikeConfigurationError,
)
from app.laike.contracts import (
    LaikeClient,
    LaikePage,
    WebhookVerification,
)
from app.laike.normalizer import (
    NormalizationError,
    OrderFieldMapping,
    OrderNormalizer,
    normalize_order,
)
from app.laike.service import LaikeSyncService
from app.laike.webhook import WebhookVerifier
from app.main import create_app


class ProtocolClient:
    async def fetch_orders(
        self,
        account_id: str,
        cursor: str | None,
        start_time: str | None,
        end_time: str | None,
    ) -> LaikePage:
        return LaikePage(items=[], next_cursor=None, raw={})

    async def verify_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        return WebhookVerification(valid=True, event_id=None, source="laike")


def test_contracts_expose_new_fields_and_legacy_aliases():
    page = LaikePage(
        items=[{"provider_field": "keep"}],
        next_cursor="cursor-001",
        raw={"items": [{"provider_field": "keep"}], "unknown": True},
    )
    verification = WebhookVerification(
        valid=True,
        event_id="evt-001",
        source="laike",
    )

    assert page.raw["unknown"] is True
    assert page.has_more is True
    assert verification.valid is True
    assert verification.verified is True

    legacy_page = LaikePage(items=[], has_more=False)
    legacy_verification = WebhookVerification(verified=True)
    assert legacy_page.has_more is False
    assert legacy_verification.valid is True


def test_laike_client_protocol_is_runtime_checkable():
    assert isinstance(ProtocolClient(), LaikeClient)


@pytest.mark.parametrize(
    ("base_url", "orders_path", "access_token"),
    [
        ("", "/orders", "token"),
        ("https://laike.test", "", "token"),
        ("https://laike.test", "/orders", ""),
        ("https://laike.test", "/orders", None),
    ],
)
def test_http_client_rejects_missing_configuration(
    base_url,
    orders_path,
    access_token,
):
    with pytest.raises(LaikeConfigurationError):
        HttpLaikeClient(base_url, orders_path, access_token)


@pytest.mark.asyncio
async def test_http_client_fetches_configured_path_and_preserves_raw_response():
    seen: list[httpx.Request] = []
    response_body = {
        "records": [{"order": {"id": "order-001"}, "unknown": "keep"}],
        "page_token": "cursor-002",
        "provider_extra": {"nested": True},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpLaikeClient(
            "https://laike.test/",
            "/v1/orders",
            "access-token",
            http_client=http_client,
            items_key="records",
            cursor_key="page_token",
        )
        page = await client.fetch_orders(
            "account-001",
            "cursor-001",
            "2026-09-11T00:00:00Z",
            "2026-09-12T00:00:00Z",
        )

    assert len(seen) == 1
    assert str(seen[0].url) == (
        "https://laike.test/v1/orders?"
        "account_id=account-001&cursor=cursor-001&"
        "start_time=2026-09-11T00%3A00%3A00Z&"
        "end_time=2026-09-12T00%3A00%3A00Z"
    )
    assert seen[0].headers["Authorization"] == "Bearer access-token"
    assert page.items == response_body["records"]
    assert page.next_cursor == "cursor-002"
    assert page.raw == response_body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(503), "laike request failed with status 503"),
        (httpx.Response(200, content=b"not-json"), "laike response is not valid JSON"),
        (
            httpx.Response(200, json=["not", "an", "object"]),
            "laike response JSON must be an object",
        ),
    ],
)
async def test_http_client_reports_stable_response_errors(response, message):
    transport = httpx.MockTransport(lambda request: response)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpLaikeClient(
            "https://laike.test",
            "/orders",
            "access-token",
            http_client=http_client,
        )

        with pytest.raises(LaikeClientError, match=message):
            await client.fetch_orders("account-001", None, None, None)


@pytest.mark.asyncio
async def test_http_client_returns_invalid_when_verifier_is_not_configured():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500)
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpLaikeClient(
            "https://laike.test",
            "/orders",
            "access-token",
            http_client=http_client,
        )

        result = await client.verify_webhook({}, b"{}")

    assert result.valid is False
    assert result.reason == "webhook verifier is not configured"


@pytest.mark.asyncio
async def test_http_client_delegates_webhook_verification():
    body = b'{"event":"created"}'
    secret = "webhook-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verifier = WebhookVerifier(secret)
    transport = httpx.MockTransport(lambda request: httpx.Response(500))

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpLaikeClient(
            "https://laike.test",
            "/orders",
            "access-token",
            http_client=http_client,
            webhook_verifier=verifier,
        )
        result = await client.verify_webhook(
            {
                "X-Laike-Signature": f"sha256={signature}",
                "X-Laike-Event-Id": "evt-001",
            },
            body,
        )

    assert result.valid is True
    assert result.event_id == "evt-001"
    assert result.source == "laike"


def test_webhook_verifier_uses_exact_raw_body_and_event_header():
    secret = "webhook-secret"
    body = b'{"amount":1}\n'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verifier = WebhookVerifier(secret)

    result = verifier.verify(
        {
            "x-laike-signature": f"sha256={signature}",
            "x-laike-event-id": "evt-raw",
        },
        body,
    )

    assert result.valid is True
    assert result.event_id == "evt-raw"
    assert result.source == "laike"


@pytest.mark.parametrize(
    ("secret", "headers", "reason"),
    [
        (None, {"X-Laike-Signature": "sha256=ignored"}, "webhook secret is not configured"),
        ("secret", {}, "missing webhook signature"),
        ("secret", {"X-Laike-Signature": "sha256=wrong"}, "invalid webhook signature"),
    ],
)
def test_webhook_verifier_rejects_missing_or_invalid_signatures(
    secret,
    headers,
    reason,
):
    result = WebhookVerifier(secret).verify(headers, b"{}")

    assert result.valid is False
    assert result.reason == reason


def test_webhook_verifier_rejects_unsupported_digest():
    with pytest.raises(ValueError, match="unsupported digest"):
        WebhookVerifier("secret", digest="not-a-digest")


def test_order_normalizer_extracts_only_explicit_paths_and_normalizes_times():
    mapping = OrderFieldMapping(
        order_id="order.id",
        subject_id="buyer.id",
        product_id="line.product.id",
        status="state",
        created_at="timestamps.created",
        updated_at="timestamps.updated",
    )
    payload = {
        "order": {"id": "order-001", "ignored": "do-not-extract"},
        "buyer": {"id": "subject-001"},
        "line": {"product": {"id": "product-001"}},
        "state": "paid",
        "timestamps": {
            "created": "2026-09-11T12:00:00+08:00",
            "updated": "2026-09-11T05:00:00Z",
        },
        "unknown": {"keep": True},
    }

    order = OrderNormalizer(mapping).normalize(payload)

    assert order.order_id == "order-001"
    assert order.subject_id == "subject-001"
    assert order.product_id == "product-001"
    assert order.status == "paid"
    assert order.original_created_at == "2026-09-11T12:00:00+08:00"
    assert order.normalized_created_at == "2026-09-11T04:00:00Z"
    assert order.original_updated_at == "2026-09-11T05:00:00Z"
    assert order.normalized_updated_at == "2026-09-11T05:00:00Z"
    assert order.raw_payload == payload
    assert not hasattr(order, "ignored")


@pytest.mark.parametrize(
    "payload",
    [
        {"order": {"id": " "}, "buyer": {"id": "subject"}, "line": {"product": {"id": "product"}}},
        {"order": {}, "buyer": {"id": "subject"}, "line": {"product": {"id": "product"}}},
        {"order": {"id": "order"}, "buyer": {}, "line": {"product": {"id": "product"}}},
        {"order": {"id": "order"}, "buyer": {"id": "subject"}, "line": {"product": {}}},
    ],
)
def test_order_normalizer_requires_non_blank_stable_ids(payload):
    mapping = OrderFieldMapping(
        order_id="order.id",
        subject_id="buyer.id",
        product_id="line.product.id",
    )

    with pytest.raises(NormalizationError):
        OrderNormalizer(mapping).normalize(payload)


def test_order_normalizer_does_not_guess_unparseable_or_unconfigured_times():
    mapping = OrderFieldMapping(
        order_id="order.id",
        subject_id="buyer.id",
        product_id="product.id",
        created_at="created",
        updated_at=None,
    )
    payload = {
        "order": {"id": "order-001"},
        "buyer": {"id": "subject-001"},
        "product": {"id": "product-001"},
        "created": "not-an-iso-time",
        "updated": "2026-09-11T00:00:00Z",
    }

    order = OrderNormalizer(mapping).normalize(payload)

    assert order.original_created_at == "not-an-iso-time"
    assert order.normalized_created_at is None
    assert order.original_updated_at is None
    assert order.normalized_updated_at is None


def test_legacy_normalize_order_payload_call_remains_supported():
    payload = {
        "order_id": "legacy-order-001",
        "status": "paid",
        "created_at": "2026-09-11T12:00:00+08:00",
        "unknown_business_field": {"keep": True},
    }

    order = normalize_order(payload)

    assert order.order_id == "legacy-order-001"
    assert order.created_at == payload["created_at"]
    assert order.payload_json == payload


def test_legacy_normalize_order_model_dump_keeps_legacy_shape():
    payload = {
        "order_id": "legacy-order-002",
        "status": "paid",
        "created_at": "2026-09-11T12:00:00+08:00",
        "unknown_business_field": {"keep": True},
    }

    dumped = normalize_order(payload).model_dump()

    assert dumped == {
        "order_id": "legacy-order-002",
        "status": "paid",
        "created_at": "2026-09-11T12:00:00+08:00",
        "payload_json": payload,
    }


def test_explicit_order_normalizer_model_dump_keeps_new_shape():
    mapping = OrderFieldMapping(
        order_id="order.id",
        subject_id="buyer.id",
        product_id="product.id",
    )
    payload = {
        "order": {"id": "order-002"},
        "buyer": {"id": "subject-002"},
        "product": {"id": "product-002"},
    }

    dumped = OrderNormalizer(mapping).normalize(payload).model_dump()

    assert dumped["order_id"] == "order-002"
    assert dumped["subject_id"] == "subject-002"
    assert dumped["product_id"] == "product-002"
    assert dumped["raw_payload"] == payload
    assert "payload_json" not in dumped
    assert "created_at" not in dumped


@pytest.mark.asyncio
async def test_default_hmac_client_result_is_safe_to_await():
    secret = "webhook-secret"
    body = b'{"event":"created"}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    client = HmacLaikeClient(secret)

    result = client.verify_webhook(
        {"X-Laike-Signature": f"sha256={signature}"},
        body,
    )

    assert result.verified is True
    assert (await result).valid is True


@pytest.mark.asyncio
async def test_default_hmac_client_order_method_is_awaitable():
    client = HmacLaikeClient("webhook-secret")

    pending = client.fetch_orders("account-001", None, None, None)

    assert inspect.isawaitable(pending)
    with pytest.raises(RuntimeError, match="order client is not configured"):
        await pending


def test_main_default_hmac_client_uses_only_configured_signature_header():
    settings = Settings(
        _env_file=None,
        database_url=None,
        laike_webhook_secret="webhook-secret",
        laike_webhook_signature_header="X-Custom-Signature",
        laike_webhook_event_id_header="X-Custom-Event-Id",
    )
    app = create_app(settings)
    body = b'{"event":"created"}'
    signature = hmac.new(
        b"webhook-secret",
        body,
        hashlib.sha256,
    ).hexdigest()

    configured = app.state.laike_client.verify_webhook(
        {
            "X-Custom-Signature": f"sha256={signature}",
            "X-Custom-Event-Id": "evt-custom",
        },
        body,
    )
    generic = app.state.laike_client.verify_webhook(
        {"Signature": f"sha256={signature}"},
        body,
    )

    assert configured.valid is True
    assert configured.event_id == "evt-custom"
    assert generic.valid is False


def test_main_can_construct_service_with_explicit_order_mapping():
    mapping = OrderFieldMapping(
        order_id="order.id",
        subject_id="buyer.id",
        product_id="product.id",
    )
    normalizer = OrderNormalizer(mapping)

    app = create_app(
        Settings(_env_file=None, database_url=None),
        laike_normalizer=normalizer,
    )

    assert app.state.laike_service_factory().normalizer is normalizer


class _ReconcileClient:
    def __init__(
        self,
        page: LaikePage,
        verification: WebhookVerification | None = None,
    ) -> None:
        self.page = page
        self.verification = verification or WebhookVerification(
            valid=True,
            event_id=None,
            source="laike",
        )

    async def fetch_orders(
        self,
        account_id: str,
        cursor: str | None,
        start_time: str | None,
        end_time: str | None,
    ) -> LaikePage:
        return self.page

    async def verify_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        return self.verification


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'laike.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_service_uses_injected_explicit_normalizer(tmp_path):
    session_factory = _session_factory(tmp_path)
    mapping = OrderFieldMapping(
        order_id="order.id",
        subject_id="buyer.id",
        product_id="product.id",
    )
    normalizer = OrderNormalizer(mapping)
    payload = {
        "order": {"id": "mapped-order-001"},
        "buyer": {"id": "mapped-subject-001"},
        "product": {"id": "mapped-product-001"},
    }
    client = _ReconcileClient(LaikePage(items=[payload], has_more=False))
    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(_env_file=None),
        normalizer=normalizer,
    )

    result = await service.reconcile_account("account-001")

    assert result.success is True
    assert result.processed_count == 1
    with session_factory() as session:
        order = session.scalar(select(LaikeOrder))
        assert order is not None
        assert order.provider_order_id == "mapped-order-001"
        assert order.payload_json == payload


@pytest.mark.asyncio
async def test_service_with_unconfigured_normalizer_does_not_guess_order_id(tmp_path):
    session_factory = _session_factory(tmp_path)
    payload = {
        "order": {"id": "not-confirmed-order-id"},
        "buyer": {"id": "subject-001"},
        "product": {"id": "product-001"},
    }
    client = _ReconcileClient(LaikePage(items=[payload], has_more=False))
    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(_env_file=None),
        normalizer=None,
    )

    result = await service.reconcile_account("account-001")

    assert result.success is False
    assert result.processed_count == 0
    assert result.failed_count == 1
    with session_factory() as session:
        assert session.scalars(select(LaikeOrder)).all() == []


@pytest.mark.asyncio
async def test_service_prefers_verification_event_id_over_other_event_sources(tmp_path):
    session_factory = _session_factory(tmp_path)
    body = b'{"event_id":"payload-event","order_id":"order-001"}'
    client = _ReconcileClient(
        LaikePage(items=[], has_more=False),
        verification=WebhookVerification(
            valid=True,
            event_id="configured-event",
            source="laike",
        ),
    )
    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(_env_file=None),
        enqueuer=lambda event_id, payload: None,
    )

    result = await service.receive_webhook(
        {
            "X-Custom-Event-Id": "configured-event",
            "X-Event-ID": "wrong-header-event",
        },
        body,
    )

    assert result.success is True
    with session_factory() as session:
        event_ids = session.scalars(select(LaikeWebhookEvent.event_id)).all()
        assert event_ids == ["configured-event"]


@pytest.mark.asyncio
async def test_legacy_verification_keeps_legacy_event_id_compatibility(tmp_path):
    session_factory = _session_factory(tmp_path)
    body = b'{"event_id":"payload-event","order_id":"order-001"}'
    client = _ReconcileClient(
        LaikePage(items=[], has_more=False),
        verification=WebhookVerification(verified=True),
    )
    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(_env_file=None),
        enqueuer=lambda event_id, payload: None,
    )

    result = await service.receive_webhook(
        {"X-Event-ID": "legacy-header-event"},
        body,
    )

    assert result.success is True
    with session_factory() as session:
        event_ids = session.scalars(select(LaikeWebhookEvent.event_id)).all()
        assert event_ids == ["legacy-header-event"]
