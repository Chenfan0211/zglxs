from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder, LaikeWebhookEvent
from app.laike.client import HmacLaikeClient
from app.laike.contracts import SyncResult, WebhookVerification
from app.main import create_app


class FakeLaikeClient:
    def __init__(self, verification: WebhookVerification | None = None) -> None:
        self.verification = verification or WebhookVerification(verified=True)
        self.calls: list[tuple[dict[str, str], bytes]] = []

    async def verify_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        self.calls.append((headers, raw_body))
        return self.verification

    async def fetch_orders(
        self,
        account_id: str,
        cursor: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ):
        raise AssertionError("webhook tests must not fetch orders")


class FakeService:
    def __init__(self, result: SyncResult | None = None) -> None:
        self.result = result or SyncResult(success=True, processed_count=1)
        self.calls: list[tuple[dict[str, str], bytes]] = []

    async def receive_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> SyncResult:
        self.calls.append((headers, raw_body))
        return self.result


def signed_headers(secret: str, body: bytes, event_id: str = "evt-001") -> dict[str, str]:
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {
        "X-Event-ID": event_id,
        "X-Laike-Signature": f"sha256={signature}",
    }


@pytest.mark.asyncio
async def test_hmac_client_uses_sha256_and_rejects_missing_or_wrong_signature():
    secret = "webhook-secret"
    body = b'{"event_id":"evt-hmac"}'
    client = HmacLaikeClient(secret)
    headers = signed_headers(secret, body, event_id="evt-hmac")

    assert (await client.verify_webhook(headers, body)).verified is True
    assert (await client.verify_webhook({}, body)).verified is False
    wrong = await client.verify_webhook(
        {"X-Laike-Signature": "sha256=wrong"},
        body,
    )
    assert wrong.verified is False
    assert (
        await HmacLaikeClient(None).verify_webhook(headers, body)
    ).verified is False


async def request(
    app,
    body: bytes,
    headers: dict[str, str] | None = None,
):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/internal/laike/webhook",
            content=body,
            headers=headers,
        )


def make_app(
    *,
    enabled: bool,
    secret: str | None = "webhook-secret",
    client: FakeLaikeClient | None = None,
    service: FakeService | None = None,
):
    settings = Settings(
        app_env="test",
        database_url=None,
        php_baseline_url=None,
        laike_webhook_enabled=enabled,
        laike_webhook_secret=secret,
    )
    resolved_service = service or FakeService()
    return create_app(
        settings,
        laike_client=client or FakeLaikeClient(),
        laike_service_factory=lambda: resolved_service,
    )


def test_create_app_uses_settings_broker_for_default_laike_enqueuer():
    settings = Settings(
        app_env="test",
        database_url=None,
        php_baseline_url=None,
        redis_url="redis://settings-host:6379/7",
        laike_webhook_enabled=False,
    )

    app = create_app(settings)

    assert app.state.laike_task_app.conf.broker_url == "redis://settings-host:6379/7"
    calls: list[tuple[str, tuple[str, ...]]] = []
    app.state.laike_task_app.send_task = (
        lambda name, args=(): calls.append((name, tuple(args)))
    )

    app.state.laike_enqueuer("evt-settings-broker", {"ignored": True})

    assert calls == [("process_laike_webhook", ("evt-settings-broker",))]


def test_create_app_uses_injected_task_app_for_default_laike_enqueuer():
    task_app = Celery(
        "injected-laike",
        broker="redis://injected-host:6379/8",
        backend="redis://injected-host:6379/8",
        set_as_current=False,
    )
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url=None,
            redis_url="redis://settings-host:6379/7",
            laike_webhook_enabled=False,
        ),
        laike_task_app=task_app,
    )
    calls: list[tuple[str, tuple[str, ...]]] = []
    task_app.send_task = (
        lambda name, args=(): calls.append((name, tuple(args)))
    )

    app.state.laike_enqueuer("evt-injected-broker", {"ignored": True})

    assert app.state.laike_task_app is task_app
    assert app.state.laike_task_app.conf.broker_url == "redis://injected-host:6379/8"
    assert calls == [("process_laike_webhook", ("evt-injected-broker",))]


@pytest.mark.asyncio
async def test_create_app_default_service_processes_orders_with_default_normalizer(
    tmp_path,
):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'laike-default-normalizer.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app(
        Settings(
            app_env="test",
            database_url=database_url,
            php_baseline_url=None,
            laike_sync_mode="shadow",
        ),
        laike_session_factory=session_factory,
    )

    result = await app.state.laike_service_factory().process_webhook(
        "evt-default-normalizer",
        {
            "event_id": "evt-default-normalizer",
            "order_id": "order-default-normalizer",
            "status": "paid",
            "created_at": "2026-09-12T08:00:00Z",
        },
    )

    assert result.success is True
    with session_factory() as session:
        assert session.scalar(
            select(LaikeOrder.provider_order_id).where(
                LaikeOrder.provider_order_id == "order-default-normalizer"
            )
        ) == "order-default-normalizer"
    engine.dispose()


