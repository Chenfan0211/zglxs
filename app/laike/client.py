from __future__ import annotations

import hashlib
import hmac
from collections.abc import Awaitable, Mapping
from typing import Protocol, runtime_checkable

from .contracts import LaikePage, WebhookVerification


@runtime_checkable
class LaikeClient(Protocol):
    def fetch_orders(
        self,
        account_id: str,
        cursor: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> LaikePage | Awaitable[LaikePage]:
        ...

    def verify_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification | Awaitable[WebhookVerification]:
        ...


class HmacLaikeClient:
    """Default boundary client for signature verification without provider calls."""

    # Compatibility placeholders only; confirm the real provider contract first.
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
