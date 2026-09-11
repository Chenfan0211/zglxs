from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models.base import Base
from app.db.models.laike import (
    LaikeOrder,
    LaikeSyncCursor,
    LaikeSyncRun,
    LaikeWebhookEvent,
)
from app.laike.repositories import LaikeRepository
from app.laike.contracts import LaikePage, WebhookVerification
from app.laike.service import LaikeSyncService


class FakeLaikeClient:
    def __init__(
        self,
        pages: list[LaikePage | Exception] | None = None,
        fetch_error: Exception | None = None,
    ) -> None:
        self.pages = pages or []
        self.fetch_error = fetch_error
        self.webhook_calls: list[tuple[dict[str, str], bytes]] = []
        self.fetch_calls: list[tuple[str, str | None]] = []

    async def verify_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        self.webhook_calls.append((headers, raw_body))
        return WebhookVerification(verified=True)

    async def fetch_orders(
        self,
        account_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
        cursor: str | None = None,
    ) -> LaikePage:
        self.fetch_calls.append((account_id, cursor))
        if self.fetch_error:
            raise self.fetch_error
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client():
    return FakeLaikeClient()


@pytest.fixture
def service(session_factory, client):
    return LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=object(),
    )


@pytest.mark.asyncio
async def test_receive_webhook_persists_event_payload(session_factory, service):
    raw_body = json.dumps({"event_id": "evt-001", "order_id": "order-001"}).encode()

    result = await service.receive_webhook(
        {"X-Event-ID": "evt-001", "X-Signature": "signature"},
        raw_body,
    )

    assert result.success is True
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-001"
            )
        )
        assert event is not None
        assert event.payload_json == {
            "event_id": "evt-001",
            "order_id": "order-001",
        }


@pytest.mark.asyncio
async def test_receive_webhook_duplicate_event_is_idempotent(
    session_factory,
    service,
    client,
):
    raw_body = b'{"event_id":"evt-001","order_id":"order-001"}'

    first = await service.receive_webhook({"X-Event-ID": "evt-001"}, raw_body)
    second = await service.receive_webhook({"X-Event-ID": "evt-001"}, raw_body)

    assert first.success is True
    assert second.success is True
    assert second.processed_count == 0
    with session_factory() as session:
        assert session.scalars(select(LaikeWebhookEvent)).all().__len__() == 1


@pytest.mark.asyncio
async def test_receive_webhook_retries_received_event_after_enqueue_failure(
    session_factory,
    client,
):
    attempts = 0

    async def enqueue(event_id, payload):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("queue unavailable")

    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=object(),
        enqueuer=enqueue,
    )
    raw_body = b'{"event_id":"evt-retry","order_id":"order-001"}'

    first = await service.receive_webhook({"X-Event-ID": "evt-retry"}, raw_body)
    second = await service.receive_webhook({"X-Event-ID": "evt-retry"}, raw_body)

    assert first.success is False
    assert first.failed_count == 1
    assert second.success is True
    assert second.processed_count == 1
    assert attempts == 2
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-retry"
            )
        )
        assert event.status == "queued"
        assert event.processed_at is not None


@pytest.mark.asyncio
async def test_reconcile_upserts_duplicate_provider_order(
    session_factory,
    client,
    service,
):
    client.pages = [
        LaikePage(
            items=[
                {
                    "order_id": "order-001",
                    "status": "paid",
                    "created_at": "2026-09-11T12:00:00+08:00",
                }
            ],
            has_more=False,
        ),
        LaikePage(
            items=[
                {
                    "order_id": "order-001",
                    "status": "completed",
                    "created_at": "2026-09-11T12:00:00+08:00",
                }
            ],
            has_more=False,
        ),
    ]

    await service.reconcile_account("account-001")
    result = await service.reconcile_account("account-001")

    assert result.success is True
    with session_factory() as session:
        orders = session.scalars(select(LaikeOrder)).all()
        assert len(orders) == 1
        assert orders[0].provider_order_id == "order-001"
        assert orders[0].status == "completed"