@pytest.mark.asyncio
async def test_webhook_is_disabled_by_default_and_returns_failure_envelope():
    app = make_app(enabled=False)

    response = await request(
        app,
        b'{"event_id":"evt-disabled"}',
        headers={"X-Laike-Signature": "ignored"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": 0,
        "msg": "laike webhook is disabled",
        "data": None,
    }


@pytest.mark.asyncio
async def test_webhook_service_owns_missing_secret_verification():
    service = FakeService()
    app = make_app(enabled=True, secret=None, service=service)

    response = await request(
        app,
        b'{"event_id":"evt-no-secret"}',
        headers={"X-Laike-Signature": "anything"},
    )

    assert response.status_code == 200
    assert response.json()["code"] == 1
    assert len(service.calls) == 1
    assert service.calls[0][0]["x-laike-signature"] == "anything"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({}, "missing webhook signature"),
        ({"X-Laike-Signature": "sha256=wrong"}, "invalid webhook signature"),
    ],
)
async def test_webhook_rejects_missing_or_invalid_signature(headers, message):
    client = HmacLaikeClient("webhook-secret")

    class VerifyingService(FakeService):
        async def receive_webhook(self, headers, raw_body):
            verification = await client.verify_webhook(headers, raw_body)
            if not verification.verified:
                return SyncResult(success=False, failed_count=1, reason=verification.reason)
            return self.result

    service = VerifyingService()
    app = make_app(
        enabled=True,
        service=service,
        client=client,
    )
    body = b'{"event_id":"evt-invalid-signature"}'

    response = await request(app, body, headers=headers)

    assert response.status_code == 400
    assert response.json() == {"code": 0, "msg": message, "data": None}
    assert len(service.calls) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"", b"not-json", b"[]", b"null"])
async def test_webhook_rejects_empty_or_invalid_json_without_calling_service(body):
    secret = "webhook-secret"
    service = FakeService()
    app = make_app(enabled=True, service=service)

    response = await request(
        app,
        body,
        headers=signed_headers(secret, body, event_id="evt-invalid-json"),
    )

    assert response.status_code == 400
    assert response.json()["code"] == 0
    assert response.json()["data"] is None
    assert service.calls == []


@pytest.mark.asyncio
async def test_webhook_valid_request_calls_service_and_returns_legacy_envelope():
    secret = "webhook-secret"
    body = json.dumps({"event_id": "evt-valid", "order_id": "order-001"}).encode()
    service = FakeService(SyncResult(success=True, processed_count=1))
    app = make_app(enabled=True, service=service)

    response = await request(
        app,
        body,
        headers=signed_headers(secret, body, event_id="evt-valid"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": 1,
        "msg": "success",
        "data": {
            "success": True,
            "processed_count": 1,
            "failed_count": 0,
        },
    }
    assert service.calls[0][1] == body
    assert service.calls[0][0]["x-event-id"] == "evt-valid"
    assert service.calls[0][0]["x-laike-signature"] == signed_headers(
        secret,
        body,
        event_id="evt-valid",
    )["X-Laike-Signature"]


@pytest.mark.asyncio
async def test_webhook_route_delegates_verification_once_and_uses_service_reason():
    class CountingClient(FakeLaikeClient):
        async def verify_webhook(self, headers, raw_body):
            self.calls.append((headers, raw_body))
            return WebhookVerification(verified=True)

    client = CountingClient()
    class CountingService(FakeService):
        async def receive_webhook(self, headers, raw_body):
            self.calls.append((headers, raw_body))
            await client.verify_webhook(headers, raw_body)
            return self.result

    service = CountingService(SyncResult(success=False, reason="invalid webhook signature"))
    app = make_app(enabled=True, client=client, service=service)
    body = b'{"event_id":"evt-route-reason"}'

    response = await request(app, body, headers={"X-Laike-Signature": "ignored"})

    assert response.status_code == 400
    assert response.json()["msg"] == "invalid webhook signature"
    assert len(client.calls) == 1
    assert len(service.calls) == 1


@pytest.mark.asyncio
async def test_webhook_persists_before_enqueue_and_does_not_process_inline(
    tmp_path,
):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'laike-webhook.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    enqueued: list[tuple[str, dict]] = []

    async def enqueue(event_id: str, payload: dict):
        with session_factory() as session:
            event = session.scalar(
                select(LaikeWebhookEvent).where(
                    LaikeWebhookEvent.event_id == event_id
                )
            )
            assert event is not None
            assert event.status == "processing"
        enqueued.append((event_id, payload))

    body = b'{"event_id":"evt-persist-first","order_id":"order-001"}'
    secret = "webhook-secret"
    client = FakeLaikeClient()
    settings = Settings(
        app_env="test",
        database_url=database_url,
        php_baseline_url=None,
        laike_webhook_enabled=True,
        laike_webhook_secret=secret,
    )
    app = create_app(
        settings,
        laike_client=client,
        laike_session_factory=session_factory,
        laike_enqueuer=enqueue,
    )

    response = await request(
        app,
        body,
        headers=signed_headers(secret, body, event_id="evt-persist-first"),
    )

    assert response.status_code == 200
    assert enqueued == [
        (
            "evt-persist-first",
            {"event_id": "evt-persist-first", "order_id": "order-001"},
        )
    ]
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-persist-first"
            )
        )
        assert event is not None
        assert event.status == "queued"


@pytest.mark.asyncio
async def test_invalid_hmac_does_not_persist_an_event(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'laike-invalid.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    secret = "webhook-secret"
    body = b'{"event_id":"evt-invalid-hmac","order_id":"order-001"}'
    app = create_app(
        Settings(
            app_env="test",
            database_url=database_url,
            php_baseline_url=None,
            laike_webhook_enabled=True,
            laike_webhook_secret=secret,
        ),
        laike_client=HmacLaikeClient(secret),
        laike_session_factory=session_factory,
    )

    response = await request(
        app,
        body,
        headers={
            "X-Event-ID": "evt-invalid-hmac",
            "X-Laike-Signature": "sha256=wrong",
        },
    )

    assert response.status_code == 400
    with session_factory() as session:
        assert session.scalars(select(LaikeWebhookEvent)).all() == []
