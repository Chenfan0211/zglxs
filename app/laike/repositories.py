from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.laike import (
    LaikeOrder,
    LaikeSyncCursor,
    LaikeSyncRun,
    LaikeWebhookEvent,
)


SENSITIVE_HEADER_KEY_PARTS = (
    "authorization",
    "cookie",
    "token",
    "secret",
    "signature",
    "password",
    "api-key",
    "credential",
)


def sanitize_request_headers(headers: dict[str, str]) -> dict[str, str]:
    """Keep tracing headers while excluding credential material from storage."""
    return {
        key: value
        for key, value in headers.items()
        if not any(part in key.lower().replace("_", "-") for part in SENSITIVE_HEADER_KEY_PARTS)
    }


class LaikeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_webhook_event(self, event_id: str) -> LaikeWebhookEvent | None:
        return self.session.scalar(
            select(LaikeWebhookEvent).where(LaikeWebhookEvent.event_id == event_id)
        )

    def insert_webhook_event(
        self,
        event_id: str,
        payload_json: dict[str, Any],
        headers_json: dict[str, str],
        verified: bool,
        source: str = "laike",
        error_reason: str | None = None,
    ) -> LaikeWebhookEvent:
        existing = self.get_webhook_event(event_id)
        if existing is not None:
            return existing
        safe_headers = sanitize_request_headers(headers_json)
        try:
            with self.session.begin_nested():
                event = LaikeWebhookEvent(
                    event_id=event_id,
                    payload_json=payload_json,
                    headers_json=safe_headers,
                    verified=verified,
                    source=source,
                    error_reason=error_reason,
                )
                self.session.add(event)
                self.session.flush()
            return event
        except IntegrityError:
            existing = self.get_webhook_event(event_id)
            if existing is None:
                raise
            return existing

    def update_webhook_event(
        self,
        event: LaikeWebhookEvent,
        *,
        status: str | None = None,
        processed_at: datetime | None = None,
    ) -> LaikeWebhookEvent:
        if status is not None:
            event.status = status
        if processed_at is not None:
            event.processed_at = processed_at
        self.session.flush()
        return event

    def claim_webhook_event(
        self,
        event_id: str,
        *,
        claimed_at: datetime,
        stale_before: datetime,
    ) -> str | None:
        claim_token = str(uuid4())
        result = self.session.execute(
            update(LaikeWebhookEvent)
            .where(
                LaikeWebhookEvent.event_id == event_id,
                or_(
                    LaikeWebhookEvent.status == "received",
                    and_(
                        LaikeWebhookEvent.status == "processing",
                        or_(
                            LaikeWebhookEvent.processed_at.is_(None),
                            LaikeWebhookEvent.processed_at < stale_before,
                        ),
                    ),
                ),
            )
            .values(
                status="processing",
                processed_at=claimed_at,
                claim_token=claim_token,
            )
            .execution_options(synchronize_session=False)
        )
        return claim_token if result.rowcount == 1 else None

    def release_webhook_claim(self, event_id: str, *, claim_token: str) -> bool:
        result = self.session.execute(
            update(LaikeWebhookEvent)
            .where(
                LaikeWebhookEvent.event_id == event_id,
                LaikeWebhookEvent.status == "processing",
                LaikeWebhookEvent.claim_token == claim_token,
            )
            .values(status="received", processed_at=None, claim_token=None)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def mark_webhook_queued(
        self,
        event_id: str,
        processed_at: datetime,
        *,
        claim_token: str,
    ) -> bool:
        result = self.session.execute(
            update(LaikeWebhookEvent)
            .where(
                LaikeWebhookEvent.event_id == event_id,
                LaikeWebhookEvent.status == "processing",
                LaikeWebhookEvent.claim_token == claim_token,
            )
            .values(status="queued", processed_at=processed_at)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def upsert_order(
        self,
        provider_order_id: str,
        payload_json: dict[str, Any],
        status: str | None,
        created_at: str | None = None,
        *,
        subject_id: str | None = None,
        product_id: str | None = None,
        original_created_at: Any = None,
        normalized_created_at: str | None = None,
        original_updated_at: Any = None,
        normalized_updated_at: str | None = None,
    ) -> LaikeOrder:
        if original_created_at is None and created_at is not None:
            original_created_at = created_at
        if created_at is None and isinstance(original_created_at, str):
            created_at = original_created_at
        now = datetime.now(timezone.utc)
        order = self.session.scalar(
            select(LaikeOrder).where(
                LaikeOrder.provider_order_id == provider_order_id
            )
        )
        if order is None:
            try:
                with self.session.begin_nested():
                    order = LaikeOrder(
                        provider_order_id=provider_order_id,
                        payload_json=payload_json,
                        status=status,
                        created_at=created_at,
                        subject_id=subject_id,
                        product_id=product_id,
                        original_created_at=original_created_at,
                        normalized_created_at=normalized_created_at,
                        original_updated_at=original_updated_at,
                        normalized_updated_at=normalized_updated_at,
                        first_discovered_at=now,
                        last_updated_at=now,
                    )
                    self.session.add(order)
                    self.session.flush()
            except IntegrityError:
                order = self.session.scalar(
                    select(LaikeOrder).where(
                        LaikeOrder.provider_order_id == provider_order_id
                    )
                )
                if order is None:
                    raise
            else:
                return order
        order.payload_json = payload_json
        for field, value in {
            "status": status,
            "created_at": created_at,
            "subject_id": subject_id,
            "product_id": product_id,
            "original_created_at": original_created_at,
            "normalized_created_at": normalized_created_at,
            "original_updated_at": original_updated_at,
            "normalized_updated_at": normalized_updated_at,
        }.items():
            if value is not None:
                setattr(order, field, value)
        order.last_updated_at = now
        self.session.flush()
        return order

    def get_cursor(self, account_id: str) -> LaikeSyncCursor | None:
        return self.session.scalar(
            select(LaikeSyncCursor).where(LaikeSyncCursor.account_id == account_id)
        )

    def advance_cursor(self, account_id: str, cursor: str | None) -> LaikeSyncCursor:
        record = self.get_cursor(account_id)
        if record is None:
            try:
                with self.session.begin_nested():
                    record = LaikeSyncCursor(account_id=account_id, cursor=cursor)
                    self.session.add(record)
                    self.session.flush()
                return record
            except IntegrityError:
                record = self.get_cursor(account_id)
                if record is None:
                    raise
        else:
            record.cursor = cursor
            record.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return record

    def start_run(
        self,
        account_id: str,
        start_time: str | None,
        end_time: str | None,
    ) -> LaikeSyncRun:
        run = LaikeSyncRun(
            account_id=account_id,
            start_time=start_time,
            end_time=end_time,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def finish_run(
        self,
        run: LaikeSyncRun,
        *,
        status: str,
        processed_count: int,
        failed_count: int,
        error_message: str | None = None,
    ) -> LaikeSyncRun:
        run.status = status
        run.processed_count = processed_count
        run.failed_count = failed_count
        run.error_message = error_message
        run.finished_at = datetime.now(timezone.utc)
        self.session.flush()
        return run
