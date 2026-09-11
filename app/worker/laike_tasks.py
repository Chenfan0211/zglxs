from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from celery import Celery
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import and_, or_, select, update

from app.db.models.laike import LaikeWebhookEvent
from app.laike.contracts import LaikePage, SyncResult
from app.worker.celery_app import create_celery_app


celery_app = create_celery_app()
_service_factory: Callable[[], Any] | None = None


def configure_service_factory(factory: Callable[[], Any] | None) -> None:
    global _service_factory
    _service_factory = factory


def _get_service() -> Any:
    if _service_factory is not None:
        return _service_factory()
    from app.main import app

    return app.state.laike_service_factory()


def _resolve(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)
    raise RuntimeError("Celery task cannot run an awaitable inside an event loop")


def _claim_event_for_processing(
    service: Any,
    event_id: str,
) -> tuple[str | None, dict[str, Any] | None, str | None, bool]:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(
        seconds=float(service.settings.laike_webhook_claim_timeout_seconds)
    )
    claim_token = str(uuid4())
    with service.session_factory() as session:
        result = session.execute(
            update(LaikeWebhookEvent)
            .where(
                LaikeWebhookEvent.event_id == event_id,
                or_(
                    LaikeWebhookEvent.status.in_(
                        ("queued", "retry_scheduled")
                    ),
                    and_(
                        LaikeWebhookEvent.status == "failed",
                        or_(
                            LaikeWebhookEvent.next_retry_at.is_(None),
                            LaikeWebhookEvent.next_retry_at <= now,
                        ),
                    ),
                    and_(
                        LaikeWebhookEvent.status == "consuming",
                        or_(
                            LaikeWebhookEvent.processed_at.is_(None),
                            LaikeWebhookEvent.processed_at < stale_before,
                        ),
                    ),
                ),
            )
            .values(
                status="consuming",
                processed_at=now,
                claim_token=claim_token,
                retry_scheduled_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        session.commit()
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == event_id
            )
        )
        if event is None:
            return None, None, None, False
        claimed = result.rowcount == 1
        return (
            event.status,
            dict(event.payload_json),
            claim_token if claimed else None,
            claimed,
        )


