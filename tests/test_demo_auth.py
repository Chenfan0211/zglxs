import base64
import json
from urllib.parse import urlencode

import httpx
import pytest

from app.core.settings import Settings
from app.main import create_app


def demo_settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "environment": "test",
        "database_url": None,
        "demo_login_enabled": True,
        "demo_login_username": "13800000000",
        "demo_login_password": "Demo@12345",
        "demo_captcha_code": "1111",
        "demo_captcha_key": "DEMO-CAPTCHA",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def request(
    app,
    path: str,
    method: str = "GET",
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            content=content,
            headers=headers,
        )


@pytest.mark.asyncio
async def test_demo_captcha_returns_a_visible_legacy_payload():
    response = await request(
        create_app(demo_settings()),
        "/apiv1/common/captcha",
        method="POST",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 1
    assert payload["msg"] == "success"
    assert payload["data"]["key"] == "DEMO-CAPTCHA"
    assert payload["data"]["content"].startswith("data:image/svg+xml;base64,")

    encoded = payload["data"]["content"].split(",", 1)[1]
    assert b"1111" in base64.b64decode(encoded)


@pytest.mark.asyncio
async def test_demo_login_accepts_the_legacy_form_payload_and_sets_cookie():
    body = urlencode(
        {
            "mobile": "13800000000",
            "password": "Demo@12345",
            "captcha": "1111",
            "captcha_key": "DEMO-CAPTCHA",
        }
    ).encode()

    response = await request(
        create_app(demo_settings()),
        "/apiv1/user/user/login",
        method="POST",
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 1
    assert payload["data"]["token"].startswith("DEMO-")
    assert response.cookies["access_token"]

    auth_info = json.loads(payload["data"]["auth_info"])
    assert auth_info["group_id"] == 1
    assert auth_info["nickname"] == "测试管理员"


@pytest.mark.asyncio
async def test_demo_login_returns_a_non_empty_legacy_error_message():
    body = urlencode(
        {
            "mobile": "13800000000",
            "password": "wrong",
            "captcha": "1111",
            "captcha_key": "DEMO-CAPTCHA",
        }
    ).encode()

    response = await request(
        create_app(demo_settings()),
        "/apiv1/user/user/login",
        method="POST",
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "msg": "测试账号或密码错误",
        "data": None,
    }


@pytest.mark.asyncio
async def test_demo_logout_clears_the_test_session_cookie():
    app = create_app(demo_settings())
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        login_response = await client.post(
            "/apiv1/user/user/login",
            content=urlencode(
                {
                    "mobile": "13800000000",
                    "password": "Demo@12345",
                    "captcha": "1111",
                    "captcha_key": "DEMO-CAPTCHA",
                }
            ).encode(),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert login_response.status_code == 200
        assert client.cookies.get("access_token")

        logout_response = await client.post("/apiv1/user/user/logout")

        assert logout_response.status_code == 200
        assert logout_response.json() == {
            "code": 1,
            "msg": "success",
            "data": {},
        }
        assert client.cookies.get("access_token") is None


@pytest.mark.asyncio
async def test_demo_auth_supports_distinct_top_level_legacy_paths():
    app = create_app(demo_settings())
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    body = urlencode(
        {
            "mobile": "13800000000",
            "password": "Demo@12345",
            "captcha": "1111",
            "captcha_key": "DEMO-CAPTCHA",
        }
    ).encode()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login_response = await client.post(
            "/apiv1/user/login",
            content=body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        logout_response = await client.post("/apiv1/user/logout")

    assert login_response.status_code == 200
    assert login_response.json()["data"]["token"].startswith("DEMO-")
    assert logout_response.json() == {"code": 1, "msg": "success", "data": {}}


@pytest.mark.asyncio
async def test_demo_auth_is_disabled_by_default_and_has_a_visible_message():
    response = await request(
        create_app(demo_settings(demo_login_enabled=False)),
        "/apiv1/common/captcha",
        method="POST",
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "msg": "测试登录未启用",
        "data": None,
    }
