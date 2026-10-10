"""组织模块完整 CRUD 行为测试。

覆盖部门（Department）与员工（Staff）的增删改查：
- 列表/搜索/分页 COUNT
- 新增（含必填校验）
- 编辑（字段更新、404）
- 删除（404、级联后的列表数量变化）
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
    database_url = f"sqlite+pysqlite:///{tmp_path / 'org.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                Department(name="直播部", dept_type="live", ordid=1),
                Department(name="转化部", dept_type="custom", ordid=2),
                Staff(name="张三", nickname="主播张三", mobile="13800000001", department_id=1, role="live_staff"),
                Staff(name="李四", nickname="客服李四", mobile="13800000002", department_id=2, role="custom_staff"),
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


# ---------- 部门 CRUD ----------

@pytest.mark.asyncio
async def test_department_full_crud_cycle(org_app):
    # 1. add
    resp = await post(
        org_app,
        "/apiv1/user/departments/add",
        headers=DEMO_HEADERS,
        json={"department_name": "售后部", "type": "maintenance", "ordid": 3},
    )
    assert resp.status_code == 200
    added = resp.json()["data"]
    dept_id = added["id"]
    assert added["name"] == "售后部"
    assert added["dept_type"] == "maintenance"

    # 2. edit
    resp = await post(
        org_app,
        "/apiv1/user/departments/edit",
        headers=DEMO_HEADERS,
        json={"id": dept_id, "department_name": "售后一部", "ordid": 33},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "售后一部"
    assert resp.json()["data"]["ordid"] == 33

    # 3. 列表可见编辑结果
    resp = await post(
        org_app,
        "/apiv1/user/departments/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert resp.json()["data"]["total"] == 3
    names = {r["department_name"] for r in resp.json()["data"]["list"]}
    assert "售后一部" in names

    # 4. del
    resp = await post(
        org_app,
        "/apiv1/user/departments/del",
        headers=DEMO_HEADERS,
        json={"id": dept_id},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 1

    # 5. 删除后总数回落
    resp = await post(
        org_app,
        "/apiv1/user/departments/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert resp.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_department_edit_missing_id(org_app):
    resp = await post(org_app, "/apiv1/user/departments/edit", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_department_edit_not_found(org_app):
    resp = await post(
        org_app,
        "/apiv1/user/departments/edit",
        headers=DEMO_HEADERS,
        json={"id": 99999, "department_name": "不存在"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_department_del_not_found(org_app):
    resp = await post(org_app, "/apiv1/user/departments/del", headers=DEMO_HEADERS, json={"id": 99999})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_department_search(org_app):
    resp = await post(
        org_app,
        "/apiv1/user/departments/searchdepartment",
        headers=DEMO_HEADERS,
        json={"keyword": "直播"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]["list"]
    assert len(body) == 1
    assert body[0]["department_name"] == "直播部"


# ---------- 员工 CRUD ----------

@pytest.mark.asyncio
async def test_staff_full_crud_cycle(org_app):
    # 1. add
    resp = await post(
        org_app,
        "/apiv1/user/staff/add",
        headers=DEMO_HEADERS,
        json={"name": "王五", "nickname": "中控王五", "mobile": "13800000003", "department_id": 1, "role": "console_staff"},
    )
    assert resp.status_code == 200
    staff_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["name"] == "王五"

    # 2. edit
    resp = await post(
        org_app,
        "/apiv1/user/staff/edit",
        headers=DEMO_HEADERS,
        json={"id": staff_id, "nickname": "王五改", "role": "console_staff"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["nickname"] == "王五改"

    # 3. 列表可见
    resp = await post(
        org_app,
        "/apiv1/user/staff/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert resp.json()["data"]["total"] == 3

    # 4. del
    resp = await post(org_app, "/apiv1/user/staff/del", headers=DEMO_HEADERS, json={"id": staff_id})
    assert resp.status_code == 200

    resp = await post(
        org_app,
        "/apiv1/user/staff/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert resp.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_staff_add_requires_name(org_app):
    resp = await post(org_app, "/apiv1/user/staff/add", headers=DEMO_HEADERS, json={"mobile": "13800000009"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_staff_index_filters_by_department(org_app):
    resp = await post(
        org_app,
        "/apiv1/user/staff/index",
        headers=DEMO_HEADERS,
        json={"department_id": 1},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["list"][0]["name"] == "张三"
    assert body["list"][0]["department_name"] == "直播部"


@pytest.mark.asyncio
async def test_staff_edit_not_found(org_app):
    resp = await post(org_app, "/apiv1/user/staff/edit", headers=DEMO_HEADERS, json={"id": 99999, "name": "x"})
    assert resp.status_code == 404
