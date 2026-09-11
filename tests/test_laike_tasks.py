from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Lock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder, LaikeWebhookEvent
from app.laike.contracts import SyncResult
from app.laike.service import LaikeSyncService
from app.worker import laike_tasks


class FakeClient:
    async def verify_webhook(self, headers, raw_body):
        raise AssertionError("worker tests do not verify webhooks")

    async def fetch_orders(self, account_id, cursor=None, start_time=None, end_time=None):
        raise AssertionError("disabled reconcile must not fetch orders")


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'laike-tasks.db'}",
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def enabled_service(session_factory):
    return LaikeSyncService(
        session_factory=session_factory,
        client=FakeClient(),
        settings=Settings(
            laike_webhook_enabled=True,
            laike_reconcile_enabled=True,
            laike_sync_mode="shadow",
            laike_max_retries=2,
        ),
    )


def test_process_webhook_observe_succeeds_without_upsert(session_factory, monkeypatch):
    service = LaikeSyncService(
        session_factory=session_factory,
        client=FakeClient(),
        settings=Settings(laike_webhook_enabled=True, laike_sync_mode="observe"),
    )
    add_event(session_factory, "evt-observe")
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: service)

    result = laike_tasks.process_laike_webhook.run("evt-observe")

    assert result["status"] == "processed"
    with session_factory() as session:
        assert session.scalars(select(LaikeOrder)).all() == []


def add_event(
    session_factory,
    event_id: str,
    status: str = "queued",
    *,
    processed_at: datetime | None = None,
    claim_token: str | None = None,
    retry_count: int | None = None,
    next_retry_at: datetime | None = None,
    retry_scheduled_at: datetime | None = None,
) -> None:
    event_kwargs = {
        "event_id": event_id,
        "payload_json": {
            "event_id": event_id,
            "order_id": "order-001",
            "status": "paid",
        },
        "headers_json": {},
        "verified": True,
        "status": status,
        "processed_at": processed_at,
        "claim_token": claim_token,
    }
    if retry_count is not None:
        event_kwargs["retry_count"] = retry_count
    if next_retry_at is not None:
        event_kwargs["next_retry_at"] = next_retry_at
    if retry_scheduled_at is not None:
        event_kwargs["retry_scheduled_at"] = retry_scheduled_at
    with session_factory() as session:
        session.add(LaikeWebhookEvent(**event_kwargs))
        session.commit()


def utc_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def test_worker_tasks_are_registered_on_the_shared_celery_app():
    assert laike_tasks.process_laike_webhook.name in (
        laike_tasks.celery_app.tasks
    )
    assert laike_tasks.reconcile_laike_account.name in (
        laike_tasks.celery_app.tasks
    )
    assert laike_tasks.retry_failed_laike_events.name in (
        laike_tasks.celery_app.tasks
    )


def test_process_webhook_is_idempotent_for_processed_event(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-processed", status="processed")
    with session_factory() as session:
        session.add(
            LaikeOrder(
                provider_order_id="order-001",
                payload_json={"order_id": "order-001", "status": "paid"},
                status="paid",
            )
        )
        session.commit()

    monkeypatch.setattr(
        laike_tasks,
        "_service_factory",
        lambda: enabled_service,
    )

    result = laike_tasks.process_laike_webhook.run("evt-processed")

    assert result == {"status": "processed", "event_id": "evt-processed"}
    with session_factory() as session:
        assert len(session.scalars(select(LaikeOrder)).all()) == 1


def test_process_webhook_is_noop_when_flag_is_disabled(
    session_factory,
    monkeypatch,
):
    service = LaikeSyncService(
        session_factory=session_factory,
        client=FakeClient(),
        settings=Settings(laike_webhook_enabled=False),
    )
    add_event(session_factory, "evt-disabled")
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: service)

    assert laike_tasks.process_laike_webhook.run("evt-disabled") == {
        "status": "disabled",
        "event_id": "evt-disabled",
    }
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-disabled"
            )
        ) == "queued"


def test_process_webhook_processes_queued_event_once(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-queued")
    monkeypatch.setattr(
        laike_tasks,
        "_service_factory",
        lambda: enabled_service,
    )

    first = laike_tasks.process_laike_webhook.run("evt-queued")
    second = laike_tasks.process_laike_webhook.run("evt-queued")

    assert first["status"] == "processed"
    assert second == {"status": "processed", "event_id": "evt-queued"}
    with session_factory() as session:
        assert len(session.scalars(select(LaikeOrder)).all()) == 1
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-queued"
            )
        ) == "processed"


