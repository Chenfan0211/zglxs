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
from app.laike.client import DouyinLaikeClient
from app.laike.contracts import LaikePage, SyncResult, WebhookVerification
from app.laike.normalizer import (
    NormalizationError,
    normalize_douyin_order,
    normalize_order,
)
from app.laike.provider_errors import LaikeProviderError

from .repositories import LaikeRepository


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


_DEFAULT_NORMALIZER = object()


class LaikeSyncService:
    def __init__(
        self,
        session_factory,
        client,
        settings,
        enqueuer: Callable[..., Any] | None = None,
        normalizer: Any = _DEFAULT_NORMALIZER,
    ) -> None:
        self.session_factory = session_factory
        self.client = client
        self.settings = settings
        self.enqueuer = enqueuer
        if normalizer is _DEFAULT_NORMALIZER:
            self.normalizer = (
                normalize_douyin_order
                if isinstance(client, DouyinLaikeClient)
                else normalize_order
            )
        else:
            self.normalizer = normalizer
        self._current_account_id: str | None = None
        self._last_page_duplicate_count = 0
        self.webhook_claim_timeout_seconds = float(
            settings.laike_webhook_claim_timeout_seconds
        )

    async def receive_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> SyncResult:
        verification = await self._verify_webhook(headers, raw_body)
        if not verification.verified:
            return SyncResult(
                success=False,
                failed_count=1,
                reason=verification.reason or "invalid webhook signature",
            )

        payload = json.loads(raw_body)
        event_id = self._event_id(
            headers,
            payload,
            raw_body,
            event_id=verification.event_id,
            legacy_compatibility=verification.legacy_compatibility,
        )
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

        if self.enqueuer is None:
            with UnitOfWork(self.session_factory) as unit:
                LaikeRepository(unit.session).release_webhook_claim(
                    event_id,
                    claim_token=claimed,
                )
            return SyncResult(success=False, failed_count=1)

        try:
            await _maybe_await(self.enqueuer(enqueue_event_id, enqueue_payload))
        except asyncio.CancelledError:
            with UnitOfWork(self.session_factory) as unit:
                LaikeRepository(unit.session).release_webhook_claim(
                    event_id,
                    claim_token=claimed,
                )
            raise
        except Exception:
            with UnitOfWork(self.session_factory) as unit:
                LaikeRepository(unit.session).release_webhook_claim(
                    event_id,
                    claim_token=claimed,
                )
            return SyncResult(success=False, failed_count=1)

        with UnitOfWork(self.session_factory) as unit:
            repository = LaikeRepository(unit.session)
            repository.mark_webhook_queued(
                event_id,
                datetime.now(timezone.utc),
                claim_token=claimed,
            )
        return SyncResult(success=True, processed_count=1)

    async def process_webhook(
        self, event_id: str, payload: Mapping[str, Any] | None = None
    ) -> SyncResult:
        self._current_account_id = None
        if payload is None:
            with self.session_factory() as session:
                event = LaikeRepository(session).get_webhook_event(event_id)
                if event is None:
                    return SyncResult(success=False, event_id=event_id, reason="event not found")
                payload = event.payload_json
        processed_count, failed_count, errors = await self._process_page(
            LaikePage(items=[payload], has_more=False)
        )
        return SyncResult(
            success=failed_count == 0,
            event_id=event_id,
            processed_count=processed_count,
            failed_count=failed_count,
            reason="; ".join(errors) if errors else None,
        )

    async def reconcile_account(
        self,
        account_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> SyncResult:
        if (start_time is None) != (end_time is None):
            return SyncResult(
                success=False,
                failed_count=1,
                reason="start_time and end_time must be provided together",
            )
        self._current_account_id = account_id
        start_time, end_time = self._resolve_window(start_time, end_time, account_id)
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
        page_count = 0
        fetched_count = 0
        duplicate_count = 0
        error_code: int | None = None

        try:
            while True:
                page_count += 1
                page = await self._fetch_page(
                    account_id, start_time, end_time, cursor
                )
                fetched_count += len(page.items)
                self._last_page_duplicate_count = 0
                page_processed, page_failed, page_errors = await self._process_page(
                    page
                )
                processed_count += page_processed
                failed_count += page_failed
                duplicate_count += self._last_page_duplicate_count
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
            if page_success:
                self._advance_cursor(
                    account_id,
                    final_cursor,
                    page_num=page_count,
                    last_success_at=datetime.now(timezone.utc),
                )
        except Exception as exc:
            page_success = False
            error_code = exc.code if isinstance(exc, LaikeProviderError) else None
            error_message = f"{type(exc).__name__}: {self._safe_error_text(exc)}"

        if failure_summaries:
            item_error_message = "; ".join(failure_summaries)
            error_message = (
                f"{error_message}; {item_error_message}"
                if error_message
                else item_error_message
            )

        if not page_success:
            with UnitOfWork(self.session_factory) as unit:
                LaikeRepository(unit.session).record_cursor_failure(account_id)

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
                page_count=page_count,
                fetched_count=fetched_count,
                succeeded_count=processed_count,
                duplicate_count=duplicate_count,
                error_code=error_code,
            )

        return SyncResult(
            success=page_success,
            processed_count=processed_count,
            failed_count=failed_count,
            fetched_count=fetched_count,
            succeeded_count=processed_count,
            duplicate_count=duplicate_count,
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
        self._last_page_duplicate_count = 0
        for payload in page.items:
            try:
                if self.normalizer is None:
                    raise NormalizationError(
                        "laike order normalizer is not configured"
                    )
                order = self._normalize_payload(payload)
                if not order.order_id:
                    raise ValueError("normalized order has no order_id")
                if self._orders_write_enabled:
                    with UnitOfWork(self.session_factory) as unit:
                        repository = LaikeRepository(unit.session)
                        if repository.get_order(order.order_id) is not None:
                            self._last_page_duplicate_count += 1
                        repository.upsert_order(
                            order.order_id,
                            order.payload_json,
                            order.status,
                            order.created_at,
                            account_id=order.account_id or self._current_account_id,
                            order_status=order.order_status,
                            pay_amount_fen=order.pay_amount_fen,
                            create_order_time=order.create_order_time,
                            update_order_time=order.update_order_time,
                            pay_time=order.pay_time,
                            subject_id=order.subject_id,
                            product_id=order.product_id,
                            original_created_at=order.original_created_at,
                            normalized_created_at=order.normalized_created_at,
                            original_updated_at=order.original_updated_at,
                            normalized_updated_at=order.normalized_updated_at,
                        )
                processed_count += 1
            except Exception as exc:
                failed_count += 1
                failure_summaries.append(self._order_error_summary(payload, exc))
        return processed_count, failed_count, failure_summaries

    def _normalize_payload(self, payload: Mapping[str, Any]) -> Any:
        normalizer = getattr(self.normalizer, "normalize", self.normalizer)
        try:
            parameters = inspect.signature(normalizer).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "account_id" in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ):
            return normalizer(payload, account_id=self._current_account_id)
        return normalizer(payload)

    @property
    def _orders_write_enabled(self) -> bool:
        return self.settings.laike_sync_mode == "shadow" or (
            self.settings.laike_sync_mode == "write"
            and self.settings.laike_write_enabled is True
        )

    def _read_cursor(self, account_id: str) -> str | None:
        with self.session_factory() as session:
            cursor = LaikeRepository(session).get_cursor(account_id)
            return cursor.cursor if cursor is not None else None

    def _advance_cursor(
        self,
        account_id: str,
        cursor: str | None,
        *,
        page_num: int = 1,
        last_success_at: datetime | None = None,
    ) -> None:
        with UnitOfWork(self.session_factory) as unit:
            LaikeRepository(unit.session).advance_cursor(
                account_id,
                cursor,
                page_num=page_num,
                last_success_at=last_success_at,
            )

    def _read_cursor_state(self, account_id: str) -> tuple[str | None, datetime | None]:
        with self.session_factory() as session:
            cursor = LaikeRepository(session).get_cursor(account_id)
            if cursor is None:
                return None, None
            return cursor.cursor, cursor.last_success_at

    def _resolve_window(
        self,
        start_time: str | None,
        end_time: str | None,
        account_id: str,
    ) -> tuple[str, str]:
        if start_time is not None and end_time is not None:
            return start_time, end_time
        now = datetime.now(timezone.utc)
        _, last_success_at = self._read_cursor_state(account_id)
        if last_success_at is None:
            start = now - timedelta(
                seconds=int(self.settings.laike_initial_lookback_seconds)
            )
        else:
            start = last_success_at - timedelta(
                seconds=int(self.settings.laike_overlap_seconds)
            )
        return _format_utc(start), _format_utc(now)
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
        headers: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
        raw_body: bytes = b"",
        *,
        event_id: str | None = None,
        legacy_compatibility: bool = False,
    ) -> str:
        if isinstance(event_id, str) and event_id.strip():
            return event_id.strip()
        if legacy_compatibility:
            normalized_headers = {
                key.lower().replace("_", "-"): value
                for key, value in (headers or {}).items()
            }
            return (
                normalized_headers.get("x-event-id")
                or normalized_headers.get("event-id")
                or str((payload or {}).get("event_id") or "")
                or hashlib.sha256(raw_body).hexdigest()
            )
        return hashlib.sha256(raw_body).hexdigest()


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
