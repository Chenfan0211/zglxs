"""中控工作台（console）模块测试。

demo_dashboard 此前完全无测试覆盖，本文件补齐工作台汇总、主播/中控搜索、
直播间/金额排名等核心只读接口。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder
from app.db.models.live import LiveRoom
from app.db.models.organization import Department, Staff
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def console_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'console.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                Department(name="直播部", dept_type="live", ordid=1),
                Department(name="客服部", dept_type="custom", ordid=2),
                Department(name="售后部", dept_type="maintenance", ordid=3),
                Staff(name="主播甲", nickname="甲", role="anchor"),
                Staff(name="中控乙", nickname="乙", role="console"),
                LiveRoom(name="直播间A", department_id=1, ordid=1),
                LaikeOrder(
                    provider_order_id="DEMO-C-001",
                    account_id="ACC-001",
                    order_status=3,
                    pay_amount_fen=10000,
                    create_order_time=1789257600,
                    update_order_time=1789257660,
                    status="3",
                    payload_json={"order_id": "DEMO-C-001"},
                ),
            ]
        )
        session.commit()
    return create_app(
        Settings(_env_file=None, database_url=None, laike_database_url=database_url)
    )


async def post(app, path, *, headers=None, json=None):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, headers=headers or {}, json=json or {})


@pytest.mark.asyncio
async def test_console_center_summary(console_app):
    resp = await post(console_app, "/apiv1/console/center", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["info"]["total_order_num"] == 1
    assert len(body["department_list"]) == 3
    assert len(body["custom_department_list"]) == 1  # 客服部
    assert len(body["maintenance_department_list"]) == 1  # 售后部


@pytest.mark.asyncio
async def test_console_search_anchors(console_app):
    resp = await post(console_app, "/apiv1/console/searchanchor", headers=DEMO_HEADERS, json={"keyword": "主播"})
    assert resp.status_code == 200
    body = resp.json()["data"]["list"]
    assert len(body) == 1
    assert body[0]["nickname"] == "甲"


@pytest.mark.asyncio
async def test_console_search_consoles(console_app):
    resp = await post(console_app, "/apiv1/console/searchconsole", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    body = resp.json()["data"]["list"]
    assert len(body) == 1
    assert body[0]["nickname"] == "乙"


@pytest.mark.asyncio
async def test_console_live_room_rank(console_app):
    resp = await post(console_app, "/apiv1/console/liveroomrank", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert isinstance(body["list"], list)


@pytest.mark.asyncio
async def test_console_order_money_rank(console_app):
    resp = await post(console_app, "/apiv1/console/ordermoneyrank", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert isinstance(body["list"], list)


@pytest.mark.asyncio
async def test_console_requires_session(console_app):
    resp = await post(console_app, "/apiv1/console/center")
    assert resp.status_code == 401
