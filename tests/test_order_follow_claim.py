"""订单跟进（follow）与认领（claim）链路测试。

覆盖：
- 跟进更新（follow_update）创建/更新 OrderFollow 并写 OrderFollowLog
- 认领（claim）创建 OrderClaim
- 跟进日志 / 认领日志查询
- 跟单状态管理（FollowStatus CRUD）
- 批量分配（batchallocation）
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder
from app.db.models.order import FollowStatus
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def order_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'order.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                LaikeOrder(
                    provider_order_id="DEMO-ORDER-001",
                    account_id="DEMO-ACCOUNT-001",
                    order_status=3,
                    pay_amount_fen=9900,
                    create_order_time=1789257600,
                    update_order_time=1789257660,
                    status="3",
                    payload_json={"order_id": "DEMO-ORDER-001"},
                ),
                LaikeOrder(
                    provider_order_id="DEMO-ORDER-002",
                    account_id="DEMO-ACCOUNT-002",
                    order_status=1,
                    pay_amount_fen=1200,
                    create_order_time=1789257600,
                    update_order_time=1789257600,
                    status="1",
                    payload_json={"order_id": "DEMO-ORDER-002"},
                ),
                FollowStatus(name="已跟进", sort_order=1),
                FollowStatus(name="待跟进", sort_order=2),
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


# ---------- 跟进链路 ----------

@pytest.mark.asyncio
async def test_follow_update_creates_and_updates(order_app):
    # 首次跟进：创建 OrderFollow
    resp = await post(
        order_app,
        "/apiv1/user/order/updatefollowstatus",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001", "follow_status": "followed", "owner_staff_id": 5, "memo": "已联系客户", "staff_id": 5},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["follow_status"] == "followed"
    assert body["owner_staff_id"] == 5
    assert body["memo"] == "已联系客户"

    # 再次跟进：更新同一 OrderFollow
    resp = await post(
        order_app,
        "/apiv1/user/order/updatefollowstatus",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001", "follow_status": "done", "memo": "成交"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["follow_status"] == "done"

    # 跟进日志应记录两条
    resp = await post(
        order_app,
        "/apiv1/user/order/followlog",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001"},
    )
    assert resp.status_code == 200
    logs = resp.json()["data"]
    assert logs["total"] == 2


@pytest.mark.asyncio
async def test_follow_update_requires_order_id(order_app):
    resp = await post(order_app, "/apiv1/user/order/updatefollowstatus", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_addfollow_updates_memo(order_app):
    resp = await post(
        order_app,
        "/apiv1/user/order/addfollow",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-002", "memo": "备注信息"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["memo"] == "备注信息"


# ---------- 认领链路 ----------

@pytest.mark.asyncio
async def test_claim_creates_record_and_log(order_app):
    # 认领
    resp = await post(
        order_app,
        "/apiv1/user/order/claim",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001", "staff_id": 7},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["provider_order_id"] == "DEMO-ORDER-001"
    assert body["staff_id"] == 7

    # 认领日志
    resp = await post(
        order_app,
        "/apiv1/user/order/claimlog",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001"},
    )
    assert resp.status_code == 200
    logs = resp.json()["data"]
    assert logs["total"] == 1
    assert logs["list"][0]["staff_id"] == 7


@pytest.mark.asyncio
async def test_claim_requires_order_id(order_app):
    resp = await post(order_app, "/apiv1/user/order/claim", headers=DEMO_HEADERS, json={"staff_id": 1})
    assert resp.status_code == 400


# ---------- 批量分配 ----------

@pytest.mark.asyncio
async def test_batchallocation_updates_owner(order_app):
    resp = await post(
        order_app,
        "/apiv1/user/order/batchallocation",
        headers=DEMO_HEADERS,
        json={"order_ids": ["DEMO-ORDER-001", "DEMO-ORDER-002"], "staff_id": 9},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 2


@pytest.mark.asyncio
async def test_batchallocation_requires_order_ids(order_app):
    resp = await post(order_app, "/apiv1/user/order/batchallocation", headers=DEMO_HEADERS, json={"staff_id": 9})
    assert resp.status_code == 400


# ---------- 跟单状态 CRUD ----------

@pytest.mark.asyncio
async def test_follow_status_full_crud(order_app):
    # index
    resp = await post(order_app, "/apiv1/user/followstatus/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 2

    # add
    resp = await post(
        order_app,
        "/apiv1/user/followstatus/add",
        headers=DEMO_HEADERS,
        json={"name": "已成交", "sort_order": 3},
    )
    assert resp.status_code == 200
    sid = resp.json()["data"]["id"]

    # edit
    resp = await post(
        order_app,
        "/apiv1/user/followstatus/edit",
        headers=DEMO_HEADERS,
        json={"id": sid, "name": "已成交(改)"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "已成交(改)"

    # del
    resp = await post(order_app, "/apiv1/user/followstatus/del", headers=DEMO_HEADERS, json={"id": sid})
    assert resp.status_code == 200

    resp = await post(order_app, "/apiv1/user/followstatus/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_follow_status_add_requires_name(order_app):
    resp = await post(order_app, "/apiv1/user/followstatus/add", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 400

# ---------- 订单字段写操作（order_field_update 包装） ----------

@pytest.mark.asyncio
async def test_order_updatememo(order_app):
    resp = await post(
        order_app,
        "/apiv1/user/order/updatememo",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001", "memo": "新备注"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["memo"] == "新备注"


@pytest.mark.asyncio
async def test_order_updatetel(order_app):
    resp = await post(
        order_app,
        "/apiv1/user/order/updatetel",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001", "tel": "13800000000"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["tel"] == "13800000000"


@pytest.mark.asyncio
async def test_order_setfollowday(order_app):
    resp = await post(
        order_app,
        "/apiv1/user/order/setfollowday",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001", "follow_day": 7},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["follow_day"] == 7


@pytest.mark.asyncio
async def test_order_release_unlocks(order_app):
    resp = await post(
        order_app,
        "/apiv1/user/order/release",
        headers=DEMO_HEADERS,
        json={"order_id": "DEMO-ORDER-001", "lock_flag": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["lock_flag"] is False


@pytest.mark.asyncio
async def test_order_field_update_requires_order_id(order_app):
    resp = await post(order_app, "/apiv1/user/order/updatememo", headers=DEMO_HEADERS, json={"memo": "x"})
    assert resp.status_code == 400
