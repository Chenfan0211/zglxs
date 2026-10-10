from __future__ import annotations

from datetime import datetime, timezone
import json

import httpx
import pytest

from app.laike.client import (
    ClientTokenProvider,
    DouyinLaikeClient,
    LaikeConfigurationError,
)
from app.laike.provider_errors import LaikeProviderError


def _json_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_client_token_is_cached_until_expiry():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "data": {
                    "access_token": "DEMO-TOKEN-001",
                    "expires_in": 7200,
                },
                "message": "success",
            },
        )

    provider = ClientTokenProvider(
        client_key="DEMO-APP-001",
        client_secret="DEMO-SECRET-001",
        http_client=_json_client(handler),
        base_url="https://open.douyin.com",
    )

    assert await provider.get_access_token() == "DEMO-TOKEN-001"
    assert await provider.get_access_token() == "DEMO-TOKEN-001"
    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert calls[0].url.path == "/oauth/client_token/"
    assert json.loads(calls[0].content) == {
        "client_key": "DEMO-APP-001",
        "client_secret": "DEMO-SECRET-001",
        "grant_type": "client_credential",
    }


@pytest.mark.asyncio
async def test_order_query_uses_official_request_shape_and_cursor():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "extra": {"error_code": 0, "description": ""},
                "data": {
                    "orders": [
                        {
                            "order_id": "DEMO-LAIKE-ORDER-001",
                            "order_status": 200,
                            "pay_amount": 9900,
                        }
                    ],
                    "search_after": {"CursorValue": ["cursor-a", "cursor-b"]},
                },
            },
        )

    token_provider = ClientTokenProvider(
        client_key="DEMO-APP-001",
        client_secret="DEMO-SECRET-001",
        http_client=_json_client(
            lambda request: httpx.Response(
                200,
                json={
                    "data": {"access_token": "DEMO-TOKEN-001", "expires_in": 7200},
                    "message": "success",
                },
            )
        ),
        base_url="https://open.douyin.com",
    )
    client = DouyinLaikeClient(
        token_provider=token_provider,
        http_client=_json_client(handler),
        base_url="https://open.douyin.com",
        page_size=100,
        rpc_transit_life_account="DEMO-LAIKE-ACCOUNT-001",
    )

    page = await client.fetch_orders(
        "DEMO-LAIKE-ACCOUNT-001",
        cursor="cursor-a,cursor-b",
        start_time="2026-09-13T00:00:00Z",
        end_time="2026-09-13T23:59:59Z",
    )

    request = calls[0]
    assert request.method == "GET"
    assert request.url == httpx.URL(
        "https://open.douyin.com/goodlife/v1/trade/order/query/"
        "?account_id=DEMO-LAIKE-ACCOUNT-001&page_num=1&page_size=100"
        "&cursor=cursor-a%2Ccursor-b"
        "&create_order_start_time=1789257600"
        "&create_order_end_time=1789343999"
        "&update_order_start_time=1789257600"
        "&update_order_end_time=1789343999"
    )
    assert request.headers["access-token"] == "DEMO-TOKEN-001"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["rpc-transit-life-account"] == "DEMO-LAIKE-ACCOUNT-001"
    assert page.items[0]["order_id"] == "DEMO-LAIKE-ORDER-001"
    assert page.next_cursor == "cursor-a,cursor-b"
    assert page.has_more is False


@pytest.mark.asyncio
async def test_business_error_in_http_200_is_classified_as_provider_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "extra": {
                    "error_code": 2119003,
                    "description": "请求太过频繁，请稍后再试",
                },
                "data": {},
            },
        )

    token_provider = ClientTokenProvider(
        client_key="DEMO-APP-001",
        client_secret="DEMO-SECRET-001",
        http_client=_json_client(
            lambda request: httpx.Response(
                200,
                json={
                    "data": {"access_token": "DEMO-TOKEN-001", "expires_in": 7200},
                    "message": "success",
                },
            )
        ),
        base_url="https://open.douyin.com",
    )
    client = DouyinLaikeClient(
        token_provider=token_provider,
        http_client=_json_client(handler),
        base_url="https://open.douyin.com",
    )

    with pytest.raises(LaikeProviderError) as error:
        await client.fetch_orders("DEMO-LAIKE-ACCOUNT-001", None, None, None)

    assert error.value.code == 2119003
    assert error.value.retryable is True
    assert "请求太过频繁" in str(error.value)


@pytest.mark.asyncio
async def test_order_query_requires_official_extra_error_code():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"orders": []}})

    provider = ClientTokenProvider(
        "DEMO-APP-001",
        "DEMO-SECRET-001",
        http_client=_json_client(
            lambda request: httpx.Response(
                200,
                json={
                    "data": {"access_token": "DEMO-TOKEN-001", "expires_in": 7200}
                },
            )
        ),
    )
    client = DouyinLaikeClient(
        provider,
        http_client=_json_client(handler),
    )

    with pytest.raises(LaikeProviderError, match="extra is invalid"):
        await client.fetch_orders("DEMO-LAIKE-ACCOUNT-001", None, None, None)


def test_client_rejects_empty_credentials_before_network():
    with pytest.raises(LaikeConfigurationError):
        ClientTokenProvider(
            client_key="",
            client_secret="DEMO-SECRET-001",
            http_client=_json_client(lambda request: httpx.Response(500)),
            base_url="https://open.douyin.com",
        )


def test_settings_expose_official_polling_defaults():
    from app.core.settings import Settings

    settings = Settings()

    assert settings.laike_base_url == "https://open.douyin.com"
    assert settings.laike_orders_path == "/goodlife/v1/trade/order/query/"
    assert settings.laike_page_size == 100
    assert settings.laike_initial_lookback_seconds == 86400
    assert settings.laike_poll_interval_seconds == 300
