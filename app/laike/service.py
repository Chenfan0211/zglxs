from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Mapping
from typing import Any

from app.db.session import UnitOfWork
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
        with UnitOfWork(self.session_factory) as unit:
            repository = LaikeRepository(unit.session)
            if repository.get_webhook_event(event_id) is not None:
                return SyncResult(success=True)
            event = repository.insert_webhook_event(
                event_id,
                payload,
                dict(headers),
                verification.verified,
            )

        if self.enqueuer is not None:
            await _maybe_await(self.enqueuer(event.event_id, event.payload_json))
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

        processed_count = 0
        failed_count = 0
        error_message: str | None = None
        page_success = True
        cursor = self._read_cursor(account_id)

        try:
            while True:
                page = await self._fetch_page(
                    account_id, start_time, end_time, cursor
                )
                page_processed, page_failed = await self._process_page(page)
                processed_count += page_processed
                failed_count += page_failed
                if page_failed:
                    page_success = False
                if page_success:
                    self._advance_cursor(account_id, page.next_cursor)
                if not page.has_more:
                    break
                cursor = page.next_cursor
        except Exception as exc:
            page_success = False
            error_message = str(exc)

        with UnitOfWork(self.session_factory) as unit:
            repository = LaikeRepository(unit.session)
            persisted_run = unit.session.get(type(run), run.id)
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

    async def _process_page(self, page: LaikePage) -> tuple[int, int]:
        processed_count = 0
        failed_count = 0
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
            except Exception:
                failed_count += 1
        return processed_count, failed_count

    def _read_cursor(self, account_id: str) -> str | None:
        with self.session_factory() as session:
            cursor = LaikeRepository(session).get_cursor(account_id)
            return cursor.cursor if cursor is not None else None

    def _advance_cursor(self, account_id: str, cursor: str | None) -> None:
        with UnitOfWork(self.session_factory) as unit:
            LaikeRepository(unit.session).advance_cursor(account_id, cursor)

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
