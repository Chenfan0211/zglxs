"""系统模块完整 CRUD 行为测试。

覆盖系统配置（SystemConfig）读写、表格列设置（TableColumnSetting）增删改查、
版本信息读取。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.system_config import SystemConfig, TableColumnSetting
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def system_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'system.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                SystemConfig(config_key="web_name", config_value="抖音订单系统"),
                SystemConfig(config_key="upversion_num", config_value="12"),
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


# ---------- 系统配置 ----------

@pytest.mark.asyncio
async def test_get_config_info_reads_web_name(system_app):
    resp = await post(system_app, "/apiv1/common/getconfiginfo", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["web_name"] == "抖音订单系统"
    assert body["config"]["web_name"] == "抖音订单系统"


@pytest.mark.asyncio
async def test_update_config_info_upserts(system_app):
    # 更新已有 + 新增键
    resp = await post(
        system_app,
        "/apiv1/common/updateconfiginfo",
        headers=DEMO_HEADERS,
        json={"web_name": "新系统名", "logo": "http://logo.png"},
    )
    assert resp.status_code == 200
    assert set(resp.json()["data"]["updated"]) == {"web_name", "logo"}

    # 读取验证
    resp = await post(system_app, "/apiv1/common/getconfiginfo", headers=DEMO_HEADERS, json={})
    body = resp.json()["data"]
    assert body["web_name"] == "新系统名"
    assert body["config"]["logo"] == "http://logo.png"


@pytest.mark.asyncio
async def test_get_upversion_num(system_app):
    resp = await post(system_app, "/apiv1/common/getupversionnum", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["num"] == 12


@pytest.mark.asyncio
async def test_get_upversion_info_empty(system_app):
    resp = await post(system_app, "/apiv1/common/getupversioninfo", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["version"] is None


# ---------- 表格列设置 CRUD ----------

@pytest.mark.asyncio
async def test_table_column_full_crud_cycle(system_app):
    # detail 初始为空
    resp = await post(
        system_app,
        "/apiv1/user/usertablecolumns/detail",
        headers=DEMO_HEADERS,
        json={"table_key": "order_list"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["content"] == ""

    # edit（创建）
    resp = await post(
        system_app,
        "/apiv1/user/usertablecolumns/edit",
        headers=DEMO_HEADERS,
        json={"table_key": "order_list", "content": '["id","name"]'},
    )
    assert resp.status_code == 200

    # detail 可见
    resp = await post(
        system_app,
        "/apiv1/user/usertablecolumns/detail",
        headers=DEMO_HEADERS,
        json={"table_key": "order_list"},
    )
    assert resp.json()["data"]["content"] == '["id","name"]'

    # edit（更新）
    resp = await post(
        system_app,
        "/apiv1/user/usertablecolumns/edit",
        headers=DEMO_HEADERS,
        json={"table_key": "order_list", "content": '["id"]'},
    )
    assert resp.status_code == 200

    # del
    resp = await post(
        system_app,
        "/apiv1/user/usertablecolumns/del",
        headers=DEMO_HEADERS,
        json={"table_key": "order_list"},
    )
    assert resp.status_code == 200

    # detail 恢复空
    resp = await post(
        system_app,
        "/apiv1/user/usertablecolumns/detail",
        headers=DEMO_HEADERS,
        json={"table_key": "order_list"},
    )
    assert resp.json()["data"]["content"] == ""


@pytest.mark.asyncio
async def test_table_column_requires_table_key(system_app):
    resp = await post(system_app, "/apiv1/user/usertablecolumns/edit", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_system_requires_session(system_app):
    resp = await post(system_app, "/apiv1/common/getconfiginfo")
    assert resp.status_code == 401
