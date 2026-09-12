from __future__ import annotations

import json
import subprocess
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models.base import Base
from app.db.models.laike import (
    LaikeOrder,
    LaikeSyncCursor,
    LaikeSyncRun,
    LaikeWebhookEvent,
)
from tools.seed_laike_demo_data import seed_demo_data


def _session_factory(database_url: str = "sqlite+pysqlite:///:memory:"):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_seed_demo_data_is_idempotent_and_scoped_to_demo_rows():
    engine, factory = _session_factory()
    try:
        with factory() as session:
            first = seed_demo_data(session, count=3)
        with factory() as session:
            second = seed_demo_data(session, count=3)

        assert first == second == {
            "account_id": "DEMO-LAIKE-ACCOUNT-001",
            "orders": 3,
            "webhook_events": 3,
            "sync_cursors": 1,
            "sync_runs": 1,
        }

        with factory() as session:
            orders = session.scalars(select(LaikeOrder)).all()
            events = session.scalars(select(LaikeWebhookEvent)).all()
            cursors = session.scalars(select(LaikeSyncCursor)).all()
            runs = session.scalars(select(LaikeSyncRun)).all()

        assert len(orders) == 3
        assert len(events) == 3
        assert len(cursors) == 1
        assert len(runs) == 1
        assert all(order.provider_order_id.startswith("DEMO-LAIKE-ORDER-") for order in orders)
        assert all(event.source == "demo-seed" for event in events)
        assert all(event.headers_json.keys() == {"X-Trace"} for event in events)
        assert {order.payload_json["buyer"]["phone"] for order in orders} == {
            "DEMO-PHONE-0001",
            "DEMO-PHONE-0002",
            "DEMO-PHONE-0003",
        }
    finally:
        engine.dispose()


def test_seed_demo_data_updates_existing_demo_order_without_duplicate():
    engine, factory = _session_factory()
    try:
        with factory() as session:
            seed_demo_data(session, count=1)
            order = session.scalar(
                select(LaikeOrder).where(
                    LaikeOrder.provider_order_id == "DEMO-LAIKE-ORDER-0001"
                )
            )
            assert order is not None
            order.status = "stale"
            session.commit()

        with factory() as session:
            seed_demo_data(session, count=1)

        with factory() as session:
            orders = session.scalars(select(LaikeOrder)).all()
        assert len(orders) == 1
        assert orders[0].status == "paid"
    finally:
        engine.dispose()


def test_seed_demo_data_cli_reads_test_database_url(tmp_path, monkeypatch):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'demo.db'}"
    engine, _ = _session_factory(database_url)
    engine.dispose()
    monkeypatch.setenv("TEST_DATABASE_URL", database_url)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.seed_laike_demo_data",
            "--count",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert json.loads(completed.stdout) == {
        "account_id": "DEMO-LAIKE-ACCOUNT-001",
        "orders": 2,
        "webhook_events": 2,
        "sync_cursors": 1,
        "sync_runs": 1,
    }
