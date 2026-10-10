"""组织子实体（账号/客服分类/客服组/客服组成员）CRUD 测试。

补齐 organization 模块中 department/staff 之外的子实体覆盖。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.organization import Department, Staff
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def org_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'org2.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                Department(name="直播部", dept_type="live", ordid=1),
                Staff(name="客服甲", nickname="甲", role="custom_staff"),
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


# ---------- 账号 CRUD ----------

@pytest.mark.asyncio
async def test_account_full_crud(org_app):
    # add
    resp = await post(
        org_app,
        "/apiv1/user/accounts/add",
        headers=DEMO_HEADERS,
        json={"username": "laike_001", "password": "secret123", "account_name": "来客账号"},
    )
    assert resp.status_code == 200
    acc_id = resp.json()["data"]["id"]

    # 重复账号被拒
    resp = await post(
        org_app,
        "/apiv1/user/accounts/add",
        headers=DEMO_HEADERS,
        json={"username": "laike_001", "password": "secret123"},
    )
    assert resp.status_code == 400

    # index
    resp = await post(org_app, "/apiv1/user/accounts/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 1

    # edit
    resp = await post(
        org_app,
        "/apiv1/user/accounts/edit",
        headers=DEMO_HEADERS,
        json={"id": acc_id, "account_name": "来客账号改"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["account_name"] == "来客账号改"

    # del
    resp = await post(org_app, "/apiv1/user/accounts/del", headers=DEMO_HEADERS, json={"id": acc_id})
    assert resp.status_code == 200

    resp = await post(org_app, "/apiv1/user/accounts/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_account_add_requires_username_password(org_app):
    resp = await post(org_app, "/apiv1/user/accounts/add", headers=DEMO_HEADERS, json={"username": "x"})
    assert resp.status_code == 400


# ---------- 客服分类 CRUD ----------

@pytest.mark.asyncio
async def test_cate_full_crud(org_app):
    resp = await post(org_app, "/apiv1/user/customservicecates/add", headers=DEMO_HEADERS, json={"name": "售前"})
    assert resp.status_code == 200
    cate_id = resp.json()["data"]["id"]

    resp = await post(org_app, "/apiv1/user/customservicecates/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 1

    resp = await post(org_app, "/apiv1/user/customservicecates/edit", headers=DEMO_HEADERS, json={"id": cate_id, "name": "售前改"})
    assert resp.json()["data"]["name"] == "售前改"

    resp = await post(org_app, "/apiv1/user/customservicecates/del", headers=DEMO_HEADERS, json={"id": cate_id})
    assert resp.status_code == 200


# ---------- 客服组 CRUD ----------

@pytest.mark.asyncio
async def test_group_full_crud(org_app):
    resp = await post(
        org_app,
        "/apiv1/user/customservicegroups/add",
        headers=DEMO_HEADERS,
        json={"name": "客服一组", "department_id": 1},
    )
    assert resp.status_code == 200
    group_id = resp.json()["data"]["id"]

    resp = await post(org_app, "/apiv1/user/customservicegroups/index", headers=DEMO_HEADERS, json={})
    assert resp.json()["data"]["total"] == 1

    resp = await post(org_app, "/apiv1/user/customservicegroups/edit", headers=DEMO_HEADERS, json={"id": group_id, "name": "客服一组改"})
    assert resp.json()["data"]["name"] == "客服一组改"

    resp = await post(org_app, "/apiv1/user/customservicegroups/del", headers=DEMO_HEADERS, json={"id": group_id})
    assert resp.status_code == 200


# ---------- 客服组成员 CRUD ----------

@pytest.mark.asyncio
async def test_member_full_crud(org_app):
    # 先建组
    resp = await post(org_app, "/apiv1/user/customservicegroups/add", headers=DEMO_HEADERS, json={"name": "组"})
    group_id = resp.json()["data"]["id"]

    # add member
    resp = await post(
        org_app,
        "/apiv1/user/customservicegroupmembers/add",
        headers=DEMO_HEADERS,
        json={"group_id": group_id, "staff_id": 1, "rate": 5},
    )
    assert resp.status_code == 200
    member_id = resp.json()["data"]["id"]

    resp = await post(
        org_app,
        "/apiv1/user/customservicegroupmembers/index",
        headers=DEMO_HEADERS,
        json={"group_id": group_id},
    )
    assert resp.json()["data"]["total"] == 1

    resp = await post(org_app, "/apiv1/user/customservicegroupmembers/del", headers=DEMO_HEADERS, json={"id": member_id})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_member_add_requires_group_and_staff(org_app):
    resp = await post(org_app, "/apiv1/user/customservicegroupmembers/add", headers=DEMO_HEADERS, json={"group_id": 1})
    assert resp.status_code == 400