def test_process_claim_writes_consuming_fencing_token_before_processing(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-consume-token")
    observed: list[tuple[str, datetime | None, str | None]] = []

    def process_webhook(event_id, payload):
        with session_factory() as session:
            event = session.scalar(
                select(LaikeWebhookEvent).where(
                    LaikeWebhookEvent.event_id == event_id
                )
            )
            assert event is not None
            observed.append((event.status, event.processed_at, event.claim_token))
        return SyncResult(success=True, processed_count=1)

    enabled_service.process_webhook = process_webhook
    monkeypatch.setattr(
        laike_tasks,
        "_service_factory",
        lambda: enabled_service,
    )

    result = laike_tasks.process_laike_webhook.run("evt-consume-token")

    assert result["status"] == "processed"
    assert observed[0][0] == "consuming"
    assert observed[0][1] is not None
    assert observed[0][2] is not None
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-consume-token"
            )
        )
        assert event is not None
        assert event.status == "processed"
        assert event.claim_token == observed[0][2]


def test_unexpired_consuming_event_is_not_claimed_again(
    session_factory,
    enabled_service,
):
    current_token = "current-consumer-token"
    add_event(
        session_factory,
        "evt-live-consuming",
        status="consuming",
        processed_at=datetime.now(timezone.utc),
        claim_token=current_token,
    )

    status, payload, claim_token, claimed = (
        laike_tasks._claim_event_for_processing(
            enabled_service,
            "evt-live-consuming",
        )
    )

    assert status == "consuming"
    assert payload is not None
    assert claim_token is None
    assert claimed is False
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-live-consuming"
            )
        )
        assert event is not None
        assert event.claim_token == current_token


@pytest.mark.parametrize("processed_at", [None, datetime.now(timezone.utc) - timedelta(minutes=10)])
def test_stale_or_unset_consuming_event_gets_a_new_fencing_token(
    session_factory,
    enabled_service,
    processed_at,
):
    old_token = "old-consumer-token"
    add_event(
        session_factory,
        "evt-stale-consuming",
        status="consuming",
        processed_at=processed_at,
        claim_token=old_token,
    )

    status, payload, claim_token, claimed = (
        laike_tasks._claim_event_for_processing(
            enabled_service,
            "evt-stale-consuming",
        )
    )

    assert status == "consuming"
    assert payload is not None
    assert claimed is True
    assert claim_token is not None
    assert claim_token != old_token
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-stale-consuming"
            )
        )
        assert event is not None
        assert event.status == "consuming"
        assert event.processed_at is not None
        assert event.claim_token == claim_token


def test_old_consumer_cannot_finish_after_stale_claim_is_replaced(
    session_factory,
    enabled_service,
):
    old_token = "old-consumer-token"
    add_event(
        session_factory,
        "evt-fenced-consumer",
        status="consuming",
        processed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        claim_token=old_token,
    )

    _, _, new_token, claimed = laike_tasks._claim_event_for_processing(
        enabled_service,
        "evt-fenced-consumer",
    )

    assert claimed is True
    assert new_token is not None
    assert (
        laike_tasks._set_event_status(
            enabled_service,
            "evt-fenced-consumer",
            "processed",
            claim_token=old_token,
        )
        is False
    )
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-fenced-consumer"
            )
        )
        assert event is not None
        assert event.status == "consuming"
        assert event.claim_token == new_token


def test_process_webhook_retries_with_exponential_backoff_on_failure(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-retry")
    monkeypatch.setattr(
        laike_tasks,
        "_service_factory",
        lambda: enabled_service,
    )

    retry_calls: list[dict] = []

    def fake_retry(**kwargs):
        retry_calls.append(kwargs)
        raise RuntimeError("retry requested")

    monkeypatch.setattr(laike_tasks.process_laike_webhook, "retry", fake_retry)
    monkeypatch.setattr(
        enabled_service,
        "_process_page",
        lambda page: _failed_page(),
    )

    with pytest.raises(RuntimeError, match="retry requested"):
        laike_tasks.process_laike_webhook.run("evt-retry")

    assert retry_calls[0]["countdown"] == 1
    assert retry_calls[0]["max_retries"] == 2
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-retry"
            )
        ) == "failed"


