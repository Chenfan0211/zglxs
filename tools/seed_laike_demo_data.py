from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models.laike import (
    LaikeSyncCursor,
    LaikeSyncRun,
    LaikeWebhookEvent,
)
from app.laike.repositories import LaikeRepository


DEFAULT_ACCOUNT_ID = "DEMO-LAIKE-ACCOUNT-001"
DEFAULT_SUBJECT_ID = "DEMO-LAIKE-SUBJECT-001"
DEFAULT_PRODUCT_PREFIX = "DEMO-LAIKE-PRODUCT"
DEFAULT_COUNT = 12


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_at(index: int) -> str:
    base = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
    return (base + timedelta(minutes=index)).isoformat().replace("+00:00", "Z")


def _demo_payload(index: int, account_id: str) -> dict[str, Any]:
    order_id = f"DEMO-LAIKE-ORDER-{index:04d}"
    product_id = f"{DEFAULT_PRODUCT_PREFIX}-{(index % 4) + 1:03d}"
    created_at = _iso_at(index)
    updated_at = _iso_at(index + 30)
    return {
        "order_id": order_id,
        "account_id": account_id,
        "subject_id": DEFAULT_SUBJECT_ID,
        "product_id": product_id,
        "status": "paid" if index % 3 else "verified",
        "amount_cent": 9900 + index * 100,
        "buyer": {
            "nickname": f"Demo Buyer {index:04d}",
            "phone": f"DEMO-PHONE-{index:04d}",
        },
        "address": f"DEMO-ADDRESS-{index:04d}",
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _upsert_cursor(session: Session, account_id: str, count: int) -> None:
    cursor = session.scalar(
        select(LaikeSyncCursor).where(LaikeSyncCursor.account_id == account_id)
    )
    if cursor is None:
        cursor = LaikeSyncCursor(account_id=account_id)
        session.add(cursor)
    cursor.cursor = f"DEMO-CURSOR-{count:04d}"
    cursor.updated_at = _utc_now()


def _upsert_run(session: Session, account_id: str, count: int) -> None:
    run = session.scalar(
        select(LaikeSyncRun).where(
            LaikeSyncRun.account_id == account_id,
            LaikeSyncRun.start_time == "DEMO-SEED-START",
        )
    )
    if run is None:
        run = LaikeSyncRun(
            account_id=account_id,
            start_time="DEMO-SEED-START",
            end_time="DEMO-SEED-END",
        )
        session.add(run)
    run.status = "succeeded"
    run.processed_count = count
    run.failed_count = 0
    run.error_message = None
    if run.finished_at is None:
        run.started_at = _utc_now()
    run.finished_at = _utc_now()


def seed_demo_data(
    session: Session,
    *,
    count: int = DEFAULT_COUNT,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, int | str]:
    if count < 1:
        raise ValueError("count must be at least 1")

    repository = LaikeRepository(session)
    for index in range(1, count + 1):
        payload = _demo_payload(index, account_id)
        event_id = f"DEMO-LAIKE-EVENT-{index:04d}"
        event = repository.insert_webhook_event(
            event_id,
            payload,
            {"X-Trace": f"demo-trace-{index:04d}"},
            True,
            source="demo-seed",
        )
        event.status = "processed"
        event.processed_at = _utc_now()
        event.retry_count = 0
        event.next_retry_at = None
        event.retry_scheduled_at = None
        event.claim_token = None
        repository.upsert_order(
            payload["order_id"],
            payload,
            payload["status"],
            payload["created_at"],
            subject_id=payload["subject_id"],
            product_id=payload["product_id"],
            original_created_at=payload["created_at"],
            normalized_created_at=payload["created_at"],
            original_updated_at=payload["updated_at"],
            normalized_updated_at=payload["updated_at"],
        )

    _upsert_cursor(session, account_id, count)
    _upsert_run(session, account_id, count)
    session.commit()
    return {
        "account_id": account_id,
        "orders": count,
        "webhook_events": count,
        "sync_cursors": 1,
        "sync_runs": 1,
    }


def _resolve_database_url(cli_value: str | None) -> str:
    database_url = (
        cli_value
        or os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not database_url:
        raise SystemExit(
            "database url is required via --database-url, TEST_DATABASE_URL, or DATABASE_URL"
        )
    return database_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed idempotent DEMO Laike sync data into the configured test database."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database_url = _resolve_database_url(args.database_url)
    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_factory() as session:
            result = seed_demo_data(
                session,
                count=args.count,
                account_id=args.account_id,
            )
    finally:
        engine.dispose()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
