from __future__ import annotations

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
        "php_baseline_url": None,
        "demo_login_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def request(
    app,
    path: str,
    payload: dict | None = None,
    *,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            path,
            json=payload if content is None else None,
            content=content,
            headers=headers,
        )


@pytest.mark.asyncio
async def test_demo_dashboard_routes_return_frontend_compatible_payloads():
    app = create_app(demo_settings())

    center = await request(app, "/apiv1/console/center")
    assert center.status_code == 200
    center_payload = center.json()
    assert center_payload["code"] == 1
    assert center_payload["msg"] == "success"
    assert {
        "today_order_num",
        "yestoday_order_num",
        "current_month_order_num",
        "last_month_order_num",
        "today_order_money",
        "total_order_num",
        "last_month_use_rate",
    } <= center_payload["data"]["info"].keys()
    assert {
        "department_list",
        "custom_department_list",
        "maintenance_department_list",
    } <= center_payload["data"].keys()

    list_routes = (
        "searchanchorliveroom",
        "searchanchor",
        "searchgroup",
        "searchcustomliveroom",
        "searchcustom",
        "searchmaintenance",
        "searchconsole",
        "liveroomanchorlist",
    )
    for action in list_routes:
        response = await request(app, f"/apiv1/console/{action}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 1
        assert isinstance(payload["data"]["list"], list)
        assert all(
            str(value.get("id", value.get("order_id", ""))).startswith("DEMO-")
            for value in payload["data"]["list"]
            if isinstance(value, dict)
        )

    for action in ("liveroomrank", "ordermoneyrank", "orderusemoneyrank"):
        response = await request(app, f"/apiv1/console/{action}")
        rows = response.json()["data"]["list"]
        assert rows
        assert rows[0]["rank"] == 1
        assert rows[0]["total_money"].startswith("DEMO-")
        assert (
            rows[0].get("live_name", "").startswith("DEMO")
            or rows[0].get("nickname", "").startswith("DEMO")
        )

    for area_type in (1, 2):
        response = await request(
            app,
            "/apiv1/console/orderarea",
            {"type": area_type},
        )
        assert response.status_code == 200
        rows = response.json()["data"]["list"]
        assert rows
        assert {
            "rank",
            "name",
            "num",
            "rate",
        } <= rows[0].keys()
        assert rows[0]["name"].startswith("DEMO-")

    form_response = await request(
        app,
        "/apiv1/console/orderarea",
        content=urlencode({"type": 2}).encode(),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert form_response.status_code == 200
    assert form_response.json()["data"]["list"][0]["name"] == "DEMO-城市-A"

    notices = await request(app, "/apiv1/user/notices/index")
    notice_payload = notices.json()
    assert notice_payload["code"] == 1
    assert notice_payload["data"]["total"] == len(notice_payload["data"]["list"])
    assert isinstance(notice_payload["data"]["notice_type_list"], list)
    assert notice_payload["data"]["list"][0]["id"].startswith("DEMO-")

    for path in (
        "/apiv1/user/notices/changeview",
        "/apiv1/user/user/changenoticeflg",
    ):
        response = await request(app, path)
        assert response.status_code == 200
        assert response.json() == {"code": 1, "msg": "success", "data": {}}


@pytest.mark.asyncio
async def test_demo_dashboard_routes_do_not_return_fake_data_when_disabled():
    app = create_app(demo_settings(demo_login_enabled=False))

    response = await request(app, "/apiv1/console/center")

    assert response.status_code == 503
    assert response.json() == {
        "code": 0,
        "msg": "测试首页兼容接口未启用",
        "data": None,
    }

    order_area = await request(app, "/apiv1/console/orderarea", {"type": 1})
    assert order_area.status_code == 503
    assert order_area.json() == {
        "code": 0,
        "msg": "测试首页兼容接口未启用",
        "data": None,
    }