def _set_event_status(
    service: Any,
    event_id: str,
    status: str,
    *,
    claim_token: str,
    from_status: str = "consuming",
) -> bool:
    with service.session_factory() as session:
        values = {
            "status": status,
            "processed_at": datetime.now(timezone.utc),
        }
        if status in {"processed", "dead_letter"}:
            values.update(next_retry_at=None, retry_scheduled_at=None)
        result = session.execute(
            update(LaikeWebhookEvent)
            .where(
                LaikeWebhookEvent.event_id == event_id,
                LaikeWebhookEvent.status == from_status,
                LaikeWebhookEvent.claim_token == claim_token,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        session.commit()
        return result.rowcount == 1


def _record_event_failure(
    service: Any,
    event_id: str,
    claim_token: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    max_retries = int(service.settings.laike_max_retries)
    with service.session_factory() as session:
        event = session.scalar(
            select(LaikeWebhookEvent).where(
                LaikeWebhookEvent.event_id == event_id,
                LaikeWebhookEvent.status == "consuming",
                LaikeWebhookEvent.claim_token == claim_token,
            )
        )
        if event is None:
            return {"status": "fenced", "event_id": event_id}

        retry_count = int(event.retry_count or 0)
        if retry_count >= max_retries:
            result = session.execute(
                update(LaikeWebhookEvent)
                .where(
                    LaikeWebhookEvent.event_id == event_id,
                    LaikeWebhookEvent.status == "consuming",
                    LaikeWebhookEvent.claim_token == claim_token,
                )
                .values(
                    status="dead_letter",
                    processed_at=now,
                    next_retry_at=None,
                    retry_scheduled_at=None,
                    claim_token=None,
                )
                .execution_options(synchronize_session=False)
            )
            session.commit()
            if result.rowcount != 1:
                return {"status": "fenced", "event_id": event_id}
            return {"status": "dead_letter", "event_id": event_id}

        countdown = 2**retry_count
        result = session.execute(
            update(LaikeWebhookEvent)
            .where(
                LaikeWebhookEvent.event_id == event_id,
                LaikeWebhookEvent.status == "consuming",
                LaikeWebhookEvent.claim_token == claim_token,
            )
            .values(
                status="failed",
                processed_at=now,
                retry_count=retry_count + 1,
                next_retry_at=now + timedelta(seconds=countdown),
                retry_scheduled_at=None,
                claim_token=None,
            )
            .execution_options(synchronize_session=False)
        )
        session.commit()
        if result.rowcount != 1:
            return {"status": "fenced", "event_id": event_id}
        return {
            "status": "failed",
            "event_id": event_id,
            "retry_count": retry_count + 1,
            "countdown": countdown,
        }


def _retry_task(
    task: Any,
    service: Any,
    *,
    event_id: str | None,
    claim_token: str | None = None,
    exc: Exception,
) -> dict[str, Any]:
    max_retries = int(service.settings.laike_max_retries)
    if event_id is not None:
        if claim_token is None:
            return {"status": "fenced", "event_id": event_id}
        event_failure = _record_event_failure(service, event_id, claim_token)
        if event_failure["status"] != "failed":
            return event_failure
        countdown = int(event_failure["countdown"])
        request_retries = int(getattr(task.request, "retries", 0))
        celery_max_retries = max(max_retries, request_retries + 1)
    else:
        request_retries = int(getattr(task.request, "retries", 0))
        if request_retries >= max_retries:
            return {"status": "dead_letter"}
        countdown = 2**request_retries
        celery_max_retries = max_retries
    try:
        raise task.retry(
            exc=exc,
            countdown=countdown,
            max_retries=celery_max_retries,
        )
    except MaxRetriesExceededError:
        return {
            "status": "failed" if event_id is not None else "dead_letter",
            **({"event_id": event_id} if event_id is not None else {}),
        }


@celery_app.task(bind=True, name="process_laike_webhook")
def process_laike_webhook(task: Any, event_id: str) -> dict[str, Any]:
    service = _get_service()
    if not service.settings.laike_webhook_enabled:
        return {"status": "disabled", "event_id": event_id}

    status, payload, claim_token, claimed = _claim_event_for_processing(
        service,
        event_id,
    )
    if status is None:
        return {"status": "missing", "event_id": event_id}
    if status in {"processed", "dead_letter"}:
        return {"status": status, "event_id": event_id}
    if not claimed:
        return {"status": status, "event_id": event_id}
    assert payload is not None

    try:
        processor = getattr(service, "process_webhook", None)
        if processor is not None:
            result = _resolve(processor(event_id, payload))
            if isinstance(result, SyncResult):
                processed_count = result.processed_count
                failed_count = result.failed_count
            else:
                result = SyncResult.model_validate(result)
                processed_count = result.processed_count
                failed_count = result.failed_count
        else:
            processed_count, failed_count, _ = _resolve(
                service._process_page(
                    LaikePage(items=[payload], has_more=False)
                )
            )
        if failed_count:
            raise ValueError("webhook payload processing failed")
        if not processed_count:
            raise ValueError("webhook payload was not processed")
        assert claim_token is not None
        if not _set_event_status(
            service,
            event_id,
            "processed",
            claim_token=claim_token,
        ):
            return {"status": "fenced", "event_id": event_id}
        return {
            "status": "processed",
            "event_id": event_id,
            "processed_count": processed_count,
        }
    except Exception as exc:
        return _retry_task(
            task,
            service,
            event_id=event_id,
            claim_token=claim_token,
            exc=exc,
        )


@celery_app.task(bind=True, name="reconcile_laike_account")
def reconcile_laike_account(task: Any, account_id: str) -> dict[str, Any]:
    service = _get_service()
    if not service.settings.laike_reconcile_enabled:
        return {"status": "disabled", "account_id": account_id}
    try:
        result = _resolve(service.reconcile_account(account_id))
        if not isinstance(result, SyncResult):
            result = SyncResult.model_validate(result)
        if not result.success:
            raise RuntimeError("laike reconciliation failed")
        return {
            "status": "succeeded",
            "account_id": account_id,
            **result.model_dump(),
        }
    except Exception as exc:
        return _retry_task(
            task,
            service,
            event_id=None,
            exc=exc,
        )


@celery_app.task(name="retry_failed_laike_events")
def retry_failed_laike_events() -> dict[str, Any]:
    service = _get_service()
    if not service.settings.laike_webhook_enabled:
        return {"status": "disabled", "count": 0}

    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(
        seconds=float(service.settings.laike_webhook_claim_timeout_seconds)
    )
    with service.session_factory() as session:
        candidates = list(
            session.scalars(
                select(LaikeWebhookEvent.event_id).where(
                    or_(
                        and_(
                            LaikeWebhookEvent.status == "failed",
                            or_(
                                LaikeWebhookEvent.next_retry_at.is_(None),
                                LaikeWebhookEvent.next_retry_at <= now,
                            ),
                        ),
                        and_(
                            LaikeWebhookEvent.status == "retry_scheduled",
                            or_(
                                LaikeWebhookEvent.retry_scheduled_at.is_(None),
                                LaikeWebhookEvent.retry_scheduled_at < stale_before,
                            ),
                        ),
                        and_(
                            LaikeWebhookEvent.status == "consuming",
                            or_(
                                LaikeWebhookEvent.processed_at.is_(None),
                                LaikeWebhookEvent.processed_at < stale_before,
                            ),
                        ),
                    )
                )
            )
        )
        scheduled_events: list[tuple[str, datetime]] = []
        for event_id in candidates:
            result = session.execute(
                update(LaikeWebhookEvent)
                .where(
                    LaikeWebhookEvent.event_id == event_id,
                    or_(
                        and_(
                            LaikeWebhookEvent.status == "failed",
                            or_(
                                LaikeWebhookEvent.next_retry_at.is_(None),
                                LaikeWebhookEvent.next_retry_at <= now,
                            ),
                        ),
                        and_(
                            LaikeWebhookEvent.status == "retry_scheduled",
                            or_(
                                LaikeWebhookEvent.retry_scheduled_at.is_(None),
                                LaikeWebhookEvent.retry_scheduled_at < stale_before,
                            ),
                        ),
                        and_(
                            LaikeWebhookEvent.status == "consuming",
                            or_(
                                LaikeWebhookEvent.processed_at.is_(None),
                                LaikeWebhookEvent.processed_at < stale_before,
                            ),
                        ),
                    ),
                )
                .values(
                    status="retry_scheduled",
                    processed_at=None,
                    claim_token=None,
                    retry_scheduled_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                scheduled_events.append((event_id, now))
        session.commit()

    queued_count = 0
    for event_id, scheduled_at in scheduled_events:
        try:
            process_laike_webhook.delay(event_id)
        except Exception:
            with service.session_factory() as session:
                session.execute(
                    update(LaikeWebhookEvent)
                    .where(
                        LaikeWebhookEvent.event_id == event_id,
                        LaikeWebhookEvent.status == "retry_scheduled",
                        LaikeWebhookEvent.retry_scheduled_at == scheduled_at,
                    )
                    .values(
                        status="failed",
                        processed_at=None,
                        claim_token=None,
                        retry_scheduled_at=None,
                    )
                    .execution_options(synchronize_session=False)
                )
                session.commit()
            continue
        queued_count += 1
    return {"status": "queued", "count": queued_count}
