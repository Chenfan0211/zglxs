from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest

from app.laike.client import (
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
from app.laike.webhook import WebhookVerifier


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
