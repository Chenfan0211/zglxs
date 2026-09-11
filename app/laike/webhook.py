from __future__ import annotations

import hashlib
import hmac
import inspect
import json
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.health import require_loopback
from app.api.responses import failure, success
from app.laike.contracts import SyncResult, WebhookVerification


class WebhookVerifier:
    def __init__(
        self,
        secret: str | None,
        signature_header: str = "X-Laike-Signature",
        event_id_header: str = "X-Laike-Event-Id",
        digest: str = "sha256",
        prefix: str = "sha256=",
    ) -> None:
        try:
            hashlib.new(digest)
        except (TypeError, ValueError):
            raise ValueError(f"unsupported digest: {digest}") from None

        self.secret = secret
        self.signature_header = signature_header
        self.event_id_header = event_id_header
        self.digest = digest
        self.prefix = prefix

    def verify(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        if not self.secret:
            return WebhookVerification(
                valid=False,
                event_id=None,
                source="laike",
                reason="webhook secret is not configured",
            )

        normalized_headers = {
            key.lower(): value for key, value in headers.items()
        }
        signature = normalized_headers.get(self.signature_header.lower())
        if not signature or not isinstance(signature, str):
            return WebhookVerification(
                valid=False,
                event_id=None,
                source="laike",
                reason="missing webhook signature",
            )

        signature = signature.strip()
        if not signature:
            return WebhookVerification(
                valid=False,
                event_id=None,
                source="laike",
                reason="missing webhook signature",
            )
        if self.prefix:
            if not signature.startswith(self.prefix):
                return WebhookVerification(
                    valid=False,
                    event_id=None,
                    source="laike",
                    reason="invalid webhook signature",
                )
            signature = signature[len(self.prefix) :]

        expected = hmac.new(
            self.secret.encode("utf-8"),
            raw_body,
            self.digest,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return WebhookVerification(
                valid=False,
                event_id=None,
                source="laike",
                reason="invalid webhook signature",
            )

        event_id = normalized_headers.get(self.event_id_header.lower()) or None
        return WebhookVerification(
            valid=True,
            event_id=event_id,
            source="laike",
        )

    verify_webhook = verify


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def create_laike_webhook_router() -> APIRouter:
    router = APIRouter()

    @router.post(
        "/internal/laike/webhook",
        dependencies=[Depends(require_loopback)],
    )
    async def receive_webhook(request: Request):
        settings = request.app.state.settings
        if not settings.laike_webhook_enabled:
            return failure("laike webhook is disabled", status_code=503)
        raw_body = await request.body()
        if not raw_body.strip():
            return failure("invalid webhook JSON")
        try:
            payload = json.loads(raw_body)
        except (TypeError, ValueError):
            return failure("invalid webhook JSON")
        if not isinstance(payload, dict):
            return failure("webhook JSON must be an object")

        headers = dict(request.headers)
        service = request.app.state.laike_service_factory()
        result = await _maybe_await(service.receive_webhook(headers, raw_body))
        if not isinstance(result, SyncResult):
            result = SyncResult.model_validate(result)
        if not result.success:
            reason_lower = (result.reason or "").lower()
            status_code = 400 if "signature" in reason_lower or "secret" in reason_lower else 503
            return failure(
                result.reason or "laike webhook enqueue failed",
                status_code=status_code,
            )
        return success(result.model_dump())

    return router

