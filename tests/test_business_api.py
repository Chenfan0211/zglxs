"""五大业务模块接口行为测试。

覆盖组织/直播/订单/财务/系统模块的核心行为：
- 演示会话鉴权（无 session 统一返回 401「请先登录」）
- 列表分页与 COUNT 计数（验证 perf 优化后的总数语义）
- 写操作（新增部门）与参数校验
- 未配置业务库时的受控错误（503）
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.organization import Department
from app.db.models.laike import LaikeOrder
from app.db.models.live import LiveRoom
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def business_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'business.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                Department(name="直播部", dept_type="live", ordid=1),
                Department(name="转化部", dept_type="custom", ordid=2),
                Department(name="售后部", dept_type="maintenance", ordid=3),
                LaikeOrder(
                    provider_order_id="DEMO-ORDER-001",
                    account_id="DEMO-ACCOUNT-001",
                    order_status=3,
                    pay_amount_fen=9900,
                    create_order_time=1789257600,
                    update_order_time=1789257660,
                    pay_time=1789257630,
                    status="3",
                    payload_json={"order_id": "DEMO-ORDER-001", "product_name": "测试商品"},
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
                LiveRoom(name="直播间A", department_id=1, ordid=1),
                LiveRoom(name="直播间B", department_id=2, ordid=2),
            ]
        )
        session.commit()
    return create_app(
        Settings(
            _env_file=None,
            database_url=None,
            laike_database_url=database_url,
        )
    )


@pytest.fixture
def empty_app():
    """未配置业务库的 app，用于验证受控错误。"""
    return create_app(
        Settings(_env_file=None, database_url=None, laike_database_url=None)
    )


async def post(app, path, *, headers=None, json=None):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, headers=headers or {}, json=json or {})


# ---------- 鉴权通用性 ----------

@pytest.mark.asyncio
async def test_department_list_requires_demo_session(business_app):
    response = await post(business_app, "/apiv1/user/departments/index")
    assert response.status_code == 401
    assert response.json()["msg"] == "请先登录"


@pytest.mark.asyncio
async def test_order_tradelist_requires_demo_session(business_app):
    response = await post(business_app, "/apiv1/user/order/tradelist")
    assert response.status_code == 401
    assert response.json()["msg"] == "请先登录"


@pytest.mark.asyncio
async def test_finance_settlement_requires_demo_session(business_app):
    response = await post(business_app, "/apiv1/financial/settlementlist")
    assert response.status_code == 401
    assert response.json()["msg"] == "请先登录"


@pytest.mark.asyncio
async def test_system_config_requires_demo_session(business_app):
    response = await post(business_app, "/apiv1/common/getconfiginfo")
    assert response.status_code == 401
    assert response.json()["msg"] == "请先登录"


# ---------- organization 部门：列表与分页 COUNT ----------

@pytest.mark.asyncio
async def test_department_list_returns_all_and_total(business_app):
    response = await post(
        business_app,
        "/apiv1/user/departments/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["total"] == 3
    assert len(body["data"]["list"]) == 3


@pytest.mark.asyncio
async def test_department_list_pagination(business_app):
    response = await post(
        business_app,
        "/apiv1/user/departments/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 3
    assert len(body["data"]["list"]) == 2


@pytest.mark.asyncio
async def test_department_list_filters_by_type(business_app):
    response = await post(
        business_app,
        "/apiv1/user/departments/index",
        headers=DEMO_HEADERS,
        json={"type": "live"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
    assert body["data"]["list"][0]["type"] == "live"


# ---------- organization 部门：写操作 ----------

@pytest.mark.asyncio
async def test_department_add_creates_row(business_app):
    response = await post(
        business_app,
        "/apiv1/user/departments/add",
        headers=DEMO_HEADERS,
        json={"department_name": "测试新部门", "type": "custom", "ordid": 9},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["name"] == "测试新部门"

    # 列表总数应变为 4
    listing = await post(
        business_app,
        "/apiv1/user/departments/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert listing.json()["data"]["total"] == 4


@pytest.mark.asyncio
async def test_department_add_requires_name(business_app):
    response = await post(
        business_app,
        "/apiv1/user/departments/add",
        headers=DEMO_HEADERS,
        json={"type": "live"},
    )
    assert response.status_code == 400
    assert response.json()["msg"] == "部门名称不能为空"


@pytest.mark.asyncio
async def test_department_add_requires_session(business_app):
    response = await post(
        business_app,
        "/apiv1/user/departments/add",
        json={"department_name": "无会话新增"},
    )
    assert response.status_code == 401


# ---------- 未配置业务库时的受控错误 ----------

@pytest.mark.asyncio
async def test_department_list_without_database_returns_503(empty_app):
    response = await post(
        empty_app,
        "/apiv1/user/departments/index",
        headers=DEMO_HEADERS,
    )
    assert response.status_code == 503
    assert response.json()["msg"] == "业务库未配置"


@pytest.mark.asyncio
async def test_order_tradelist_without_database_returns_503(empty_app):
    response = await post(
        empty_app,
        "/apiv1/user/order/tradelist",
        headers=DEMO_HEADERS,
    )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_finance_settlement_without_database_returns_503(empty_app):
    response = await post(
        empty_app,
        "/apiv1/financial/settlementlist",
        headers=DEMO_HEADERS,
    )
    assert response.status_code == 503
    assert response.json()["msg"] == "来客同步库未配置"

# ---------- order 订单列表 ----------

@pytest.mark.asyncio
async def test_order_tradelist_returns_page(business_app):
    response = await post(
        business_app,
        "/apiv1/user/order/tradelist",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["total"] == 2
    assert len(body["data"]["list"]) == 2


@pytest.mark.asyncio
async def test_order_tradelist_filters_by_order_status(business_app):
    response = await post(
        business_app,
        "/apiv1/user/order/tradelist",
        headers=DEMO_HEADERS,
        json={"order_status": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
    assert body["data"]["list"][0]["provider_order_id"] == "DEMO-ORDER-001"


@pytest.mark.asyncio
async def test_order_detail_requires_order_id(business_app):
    response = await post(
        business_app,
        "/apiv1/user/order/detail",
        headers=DEMO_HEADERS,
        json={},
    )
    assert response.status_code == 400


# ---------- finance 财务结算 ----------

@pytest.mark.asyncio
async def test_finance_settlement_returns_paid_orders(business_app):
    response = await post(
        business_app,
        "/apiv1/financial/settlementlist",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["total"] == 2


@pytest.mark.asyncio
async def test_finance_statistic_returns_totals(business_app):
    response = await post(
        business_app,
        "/apiv1/financial/statistic",
        headers=DEMO_HEADERS,
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["total_orders"] == 2
    assert body["data"]["paid_orders"] == 2

# ---------- live 直播间 ----------

@pytest.mark.asyncio
async def test_live_rooms_requires_demo_session(business_app):
    response = await post(business_app, "/apiv1/user/liverooms/index")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_live_rooms_list_returns_page(business_app):
    response = await post(
        business_app,
        "/apiv1/user/liverooms/index",
        headers=DEMO_HEADERS,
        json={"page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["total"] == 2
    assert len(body["data"]["list"]) == 2
    # 部门名映射
    assert body["data"]["list"][0]["department_name"] == "直播部"


@pytest.mark.asyncio
async def test_live_rooms_filters_by_keyword(business_app):
    response = await post(
        business_app,
        "/apiv1/user/liverooms/index",
        headers=DEMO_HEADERS,
        json={"keyword": "直播间A"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
    assert body["data"]["list"][0]["name"] == "直播间A"