def test_failure_persists_retry_schedule_and_scanner_waits_for_countdown(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-persisted-retry", retry_count=0)
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    monkeypatch.setattr(
        enabled_service,
        "_process_page",
        lambda page: _failed_page(),
    )

    def fake_retry(**kwargs):
        raise RuntimeError("retry requested")

    monkeypatch.setattr(laike_tasks.process_laike_webhook, "retry", fake_retry)

    with pytest.raises(RuntimeError, match="retry requested"):
        laike_tasks.process_laike_webhook.run("evt-persisted-retry")

    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-persisted-retry"
            )
        )
        assert event is not None
        assert event.status == "failed"
        assert event.retry_count == 1
        assert event.next_retry_at is not None
        assert utc_datetime(event.next_retry_at) > datetime.now(timezone.utc)

    enqueued: list[str] = []
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "delay",
        lambda event_id: enqueued.append(event_id),
    )
    result = laike_tasks.retry_failed_laike_events.run()

    assert result == {"status": "queued", "count": 0}
    assert enqueued == []


def test_failed_celery_retry_is_not_scanned_before_persisted_due_time(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-celery-countdown-race", retry_count=0)
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    monkeypatch.setattr(
        enabled_service,
        "_process_page",
        lambda page: _failed_page(),
    )
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "retry",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("retry requested")),
    )

    with pytest.raises(RuntimeError, match="retry requested"):
        laike_tasks.process_laike_webhook.run("evt-celery-countdown-race")

    enqueued: list[str] = []
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "delay",
        lambda event_id: enqueued.append(event_id),
    )
    assert laike_tasks.retry_failed_laike_events.run() == {
        "status": "queued",
        "count": 0,
    }
    assert enqueued == []
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-celery-countdown-race"
            )
        )
        assert event is not None
        assert event.status == "failed"
        assert event.retry_count == 1
        assert event.next_retry_at is not None


def test_retry_scanner_due_event_uses_persisted_count_after_celery_request_restart(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(
        session_factory,
        "evt-celery-request-restart",
        status="failed",
        retry_count=1,
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    enqueued: list[str] = []
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "delay",
        lambda event_id: enqueued.append(event_id),
    )

    laike_tasks.process_laike_webhook.push_request(retries=0)
    try:
        result = laike_tasks.retry_failed_laike_events.run()
    finally:
        laike_tasks.process_laike_webhook.pop_request()

    assert result == {"status": "queued", "count": 1}
    assert enqueued == ["evt-celery-request-restart"]
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-celery-request-restart"
            )
        )
        assert event is not None
        assert event.status == "retry_scheduled"
        assert event.retry_count == 1
        assert event.next_retry_at is not None


def test_old_retry_delivery_failure_cannot_clear_a_new_lease_with_same_timestamp(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(
        session_factory,
        "evt-retry-lease-fencing",
        status="failed",
        retry_count=1,
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)

    def first_delivery(event_id):
        with session_factory() as session:
            event = session.scalar(
                select(LaikeWebhookEvent).where(
                    LaikeWebhookEvent.event_id == event_id
                )
            )
            assert event is not None
            first_schedule = event.retry_scheduled_at
            assert event.claim_token is not None
            session.execute(
                LaikeWebhookEvent.__table__.update()
                .where(LaikeWebhookEvent.event_id == event_id)
                .values(
                    status="retry_scheduled",
                    retry_scheduled_at=first_schedule,
                    claim_token="new-lease-token",
                )
            )
            session.commit()
        raise RuntimeError("old delivery failed")

    monkeypatch.setattr(laike_tasks.process_laike_webhook, "delay", first_delivery)
    result = laike_tasks.retry_failed_laike_events.run()

    assert result == {"status": "queued", "count": 0}
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-retry-lease-fencing"
            )
        )
        assert event is not None
        assert event.status == "retry_scheduled"
        assert event.claim_token == "new-lease-token"


def test_second_retry_uses_persisted_count_even_when_celery_request_restarts(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(
        session_factory,
        "evt-persisted-second-retry",
        retry_count=1,
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    monkeypatch.setattr(
        enabled_service,
        "_process_page",
        lambda page: _failed_page(),
    )
    retry_calls: list[dict] = []

    def fake_retry(**kwargs):
        retry_calls.append(kwargs)
        raise RuntimeError("retry requested")

    monkeypatch.setattr(laike_tasks.process_laike_webhook, "retry", fake_retry)

    with pytest.raises(RuntimeError, match="retry requested"):
        laike_tasks.process_laike_webhook.run("evt-persisted-second-retry")

    assert retry_calls[0]["countdown"] == 2
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-persisted-second-retry"
            )
        )
        assert event is not None
        assert event.retry_count == 2


