from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping

import httpx

from .contracts import LaikeClient, LaikePage, WebhookVerification
from .webhook import WebhookVerifier


class LaikeClientError(RuntimeError):
    """Raised when a provider response cannot be consumed safely."""


class LaikeConfigurationError(LaikeClientError):
    """Raised when the adapter lacks an explicitly configured dependency."""


class HttpLaikeClient:
    def __init__(
        self,
        base_url: str,
        orders_path: str,
        access_token: str | None,
        http_client: httpx.AsyncClient | None = None,
        webhook_verifier: WebhookVerifier | None = None,
        *,
        verifier: WebhookVerifier | None = None,
        items_key: str = "items",
        cursor_key: str = "next_cursor",
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise LaikeConfigurationError("laike base_url is not configured")
        if not isinstance(orders_path, str) or not orders_path.strip():
            raise LaikeConfigurationError("laike orders_path is not configured")
        if not isinstance(access_token, str) or not access_token.strip():
            raise LaikeConfigurationError("laike access_token is not configured")
        if not isinstance(items_key, str) or not items_key:
            raise LaikeConfigurationError("laike items_key is not configured")
        if not isinstance(cursor_key, str) or not cursor_key:
            raise LaikeConfigurationError("laike cursor_key is not configured")

        self.base_url = base_url
        self.orders_path = orders_path
        self.access_token = access_token
        self.items_key = items_key
        self.cursor_key = cursor_key
        self.http_client = (
            http_client if http_client is not None else httpx.AsyncClient()
        )
        self.webhook_verifier = (
            webhook_verifier if webhook_verifier is not None else verifier
        )

    @property
    def orders_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.orders_path.lstrip('/')}"

    async def fetch_orders(
        self,
        account_id: str,
        cursor: str | None,
        start_time: str | None,
        end_time: str | None,
    ) -> LaikePage:
        params = {
            key: value
            for key, value in {
                "account_id": account_id,
                "cursor": cursor,
                "start_time": start_time,
                "end_time": end_time,
            }.items()
            if value is not None
        }
        response = await self.http_client.get(
            self.orders_url,
            params=params,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        if not 200 <= response.status_code < 300:
            raise LaikeClientError(
                f"laike request failed with status {response.status_code}"
            )

        try:
            payload = response.json()
        except (TypeError, ValueError):
            raise LaikeClientError("laike response is not valid JSON") from None
        if not isinstance(payload, Mapping):
            raise LaikeClientError("laike response JSON must be an object")

        if self.items_key not in payload:
            raise LaikeClientError("laike response is missing configured items")
        items = payload[self.items_key]
        if not isinstance(items, list) or any(
            not isinstance(item, Mapping) for item in items
        ):
            raise LaikeClientError("laike response configured items must be a list")

        next_cursor = payload.get(self.cursor_key)
        if next_cursor is not None and not isinstance(next_cursor, str):
            raise LaikeClientError(
                "laike response configured cursor must be a string"
            )

        return LaikePage(
            items=items,
            next_cursor=next_cursor,
            raw=payload,
        )

    async def verify_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        if self.webhook_verifier is None:
            return WebhookVerification(
                valid=False,
                event_id=None,
                source="laike",
                reason="webhook verifier is not configured",
            )
        return self.webhook_verifier.verify(headers, raw_body)


class HmacLaikeClient:
    """Default boundary client for signature verification without provider calls."""

    _COMPATIBILITY_SIGNATURE_HEADERS = (
        "x-laike-signature",
        "x-webhook-signature",
        "x-signature",
        "signature",
    )

    def __init__(self, secret: str | None) -> None:
        self.secret = secret

    def verify_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        if not self.secret:
            return WebhookVerification(
                verified=False,
                reason="laike webhook secret is not configured",
            )

        normalized_headers = {
            key.lower().replace("_", "-"): value for key, value in headers.items()
        }
        signature = next(
            (
                normalized_headers[name].strip()
                for name in self._COMPATIBILITY_SIGNATURE_HEADERS
                if normalized_headers.get(name)
            ),
            None,
        )
        if not signature:
            return WebhookVerification(
                verified=False,
                reason="missing webhook signature",
            )

        if signature.lower().startswith("sha256="):
            signature = signature[7:]
        expected = hmac.new(
            self.secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return WebhookVerification(
                verified=False,
                reason="invalid webhook signature",
            )
        return WebhookVerification(verified=True)

    def fetch_orders(
        self,
        account_id: str,
        cursor: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> LaikePage:
        raise RuntimeError("laike order client is not configured")
