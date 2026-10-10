from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from .contracts import LaikeClient, LaikePage, WebhookVerification
from .provider_errors import LaikeProviderError
from .webhook import WebhookVerifier


class LaikeClientError(RuntimeError):
    """Raised when a provider response cannot be consumed safely."""


class LaikeConfigurationError(LaikeClientError):
    """Raised when the adapter lacks an explicitly configured dependency."""


class ClientTokenProvider:
    """Fetch and cache a Douyin client_token without persisting credentials."""

    def __init__(
        self,
        client_key: str,
        client_secret: str,
        *,
        base_url: str = "https://open.douyin.com",
        http_client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not isinstance(client_key, str) or not client_key.strip():
            raise LaikeConfigurationError("laike client_key is not configured")
        if not isinstance(client_secret, str) or not client_secret.strip():
            raise LaikeConfigurationError("laike client_secret is not configured")
        if not isinstance(base_url, str) or not base_url.strip():
            raise LaikeConfigurationError("laike base_url is not configured")
        if timeout <= 0:
            raise LaikeConfigurationError("laike timeout must be positive")

        self.client_key = client_key
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.AsyncClient(timeout=timeout)
        self.clock = clock or time.monotonic
        self._token: str | None = None
        self._expires_at = 0.0

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/oauth/client_token/"

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        now = self.clock()
        if not force_refresh and self._token and now < self._expires_at:
            return self._token

        try:
            response = await self.http_client.post(
                self.token_url,
                headers={"content-type": "application/json"},
                json={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credential",
                },
            )
        except httpx.HTTPError as exc:
            raise LaikeProviderError(
                "laike client token request failed",
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise LaikeProviderError(
                "laike client token request failed",
                retryable=response.status_code >= 500,
            )

        payload = _json_object(response, "laike client token response")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise LaikeProviderError("laike client token data is invalid")
        error_code = _error_code(data.get("error_code"))
        if error_code:
            raise LaikeProviderError(
                "laike client token request was rejected",
                code=error_code,
                retryable=False,
            )
        token = data.get("access_token")
        expires_in = data.get("expires_in")
        if not isinstance(token, str) or not token.strip():
            raise LaikeProviderError("laike client token is missing")
        if not isinstance(expires_in, int) or expires_in <= 0:
            raise LaikeProviderError("laike client token expiry is invalid")

        self._token = token
        self._expires_at = now + max(0, expires_in - 300)
        return token

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0


class DouyinLaikeClient:
    """Official read-only order query adapter for the local-life API."""

    _TOKEN_REFRESH_CODES = {2190002, 2190008}
    _RETRYABLE_CODES = {2119002, 2119003, 2100001, 2100004, 5000001}

    def __init__(
        self,
        token_provider: ClientTokenProvider,
        *,
        base_url: str = "https://open.douyin.com",
        orders_path: str = "/goodlife/v1/trade/order/query/",
        page_size: int = 100,
        timeout: float = 10.0,
        rpc_transit_life_account: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        webhook_verifier: WebhookVerifier | None = None,
    ) -> None:
        if not isinstance(orders_path, str) or not orders_path.strip():
            raise LaikeConfigurationError("laike orders_path is not configured")
        if not 1 <= page_size <= 100:
            raise LaikeConfigurationError("laike page_size must be between 1 and 100")
        if timeout <= 0:
            raise LaikeConfigurationError("laike timeout must be positive")
        self.token_provider = token_provider
        self.base_url = base_url.rstrip("/")
        self.orders_path = orders_path
        self.page_size = page_size
        self.timeout = timeout
        self.rpc_transit_life_account = rpc_transit_life_account
        self.http_client = http_client or httpx.AsyncClient(timeout=timeout)
        self.webhook_verifier = webhook_verifier

    @property
    def orders_url(self) -> str:
        return f"{self.base_url}/{self.orders_path.lstrip('/')}"

    async def fetch_orders(
        self,
        account_id: str,
        cursor: str | None,
        start_time: str | None,
        end_time: str | None,
    ) -> LaikePage:
        if not isinstance(account_id, str) or not account_id.strip():
            raise LaikeConfigurationError("laike account_id is not configured")
        if (start_time is None) != (end_time is None):
            raise ValueError("start_time and end_time must be provided together")

        params: dict[str, Any] = {
            "account_id": account_id,
            "page_num": 1,
            "page_size": self.page_size,
        }
        if cursor is not None:
            params["cursor"] = cursor
        if start_time is not None and end_time is not None:
            start_epoch = _epoch_seconds(start_time)
            end_epoch = _epoch_seconds(end_time)
            if start_epoch > end_epoch:
                raise ValueError("start_time must not be after end_time")
            params.update(
                {
                    "create_order_start_time": start_epoch,
                    "create_order_end_time": end_epoch,
                    "update_order_start_time": start_epoch,
                    "update_order_end_time": end_epoch,
                }
            )

        for attempt in range(2):
            token = await self.token_provider.get_access_token(
                force_refresh=attempt == 1
            )
            headers = {
                "access-token": token,
                "content-type": "application/json",
            }
            if self.rpc_transit_life_account:
                headers["Rpc-Transit-Life-Account"] = self.rpc_transit_life_account
            try:
                response = await self.http_client.get(
                    self.orders_url,
                    params=params,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                raise LaikeProviderError(
                    "laike order query request failed",
                    retryable=True,
                ) from exc
            payload = _json_object(response, "laike order query response")
            extra = payload.get("extra")
            if not isinstance(extra, Mapping) or "error_code" not in extra:
                raise LaikeProviderError("laike order query extra is invalid")
            error_code, description = _provider_error_details(payload)
            if error_code:
                if error_code in self._TOKEN_REFRESH_CODES and attempt == 0:
                    self.token_provider.invalidate()
                    continue
                raise LaikeProviderError(
                    description or "laike order query was rejected",
                    code=error_code,
                    retryable=error_code in self._RETRYABLE_CODES,
                )
            if response.status_code != 200:
                raise LaikeProviderError(
                    "laike order query request failed",
                    retryable=response.status_code >= 500,
                )
            return _parse_order_page(payload, page_size=self.page_size)

        raise LaikeProviderError("laike access token refresh failed")

    async def verify_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        if self.webhook_verifier is None:
            return WebhookVerification(
                valid=False,
                reason="webhook verifier is not configured",
            )
        return self.webhook_verifier.verify(headers, raw_body)


def _json_object(response: httpx.Response, name: str) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise LaikeProviderError(f"{name} is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise LaikeProviderError(f"{name} must be a JSON object")
    return payload


def _error_code(value: Any) -> int | None:
    if value in (None, 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _provider_error_details(payload: Mapping[str, Any]) -> tuple[int | None, str | None]:
    extra = payload.get("extra")
    if not isinstance(extra, Mapping):
        return None, None
    code = _error_code(extra.get("error_code"))
    description = extra.get("description")
    return code, description if isinstance(description, str) else None


def _parse_order_page(payload: Mapping[str, Any], *, page_size: int) -> LaikePage:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise LaikeProviderError("laike order query data is invalid")
    orders = data.get("orders")
    if not isinstance(orders, list) or any(
        not isinstance(order, Mapping) for order in orders
    ):
        raise LaikeProviderError("laike order query orders are invalid")

    next_cursor: str | None = None
    search_after = data.get("search_after")
    if isinstance(search_after, Mapping):
        cursor_values = search_after.get("CursorValue")
        if isinstance(cursor_values, list) and cursor_values:
            if any(value is None or isinstance(value, (dict, list)) for value in cursor_values):
                raise LaikeProviderError("laike order query cursor is invalid")
            next_cursor = ",".join(str(value) for value in cursor_values)

    return LaikePage(
        items=orders,
        next_cursor=next_cursor,
        raw=payload,
        has_more=bool(next_cursor) and len(orders) >= page_size,
    )


def _epoch_seconds(value: str) -> int:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must not be blank")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


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

    def __init__(
        self,
        secret: str | None,
        signature_header: str | None = None,
        event_id_header: str | None = None,
        digest: str = "sha256",
        prefix: str = "sha256=",
        verifier: WebhookVerifier | None = None,
    ) -> None:
        self.secret = secret
        self.verifier = verifier
        if self.verifier is None and (
            signature_header is not None or event_id_header is not None
        ):
            self.verifier = WebhookVerifier(
                secret,
                signature_header=signature_header or "X-Laike-Signature",
                event_id_header=event_id_header or "X-Laike-Event-Id",
                digest=digest,
                prefix=prefix,
            )

    async def verify_webhook(
        self,
        headers: Mapping[str, str],
        raw_body: bytes,
    ) -> WebhookVerification:
        if self.verifier is not None:
            return self.verifier.verify(headers, raw_body)
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

    async def fetch_orders(
        self,
        account_id: str,
        cursor: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> LaikePage:
        raise RuntimeError("laike order client is not configured")