def test_persisted_retry_count_dead_letters_without_celery_request_retries(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(
        session_factory,
        "evt-persisted-max-retries",
        retry_count=2,
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    monkeypatch.setattr(
        enabled_service,
        "_process_page",
        lambda page: _failed_page(),
    )
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "retry",
        lambda **kwargs: pytest.fail("max retries must not call Celery retry"),
    )

    result = laike_tasks.process_laike_webhook.run("evt-persisted-max-retries")

    assert result == {
        "status": "dead_letter",
        "event_id": "evt-persisted-max-retries",
    }
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-persisted-max-retries"
            )
        ) == "dead_letter"


def test_process_webhook_uses_second_exponential_backoff(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-second-retry", retry_count=1)
    monkeypatch.setattr(
        laike_tasks,
        "_service_factory",
        lambda: enabled_service,
    )
    monkeypatch.setattr(
        enabled_service,
        "_process_page",
        lambda page: _failed_page(),
    )
    retry_calls: list[dict] = []

    def fake_retry(**kwargs):
        retry_calls.append(kwargs)
        raise RuntimeError("retry requested")

    monkeypatch.setattr(laike_tasks.process_laike_webhook, "retry", fake_retry)

    laike_tasks.process_laike_webhook.push_request(retries=1)
    try:
        with pytest.raises(RuntimeError, match="retry requested"):
            laike_tasks.process_laike_webhook.run("evt-second-retry")
    finally:
        laike_tasks.process_laike_webhook.pop_request()

    assert retry_calls[0]["countdown"] == 2
    assert retry_calls[0]["max_retries"] == 2


def test_process_webhook_dead_letters_after_max_retries(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-dead-letter", retry_count=2)
    monkeypatch.setattr(
        laike_tasks,
        "_service_factory",
        lambda: enabled_service,
    )
    monkeypatch.setattr(
        enabled_service,
        "_process_page",
        lambda page: _failed_page(),
    )

    laike_tasks.process_laike_webhook.push_request(retries=2)
    try:
        result = laike_tasks.process_laike_webhook.run("evt-dead-letter")
    finally:
        laike_tasks.process_laike_webhook.pop_request()

    assert result == {"status": "dead_letter", "event_id": "evt-dead-letter"}
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-dead-letter"
            )
        ) == "dead_letter"


def test_reconcile_task_is_noop_when_flag_is_disabled(
    session_factory,
    monkeypatch,
):
    service = LaikeSyncService(
        session_factory=session_factory,
        client=FakeClient(),
        settings=Settings(laike_reconcile_enabled=False),
    )
    called = False

    async def reconcile(account_id):
        nonlocal called
        called = True
        return SyncResult(success=True)

    monkeypatch.setattr(service, "reconcile_account", reconcile)
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: service)

    assert laike_tasks.reconcile_laike_account.run("account-001") == {
        "status": "disabled",
        "account_id": "account-001",
    }
    assert called is False


def test_retry_failed_only_enqueues_failed_events_when_enabled(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-failed", status="failed")
    add_event(session_factory, "evt-queued", status="queued")
    add_event(session_factory, "evt-dead", status="dead_letter")
    enqueued: list[str] = []

    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "delay",
        lambda event_id: enqueued.append(event_id),
    )

    result = laike_tasks.retry_failed_laike_events.run()

    assert result == {"status": "queued", "count": 1}
    assert enqueued == ["evt-failed"]


def test_retry_scanner_atomically_schedules_each_failed_event_once(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-scan-failed", status="failed")
    add_event(
        session_factory,
        "evt-scan-stale",
        status="consuming",
        processed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        claim_token="stale-token",
    )
    add_event(
        session_factory,
        "evt-scan-live",
        status="consuming",
        processed_at=datetime.now(timezone.utc),
        claim_token="live-token",
    )
    scheduled: list[str] = []

    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)

    def delay(event_id):
        with session_factory() as session:
            assert session.scalar(
                select(LaikeWebhookEvent.status).where(
                    LaikeWebhookEvent.event_id == event_id
                )
            ) == "retry_scheduled"
        scheduled.append(event_id)

    monkeypatch.setattr(laike_tasks.process_laike_webhook, "delay", delay)

    first = laike_tasks.retry_failed_laike_events.run()
    second = laike_tasks.retry_failed_laike_events.run()

    assert first == {"status": "queued", "count": 2}
    assert second == {"status": "queued", "count": 0}
    assert scheduled == ["evt-scan-failed", "evt-scan-stale"]


