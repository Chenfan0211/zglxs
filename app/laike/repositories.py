from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.laike import (
    LaikeOrder,
    LaikeSyncCursor,
    LaikeSyncRun,
    LaikeWebhookEvent,
)


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
    ) -> LaikeWebhookEvent:
        existing = self.get_webhook_event(event_id)
        if existing is not None:
            return existing
        try:
            with self.session.begin_nested():
                event = LaikeWebhookEvent(
                    event_id=event_id,
                    payload_json=payload_json,
                    headers_json=headers_json,
                    verified=verified,
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

    def upsert_order(
        self,
        provider_order_id: str,
        payload_json: dict[str, Any],
        status: str | None,
        created_at: str | None,
    ) -> LaikeOrder:
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
                    )
                    self.session.add(order)
                    self.session.flush()
                return order
            except IntegrityError:
                order = self.session.scalar(
                    select(LaikeOrder).where(
                        LaikeOrder.provider_order_id == provider_order_id
                    )
                )
                if order is None:
                    raise
        else:
            order.payload_json = payload_json
            order.status = status
            order.created_at = created_at
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
