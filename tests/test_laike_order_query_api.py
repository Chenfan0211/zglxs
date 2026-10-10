from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder, LaikeSyncRun
from app.main import create_app


@pytest.fixture
def query_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'laike-query.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                LaikeOrder(
                    provider_order_id="DEMO-LAIKE-ORDER-001",
                    account_id="DEMO-LAIKE-ACCOUNT-001",
                    order_status=200,
                    pay_amount_fen=9900,
                    create_order_time=1789257600,
                    update_order_time=1789257660,
                    pay_time=1789257630,
                    status="200",
                    payload_json={
                        "order_id": "DEMO-LAIKE-ORDER-001",
                        "private": {"phone": "DEMO-PRIVATE"},
                    },
                ),
                LaikeOrder(
                    provider_order_id="DEMO-LAIKE-ORDER-002",
                    account_id="DEMO-LAIKE-ACCOUNT-002",
                    order_status=100,
                    pay_amount_fen=1200,
                    create_order_time=1789257600,
                    update_order_time=1789257600,
                    status="100",
                    payload_json={"order_id": "DEMO-LAIKE-ORDER-002"},
                ),
            ]
        )
        session.add(
            LaikeSyncRun(
                account_id="DEMO-LAIKE-ACCOUNT-001",
                status="succeeded",
                processed_count=1,
                fetched_count=1,
                succeeded_count=1,
            )
        )
        session.commit()
    return create_app(
        Settings(
            _env_file=None,
            database_url=None,
            laike_database_url=database_url,
        )
    )


async def get_json(app, path: str, *, client_address=("127.0.0.1", 123)):
    transport = httpx.ASGITransport(app=app, client=client_address)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_order_list_filters_and_does_not_return_raw_payload(query_app):
    response = await get_json(
        query_app,
        "/api/laike/orders?account_id=DEMO-LAIKE-ACCOUNT-001&page_num=1&page_size=20",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["total"] == 1
    assert body["data"]["list"][0]["provider_order_id"] == "DEMO-LAIKE-ORDER-001"
    assert "payload_json" not in body["data"]["list"][0]
    assert set(body["data"]["list"][0]) == {
        "provider_order_id",
        "account_id",
        "order_status",
        "pay_amount_fen",
        "create_order_time",
        "update_order_time",
        "pay_time",
        "subject_id",
        "product_id",
        "first_discovered_at",
        "last_updated_at",
    }


@pytest.mark.asyncio
async def test_order_detail_redacts_sensitive_nested_payload_by_default(query_app):
    response = await get_json(query_app, "/api/laike/orders/DEMO-LAIKE-ORDER-001")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 1
    assert body["data"]["payload_json"]["private"]["phone"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_sync_runs_endpoint_returns_standard_page(query_app):
    response = await get_json(query_app, "/api/laike/sync-runs?page_num=1&page_size=20")

    assert response.status_code == 200
    assert response.json()["data"]["list"][0]["account_id"] == (
        "DEMO-LAIKE-ACCOUNT-001"
    )


@pytest.mark.asyncio
async def test_query_rejects_invalid_page_and_non_loopback_access(query_app):
    invalid = await get_json(query_app, "/api/laike/orders?page_num=0")
    assert invalid.status_code == 400
    assert invalid.json() == {"code": 0, "msg": "page_num must be positive", "data": None}

    remote = await get_json(
        query_app,
        "/api/laike/orders",
        client_address=("10.0.0.5", 123),
    )
    assert remote.status_code == 403
    assert remote.json()["code"] == 0


@pytest.mark.asyncio
async def test_query_without_sync_database_returns_controlled_error():
    app = create_app(Settings(_env_file=None, database_url=None, laike_database_url=None))

    response = await get_json(app, "/api/laike/orders")

    assert response.status_code == 503
    assert response.json() == {"code": 0, "msg": "来客同步库未配置", "data": None}
