from __future__ import annotations

import hashlib
import inspect
import json
import asyncio
from datetime import datetime, timedelta, timezone
from collections.abc import Callable, Mapping
from typing import Any

from app.db.session import UnitOfWork
from app.db.models.laike import LaikeSyncRun
from app.laike.contracts import LaikePage, SyncResult, WebhookVerification
from app.laike.normalizer import normalize_order

from .repositories import LaikeRepository


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class LaikeSyncService:
    def __init__(
        self,
        session_factory,
        client,
        settings,
        enqueuer: Callable[..., Any] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.client = client
        self.settings = settings
        self.enqueuer = enqueuer
        self.webhook_claim_timeout_seconds = float(
            getattr(settings, "laike_webhook_claim_timeout_seconds", 300)
        )

    async def receive_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> SyncResult:
        verification = await self._verify_webhook(headers, raw_body)
        if not verification.verified:
            return SyncResult(success=False, failed_count=1)

        payload = json.loads(raw_body)
        event_id = self._event_id(headers, payload, raw_body)
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=self.webhook_claim_timeout_seconds)
        with UnitOfWork(self.session_factory) as unit:
            repository = LaikeRepository(unit.session)
            event = repository.get_webhook_event(event_id)
            if event is not None and event.status == "queued":
                return SyncResult(success=True)
            event = repository.insert_webhook_event(
                event_id, payload, dict(headers), verification.verified
            )
            claimed = repository.claim_webhook_event(
                event_id,
                claimed_at=now,
                stale_before=stale_before,
            )
            enqueue_event_id = event.event_id
            enqueue_payload = dict(event.payload_json)

        if not claimed:
            return SyncResult(success=True)

        try:
            if self.enqueuer is not None:
                await _maybe_await(self.enqueuer(enqueue_event_id, enqueue_payload))
        except asyncio.CancelledError:
            with UnitOfWork(self.session_factory) as unit:
                LaikeRepository(unit.session).release_webhook_claim(event_id)
            raise
        except Exception:
            with UnitOfWork(self.session_factory) as unit:
                LaikeRepository(unit.session).release_webhook_claim(event_id)
            return SyncResult(success=False, failed_count=1)

        with UnitOfWork(self.session_factory) as unit:
            repository = LaikeRepository(unit.session)
            repository.mark_webhook_queued(
                event_id,
                datetime.now(timezone.utc),
            )
        return SyncResult(success=True, processed_count=1)

    async def reconcile_account(
        self,
        account_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> SyncResult:
        with UnitOfWork(self.session_factory) as unit:
            run = LaikeRepository(unit.session).start_run(
                account_id, start_time, end_time
            )
            run_id = run.id

        processed_count = 0
        failed_count = 0
        error_message: str | None = None
        page_success = True
        cursor = self._read_cursor(account_id)
        initial_cursor = cursor
        seen_cursors: set[str | None] = {cursor}
        final_cursor: str | None = cursor
        failure_summaries: list[str] = []

        try:
            while True:
                page = await self._fetch_page(
                    account_id, start_time, end_time, cursor
                )
                page_processed, page_failed, page_errors = await self._process_page(
                    page
                )
                processed_count += page_processed
                failed_count += page_failed
                failure_summaries.extend(page_errors)
                if page_failed:
                    page_success = False
                if not page.has_more:
                    if page.next_cursor:
                        final_cursor = page.next_cursor
                    break
                if not page.next_cursor:
                    raise ValueError(
                        "pagination cursor must be non-empty and advance"
                    )
                if page.next_cursor in seen_cursors:
                    raise ValueError("pagination cursor cycle detected")
                seen_cursors.add(page.next_cursor)
                cursor = page.next_cursor
                final_cursor = cursor
            if page_success and final_cursor is not None and final_cursor != initial_cursor:
                self._advance_cursor(account_id, final_cursor)
        except Exception as exc:
            page_success = False
            error_message = f"{type(exc).__name__}: {self._safe_error_text(exc)}"

        if failure_summaries:
            item_error_message = "; ".join(failure_summaries)
            error_message = (
                f"{error_message}; {item_error_message}"
                if error_message
                else item_error_message
            )

        with UnitOfWork(self.session_factory) as unit:
            repository = LaikeRepository(unit.session)
            persisted_run = unit.session.get(LaikeSyncRun, run_id)
            assert persisted_run is not None
            repository.finish_run(
                persisted_run,
                status="succeeded" if page_success else "failed",
                processed_count=processed_count,
                failed_count=failed_count,
                error_message=error_message,
            )

        return SyncResult(
            success=page_success,
            processed_count=processed_count,
            failed_count=failed_count,
        )

    async def _verify_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        verifier = getattr(self.client, "verify_webhook", None)
        if verifier is None:
            return WebhookVerification(verified=True)
        result = await _maybe_await(verifier(dict(headers), raw_body))
        if isinstance(result, WebhookVerification):
            return result
        return WebhookVerification.model_validate(result)

    async def _fetch_page(
        self,
        account_id: str,
        start_time: str | None,
        end_time: str | None,
        cursor: str | None,
    ) -> LaikePage:
        fetcher = getattr(self.client, "fetch_orders", None)
        if fetcher is None:
            fetcher = getattr(self.client, "list_orders")
        result = await _maybe_await(
            fetcher(
                account_id,
                start_time=start_time,
                end_time=end_time,
                cursor=cursor,
            )
        )
        if isinstance(result, LaikePage):
            return result
        return LaikePage.model_validate(result)

    async def _process_page(
        self, page: LaikePage
    ) -> tuple[int, int, list[str]]:
        processed_count = 0
        failed_count = 0
        failure_summaries: list[str] = []
        for payload in page.items:
            try:
                order = normalize_order(payload)
                if not order.order_id:
                    raise ValueError("normalized order has no order_id")
                with UnitOfWork(self.session_factory) as unit:
                    LaikeRepository(unit.session).upsert_order(
                        order.order_id,
                        order.payload_json,
                        order.status,
                        order.created_at,
                    )
                processed_count += 1
            except Exception as exc:
                failed_count += 1
                failure_summaries.append(self._order_error_summary(payload, exc))
        return processed_count, failed_count, failure_summaries

    def _read_cursor(self, account_id: str) -> str | None:
        with self.session_factory() as session:
            cursor = LaikeRepository(session).get_cursor(account_id)
            return cursor.cursor if cursor is not None else None

    def _advance_cursor(self, account_id: str, cursor: str | None) -> None:
        with UnitOfWork(self.session_factory) as unit:
            LaikeRepository(unit.session).advance_cursor(account_id, cursor)

    @staticmethod
    def _order_error_summary(payload: Any, exc: Exception) -> str:
        provider_order_id = (
            payload.get("order_id") if isinstance(payload, Mapping) else None
        )
        order_ref = (
            hashlib.sha256(str(provider_order_id).encode("utf-8")).hexdigest()[:12]
            if provider_order_id
            else "missing"
        )
        return (
            f"order_failure_count=1; order_ref={order_ref}; "
            f"exception_type={type(exc).__name__}"
        )

    @staticmethod
    def _safe_error_text(exc: Exception) -> str:
        if isinstance(exc, ValueError) and "cycle" in str(exc).lower():
            return "pagination cursor cycle"
        if isinstance(exc, ValueError) and "cursor" in str(exc).lower():
            return "pagination cursor invalid"
        if isinstance(exc, ValueError):
            return "invalid input"
        return "operation failed"

    @staticmethod
    def _event_id(
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        raw_body: bytes,
    ) -> str:
        normalized_headers = {
            key.lower().replace("_", "-"): value for key, value in headers.items()
        }
        return (
            normalized_headers.get("x-event-id")
            or normalized_headers.get("event-id")
            or str(payload.get("event_id") or "")
            or hashlib.sha256(raw_body).hexdigest()
        )
