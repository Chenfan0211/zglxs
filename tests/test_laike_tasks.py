from __future__ import annotations

import asyncio
from types import SimpleNamespace

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
            laike_max_retries=2,
        ),
    )


def add_event(session_factory, event_id: str, status: str = "queued") -> None:
    with session_factory() as session:
        session.add(
            LaikeWebhookEvent(
                event_id=event_id,
                payload_json={
                    "event_id": event_id,
                    "order_id": "order-001",
                    "status": "paid",
                },
                headers_json={},
                verified=True,
                status=status,
            )
        )
        session.commit()


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
