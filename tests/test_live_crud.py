"""直播模块完整 CRUD 行为测试。

覆盖直播间（LiveRoom）与主播成员（LiveRoomMember）的增删改查。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.live import LiveRoom
from app.db.models.organization import Department, Staff
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def live_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'live.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                Department(name="直播部", dept_type="live", ordid=1),
                Staff(name="主播甲", nickname="甲", department_id=1, role="anchor"),
                Staff(name="主播乙", nickname="乙", department_id=1, role="anchor"),
                LiveRoom(name="直播间A", department_id=1, ordid=1),
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


# ---------- 直播间 CRUD ----------

@pytest.mark.asyncio
async def test_live_room_full_crud_cycle(live_app):
    # add
    resp = await post(
        live_app,
        "/apiv1/user/liverooms/add",
        headers=DEMO_HEADERS,
        json={"name": "直播间B", "department_id": 1, "room_id": "ROOM-B", "ordid": 2},
    )
    assert resp.status_code == 200
    room_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["name"] == "直播间B"

    # edit
    resp = await post(
        live_app,
        "/apiv1/user/liverooms/edit",
        headers=DEMO_HEADERS,
        json={"id": room_id, "name": "直播间B改", "ordid": 22},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "直播间B改"
    assert resp.json()["data"]["ordid"] == 22

    # index 可见
    resp = await post(live_app, "/apiv1/user/liverooms/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 2

    # del
    resp = await post(live_app, "/apiv1/user/liverooms/del", headers=DEMO_HEADERS, json={"id": room_id})
    assert resp.status_code == 200

    resp = await post(live_app, "/apiv1/user/liverooms/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_live_room_add_requires_name(live_app):
    resp = await post(live_app, "/apiv1/user/liverooms/add", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_live_room_edit_not_found(live_app):
    resp = await post(live_app, "/apiv1/user/liverooms/edit", headers=DEMO_HEADERS, json={"id": 99999, "name": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_live_room_del_not_found(live_app):
    resp = await post(live_app, "/apiv1/user/liverooms/del", headers=DEMO_HEADERS, json={"id": 99999})
    assert resp.status_code == 404


# ---------- 主播成员 CRUD ----------

@pytest.mark.asyncio
async def test_live_room_member_full_crud_cycle(live_app):
    # 先获取直播间 id（fixture 里第一个 LiveRoom 的 id 为 1）
    # add
    resp = await post(
        live_app,
        "/apiv1/user/liveroommembers/add",
        headers=DEMO_HEADERS,
        json={"live_room_id": 1, "staff_id": 1, "role": "anchor"},
    )
    assert resp.status_code == 200
    member_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["staff_id"] == 1

    # edit
    resp = await post(
        live_app,
        "/apiv1/user/liveroommembers/edit",
        headers=DEMO_HEADERS,
        json={"id": member_id, "role": "co-anchor"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "co-anchor"

    # index 按 live_room_id 过滤
    resp = await post(
        live_app,
        "/apiv1/user/liveroommembers/index",
        headers=DEMO_HEADERS,
        json={"live_room_id": 1},
    )
    assert resp.json()["data"]["total"] == 1

    # del
    resp = await post(live_app, "/apiv1/user/liveroommembers/del", headers=DEMO_HEADERS, json={"id": member_id})
    assert resp.status_code == 200

    resp = await post(
        live_app,
        "/apiv1/user/liveroommembers/index",
        headers=DEMO_HEADERS,
        json={"live_room_id": 1},
    )
    assert resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_member_add_requires_live_room_and_staff(live_app):
    resp = await post(live_app, "/apiv1/user/liveroommembers/add", headers=DEMO_HEADERS, json={"live_room_id": 1})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_member_edit_not_found(live_app):
    resp = await post(live_app, "/apiv1/user/liveroommembers/edit", headers=DEMO_HEADERS, json={"id": 99999})
    assert resp.status_code == 404
