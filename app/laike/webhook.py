from __future__ import annotations

import inspect
import json
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.health import require_loopback
from app.api.responses import failure, success
from app.laike.contracts import SyncResult, WebhookVerification


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
        if not settings.laike_webhook_secret:
            return failure(
                "laike webhook secret is not configured",
                status_code=503,
            )

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
        verification = await _maybe_await(
            request.app.state.laike_client.verify_webhook(headers, raw_body)
        )
        if not isinstance(verification, WebhookVerification):
            verification = WebhookVerification.model_validate(verification)
        if not verification.verified:
            return failure(
                verification.reason or "invalid webhook signature",
            )

        service = request.app.state.laike_service_factory()
        result = await _maybe_await(service.receive_webhook(headers, raw_body))
        if not isinstance(result, SyncResult):
            result = SyncResult.model_validate(result)
        if not result.success:
            return failure(
                "laike webhook enqueue failed",
                status_code=503,
                data=result.model_dump(),
            )
        return success(result.model_dump())

    return router

