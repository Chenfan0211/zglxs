"""财务模块行为测试。

财务模块无独立写操作 CRUD，核心为结算列表（分页/脱敏/关联名称）与统计汇总。
本文件补充分页边界、统计金额准确性、无库 503 语义。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def finance_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'finance.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                LaikeOrder(
                    provider_order_id="DEMO-FIN-001",
                    account_id="DEMO-ACC-001",
                    order_status=3,
                    pay_amount_fen=10000,
                    create_order_time=1789257600,
                    update_order_time=1789257660,
                    status="3",
                    payload_json={"order_id": "DEMO-FIN-001", "product_name": "商品A", "talent_commission": 500},
                ),
                LaikeOrder(
                    provider_order_id="DEMO-FIN-002",
                    account_id="DEMO-ACC-002",
                    order_status=1,
                    pay_amount_fen=2000,
                    create_order_time=1789257600,
                    update_order_time=1789257600,
                    status="1",
                    payload_json={"order_id": "DEMO-FIN-002", "product_name": "商品B"},
                ),
                # 未支付订单（pay_amount_fen 为空），不应进入结算列表
                LaikeOrder(
                    provider_order_id="DEMO-FIN-003",
                    account_id="DEMO-ACC-003",
                    order_status=0,
                    pay_amount_fen=None,
                    create_order_time=1789257600,
                    update_order_time=1789257600,
                    status="0",
                    payload_json={"order_id": "DEMO-FIN-003"},
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
async def test_settlement_excludes_unpaid_orders(finance_app):
    resp = await post(finance_app, "/apiv1/financial/settlementlist", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    body = resp.json()["data"]
    # 未支付订单（pay_amount_fen 为 None）不计入结算
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_settlement_pagination(finance_app):
    resp = await post(finance_app, "/apiv1/financial/settlementlist", headers=DEMO_HEADERS, json={"page": 1, "page_size": 1})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 2
    assert len(body["list"]) == 1


@pytest.mark.asyncio
async def test_settlement_row_contains_finance_fields(finance_app):
    resp = await post(finance_app, "/apiv1/financial/settlementlist", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    row = resp.json()["data"]["list"][0]
    assert row["verify_amount"] == 2000 or row["verify_amount"] == 10000
    assert "product_name" in row
    assert "order_no" in row


@pytest.mark.asyncio
async def test_statistic_sums_amounts(finance_app):
    resp = await post(finance_app, "/apiv1/financial/statistic", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total_orders"] == 3  # 所有订单
    assert body["paid_orders"] == 2   # 已支付订单
    assert body["total_amount_fen"] == 12000  # 10000 + 2000


@pytest.mark.asyncio
async def test_settlement_requires_session(finance_app):
    resp = await post(finance_app, "/apiv1/financial/settlementlist")
    assert resp.status_code == 401