@pytest.mark.asyncio
async def test_reconcile_isolates_one_failed_order_from_other_items(
    session_factory,
    client,
    service,
):
    client.pages = [
        LaikePage(
            items=[
                {"order_id": "order-good", "status": "paid"},
                {"status": "paid"},
            ],
            has_more=False,
            next_cursor="cursor-should-not-advance",
        )
    ]

    result = await service.reconcile_account("account-001")

    assert result.success is False
    assert result.processed_count == 1
    assert result.failed_count == 1
    with session_factory() as session:
        assert session.scalar(
            select(LaikeOrder.provider_order_id).where(
                LaikeOrder.provider_order_id == "order-good"
            )
        ) == "order-good"
        assert session.scalar(
            select(LaikeSyncCursor.cursor).where(
                LaikeSyncCursor.account_id == "account-001"
            )
        ) is None
        run = session.scalar(select(LaikeSyncRun))
        assert "exception_type=ValueError" in run.error_message
        assert "paid" not in run.error_message


@pytest.mark.asyncio
async def test_reconcile_does_not_advance_cursor_when_fetch_fails(
    session_factory,
    client,
    service,
):
    client.fetch_error = RuntimeError("temporary provider failure")

    result = await service.reconcile_account("account-001")

    assert result.success is False
    assert result.processed_count == 0
    assert result.failed_count == 0
    with session_factory() as session:
        assert session.scalar(
            select(LaikeSyncCursor.cursor).where(
                LaikeSyncCursor.account_id == "account-001"
            )
        ) is None


@pytest.mark.asyncio
async def test_reconcile_does_not_advance_old_cursor_when_second_page_fetch_fails(
    session_factory,
    client,
    service,
):
    with session_factory() as session:
        session.add(LaikeSyncCursor(account_id="account-001", cursor="old-cursor"))
        session.commit()
    client.pages = [
        LaikePage(
            items=[{"order_id": "order-001", "status": "paid"}],
            next_cursor="page-2",
            has_more=True,
        ),
        RuntimeError("second page unavailable"),
    ]

    result = await service.reconcile_account("account-001")

    assert result.success is False
    assert result.processed_count == 1
    with session_factory() as session:
        assert session.scalar(
            select(LaikeSyncCursor.cursor).where(
                LaikeSyncCursor.account_id == "account-001"
            )
        ) == "old-cursor"


@pytest.mark.parametrize(
    ("page", "initial_cursor"),
    [
        (LaikePage(items=[], has_more=True, next_cursor=None), None),
        (LaikePage(items=[], has_more=True, next_cursor="same-cursor"), "same-cursor"),
    ],
)
@pytest.mark.asyncio
async def test_reconcile_rejects_missing_or_repeated_next_cursor(
    session_factory,
    client,
    service,
    page,
    initial_cursor,
):
    if initial_cursor is not None:
        with session_factory() as session:
            session.add(
                LaikeSyncCursor(
                    account_id="account-001",
                    cursor=initial_cursor,
                )
            )
            session.commit()
    client.pages = [page]

    result = await service.reconcile_account("account-001")

    assert result.success is False
    assert result.failed_count == 0
    with session_factory() as session:
        run = session.scalar(select(LaikeSyncRun))
        assert run.error_message is not None
        assert "cursor" in run.error_message.lower()


def test_repository_duplicate_event_insert_returns_existing_event(session_factory):
    with session_factory() as session:
        repository = LaikeRepository(session)
        first = repository.insert_webhook_event(
            "evt-concurrent",
            {"event_id": "evt-concurrent"},
            {},
            True,
        )
        session.commit()

    with session_factory() as session:
        repository = LaikeRepository(session)
        second = repository.insert_webhook_event(
            "evt-concurrent",
            {"event_id": "evt-concurrent", "new": True},
            {},
            True,
        )
        session.commit()

    assert second.id == first.id
    assert second.payload_json == {"event_id": "evt-concurrent"}


@pytest.mark.asyncio
async def test_reconcile_advances_cursor_after_successful_page(
    session_factory,
    client,
    service,
):
    client.pages = [
        LaikePage(
            items=[{"order_id": "order-001", "status": "paid"}],
            next_cursor="cursor-001",
            has_more=False,
        )
    ]

    result = await service.reconcile_account("account-001")

    assert result.success is True
    assert result.processed_count == 1
    with session_factory() as session:
        assert session.scalar(
            select(LaikeSyncCursor.cursor).where(
                LaikeSyncCursor.account_id == "account-001"
            )
        ) == "cursor-001"