def test_concurrent_retry_scanners_enqueue_a_failed_event_once(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-concurrent-scan", status="failed")
    delay_started = Event()
    release_delay = Event()
    scheduled: list[str] = []
    scheduled_lock = Lock()

    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)

    def delay(event_id):
        with scheduled_lock:
            scheduled.append(event_id)
        delay_started.set()
        assert release_delay.wait(timeout=5)

    monkeypatch.setattr(laike_tasks.process_laike_webhook, "delay", delay)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(laike_tasks.retry_failed_laike_events.run)
            for _ in range(2)
        ]
        assert delay_started.wait(timeout=5)
        release_delay.set()
        results = [future.result(timeout=5) for future in futures]

    assert sum(result["count"] for result in results) == 1
    assert scheduled == ["evt-concurrent-scan"]


def test_retry_scanner_restores_failed_when_delay_raises(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-delay-error", status="failed")
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)

    def failing_delay(event_id):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "delay",
        failing_delay,
    )

    result = laike_tasks.retry_failed_laike_events.run()

    assert result["count"] == 0
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-delay-error"
            )
        ) == "failed"


def test_retry_scanner_reclaims_expired_retry_scheduled_event(
    session_factory,
    enabled_service,
    monkeypatch,
):
    old_schedule = datetime.now(timezone.utc) - timedelta(minutes=10)
    add_event(
        session_factory,
        "evt-expired-schedule",
        status="retry_scheduled",
        retry_count=1,
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        retry_scheduled_at=old_schedule,
    )
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    enqueued: list[str] = []
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "delay",
        lambda event_id: enqueued.append(event_id),
    )

    result = laike_tasks.retry_failed_laike_events.run()

    assert result == {"status": "queued", "count": 1}
    assert enqueued == ["evt-expired-schedule"]
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-expired-schedule"
            )
        )
        assert event is not None
        assert event.status == "retry_scheduled"
        assert event.retry_count == 1
        assert event.retry_scheduled_at is not None
        assert utc_datetime(event.retry_scheduled_at) > old_schedule


def test_retry_scanner_delay_error_restores_failed_without_losing_retry_schedule(
    session_factory,
    enabled_service,
    monkeypatch,
):
    next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    add_event(
        session_factory,
        "evt-delay-error-preserves-count",
        status="failed",
        retry_count=1,
        next_retry_at=next_retry_at,
    )
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: enabled_service)
    monkeypatch.setattr(
        laike_tasks.process_laike_webhook,
        "delay",
        lambda event_id: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )

    result = laike_tasks.retry_failed_laike_events.run()

    assert result == {"status": "queued", "count": 0}
    with session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == "evt-delay-error-preserves-count"
            )
        )
        assert event is not None
        assert event.status == "failed"
        assert event.retry_count == 1
        assert utc_datetime(event.next_retry_at) == next_retry_at
        assert event.retry_scheduled_at is None


def test_process_webhook_consumes_retry_scheduled_event(
    session_factory,
    enabled_service,
    monkeypatch,
):
    add_event(session_factory, "evt-retry-scheduled", status="retry_scheduled")
    monkeypatch.setattr(
        laike_tasks,
        "_service_factory",
        lambda: enabled_service,
    )

    result = laike_tasks.process_laike_webhook.run("evt-retry-scheduled")

    assert result["status"] == "processed"
    with session_factory() as session:
        assert session.scalar(
            select(LaikeWebhookEvent.status).where(
                LaikeWebhookEvent.event_id == "evt-retry-scheduled"
            )
        ) == "processed"


def test_retry_failed_is_noop_when_webhook_flag_is_disabled(
    session_factory,
    monkeypatch,
):
    service = LaikeSyncService(
        session_factory=session_factory,
        client=FakeClient(),
        settings=Settings(laike_webhook_enabled=False),
    )
    add_event(session_factory, "evt-disabled", status="failed")
    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: service)

    assert laike_tasks.retry_failed_laike_events.run() == {
        "status": "disabled",
        "count": 0,
    }


async def _failed_page():
    return 0, 1, ["order_failure_count=1"]
