from __future__ import annotations

from collections.abc import Mapping

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder
from app.laike.contracts import LaikePage
from app.laike.normalizer import normalize_douyin_order
from app.laike.service import LaikeSyncService
from app.laike.client import ClientTokenProvider, DouyinLaikeClient


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def official_order() -> dict[str, object]:
    return {
        "order_id": "DEMO-LAIKE-ORDER-001",
        "order_status": 200,
        "pay_amount": 9900,
        "create_order_time": 1789257600,
        "update_order_time": 1789257660,
        "pay_time": 1789257630,
        "user_id": 10001,
        "products": [{"product_id": "DEMO-LAIKE-PRODUCT-001"}],
        "private_field": {"phone": "DEMO-REDACTED"},
    }


def test_douyin_order_normalizer_maps_confirmed_fields_and_keeps_raw_payload():
    normalized = normalize_douyin_order(
        official_order(),
        account_id="DEMO-LAIKE-ACCOUNT-001",
    )

    assert normalized.order_id == "DEMO-LAIKE-ORDER-001"
    assert normalized.account_id == "DEMO-LAIKE-ACCOUNT-001"
    assert normalized.order_status == 200
    assert normalized.pay_amount_fen == 9900
    assert normalized.create_order_time == 1789257600
    assert normalized.update_order_time == 1789257660
    assert normalized.pay_time == 1789257630
    assert normalized.subject_id == "10001"
    assert normalized.product_id == "DEMO-LAIKE-PRODUCT-001"
    assert normalized.raw_payload == official_order()


class OfficialClient:
    async def fetch_orders(
        self,
        account_id: str,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
        cursor: str | None = None,
    ) -> LaikePage:
        return LaikePage(items=[official_order()], has_more=False)


def test_official_client_selects_official_default_normalizer():
    client = DouyinLaikeClient(
        ClientTokenProvider("DEMO-APP", "DEMO-SECRET"),
    )
    service = LaikeSyncService(
        session_factory=lambda: None,
        client=client,
        settings=Settings(_env_file=None),
    )

    assert service.normalizer.__name__ == "normalize_douyin_order"


@pytest.mark.asyncio
async def test_reconcile_persists_official_order_indexes_in_sync_database(
    session_factory,
):
    service = LaikeSyncService(
        session_factory=session_factory,
        client=OfficialClient(),
        settings=Settings(_env_file=None, laike_sync_mode="shadow"),
        normalizer=normalize_douyin_order,
    )

    result = await service.reconcile_account("DEMO-LAIKE-ACCOUNT-001")

    assert result.success is True
    with session_factory() as session:
        order = session.scalar(
            select(LaikeOrder).where(
                LaikeOrder.provider_order_id == "DEMO-LAIKE-ORDER-001"
            )
        )
        assert order is not None
        assert order.account_id == "DEMO-LAIKE-ACCOUNT-001"
        assert order.order_status == 200
        assert order.pay_amount_fen == 9900
        assert order.create_order_time == 1789257600
        assert order.update_order_time == 1789257660
        assert order.pay_time == 1789257630
