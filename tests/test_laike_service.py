from __future__ import annotations

import json
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
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
def default_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def client():
    return FakeLaikeClient()


@pytest.fixture
def service(session_factory, client):
    return LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(),
        enqueuer=lambda event_id, payload: None,
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
async def test_receive_webhook_without_enqueuer_keeps_event_received_for_retry(
    session_factory,
    client,
):
    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(),
    )
    raw_body = b'{"event_id":"evt-no-queue","order_id":"order-001"}'

    first = await service.receive_webhook(
        {"X-Event-ID": "evt-no-queue"},
        raw_body,
    )

    assert first.success is False
    assert first.processed_count == 0
    assert first.failed_count == 1
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-no-queue"
            )
        )
        assert event.status == "received"
        assert event.processed_at is None
        assert event.claim_token is None

    enqueued: list[tuple[str, dict]] = []

    async def enqueue(event_id, payload):
        enqueued.append((event_id, payload))

    service.enqueuer = enqueue
    second = await service.receive_webhook(
        {"X-Event-ID": "evt-no-queue"},
        raw_body,
    )

    assert second.success is True
    assert second.processed_count == 1
    assert second.failed_count == 0
    assert enqueued == [
        ("evt-no-queue", {"event_id": "evt-no-queue", "order_id": "order-001"})
    ]
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-no-queue"
            )
        ) == "queued"


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
        settings=Settings(),
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
async def test_concurrent_webhooks_only_the_claiming_service_enqueues(
    session_factory,
    client,
):
    enqueue_started = asyncio.Event()
    release_enqueue = asyncio.Event()
    calls: list[str] = []

    async def first_enqueue(event_id, payload):
        calls.append(f"first:{event_id}")
        enqueue_started.set()
        await release_enqueue.wait()

    async def second_enqueue(event_id, payload):
        calls.append(f"second:{event_id}")

    first_service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(),
        enqueuer=first_enqueue,
    )
    second_service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(),
        enqueuer=second_enqueue,
    )
    raw_body = b'{"event_id":"evt-claim","order_id":"order-001"}'

    first_task = asyncio.create_task(
        first_service.receive_webhook({"X-Event-ID": "evt-claim"}, raw_body)
    )
    await enqueue_started.wait()
    second_result = await second_service.receive_webhook(
        {"X-Event-ID": "evt-claim"},
        raw_body,
    )
    release_enqueue.set()
    first_result = await first_task

    assert first_result.success is True
    assert second_result.success is True
    assert second_result.processed_count == 0
    assert calls == ["first:evt-claim"]


@pytest.mark.asyncio
async def test_receive_webhook_copies_enqueue_values_before_default_commit_expiry(
    default_session_factory,
    client,
):
    enqueued: list[tuple[str, dict]] = []

    async def enqueue(event_id, payload):
        enqueued.append((event_id, payload))

    service = LaikeSyncService(
        session_factory=default_session_factory,
        client=client,
        settings=Settings(),
        enqueuer=enqueue,
    )

    result = await service.receive_webhook(
        {"X-Event-ID": "evt-expire"},
        b'{"event_id":"evt-expire","order_id":"order-001"}',
    )

    assert result.success is True
    assert enqueued == [
        ("evt-expire", {"event_id": "evt-expire", "order_id": "order-001"})
    ]


@pytest.mark.asyncio
async def test_receive_webhook_releases_claim_when_enqueue_is_cancelled(
    session_factory,
    client,
):
    async def enqueue(event_id, payload):
        raise asyncio.CancelledError()

    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(),
        enqueuer=enqueue,
    )

    with pytest.raises(asyncio.CancelledError):
        await service.receive_webhook(
            {"X-Event-ID": "evt-cancel"},
            b'{"event_id":"evt-cancel","order_id":"order-001"}',
        )

    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-cancel"
            )
        ) == "received"


@pytest.mark.asyncio
async def test_receive_webhook_reclaims_stale_processing_event(
    session_factory,
    client,
):
    calls: list[str] = []
    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=Settings(),
        enqueuer=lambda event_id, payload: calls.append(event_id),
    )
    with session_factory() as session:
        session.add(
            LaikeWebhookEvent(
                event_id="evt-stale",
                payload_json={"event_id": "evt-stale", "order_id": "order-001"},
                headers_json={},
                verified=True,
                status="processing",
                processed_at=None,
            )
        )
        session.commit()

    result = await service.receive_webhook(
        {"X-Event-ID": "evt-stale"},
        b'{"event_id":"evt-stale","order_id":"order-001"}',
    )

    assert result.success is True
    assert calls == ["evt-stale"]
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-stale"
            )
        ) == "queued"


def test_stale_webhook_claim_cannot_finish_new_claim(
    session_factory,
):
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        repository = LaikeRepository(session)
        repository.insert_webhook_event(
            "evt-fenced",
            {"event_id": "evt-fenced"},
            {},
            True,
        )
        session.commit()

    with session_factory() as old_session:
        old_repository = LaikeRepository(old_session)
        old_token = old_repository.claim_webhook_event(
            "evt-fenced",
            claimed_at=now - timedelta(minutes=10),
            stale_before=now - timedelta(minutes=5),
        )
        old_session.commit()

    with session_factory() as new_session:
        new_repository = LaikeRepository(new_session)
        new_token = new_repository.claim_webhook_event(
            "evt-fenced",
            claimed_at=now,
            stale_before=now - timedelta(minutes=5),
        )
        new_session.commit()

    assert old_token is not None
    assert new_token is not None
    assert old_token != new_token
    with session_factory() as old_session:
        old_repository = LaikeRepository(old_session)
        assert old_repository.release_webhook_claim(
            "evt-fenced",
            claim_token=old_token,
        ) is False
        assert old_repository.mark_webhook_queued(
            "evt-fenced",
            processed_at=now,
            claim_token=old_token,
        ) is False
        old_session.commit()

    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-fenced"
            )
        )
        assert event.status == "processing"
        assert event.claim_token == new_token


def test_service_reads_webhook_claim_timeout_from_formal_settings(
    session_factory,
    client,
):
    settings = Settings(laike_webhook_claim_timeout_seconds=17)

    service = LaikeSyncService(
        session_factory=session_factory,
        client=client,
        settings=settings,
    )

    assert service.webhook_claim_timeout_seconds == 17


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


@pytest.mark.asyncio
async def test_reconcile_preserves_old_cursor_when_final_page_has_no_checkpoint(
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
            next_cursor=None,
            has_more=False,
        )
    ]

    result = await service.reconcile_account("account-001")

    assert result.success is True
    with session_factory() as session:
        assert session.scalar(
            select(LaikeSyncCursor.cursor).where(
                LaikeSyncCursor.account_id == "account-001"
            )
        ) == "old-cursor"


@pytest.mark.asyncio
async def test_reconcile_preserves_old_cursor_when_final_page_cursor_is_empty(
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
            next_cursor="",
            has_more=False,
        )
    ]

    result = await service.reconcile_account("account-001")

    assert result.success is True
    with session_factory() as session:
        assert session.scalar(
            select(LaikeSyncCursor.cursor).where(
                LaikeSyncCursor.account_id == "account-001"
            )
        ) == "old-cursor"


@pytest.mark.asyncio
async def test_reconcile_works_with_default_expiring_session_factory(
    default_session_factory,
    client,
):
    service = LaikeSyncService(
        session_factory=default_session_factory,
        client=client,
        settings=Settings(),
    )
    client.pages = [
        LaikePage(
            items=[{"order_id": "order-001", "status": "paid"}],
            next_cursor="cursor-001",
            has_more=False,
        )
    ]

    result = await service.reconcile_account("account-001")

    assert result.success is True
    with default_session_factory() as session:
        run = session.scalar(select(LaikeSyncRun))
        assert run.status == "succeeded"
        assert session.scalar(
            select(LaikeSyncCursor.cursor).where(
                LaikeSyncCursor.account_id == "account-001"
            )
        ) == "cursor-001"


@pytest.mark.asyncio
async def test_reconcile_rejects_historical_cursor_cycle(
    session_factory,
    client,
    service,
):
    with session_factory() as session:
        session.add(LaikeSyncCursor(account_id="account-001", cursor="A"))
        session.commit()
    client.pages = [
        LaikePage(items=[], next_cursor="B", has_more=True),
        LaikePage(items=[], next_cursor="A", has_more=True),
    ]

    result = await service.reconcile_account("account-001")

    assert result.success is False
    assert len(client.fetch_calls) == 2
    with session_factory() as session:
        run = session.scalar(select(LaikeSyncRun))
        assert "cycle" in run.error_message.lower()


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
