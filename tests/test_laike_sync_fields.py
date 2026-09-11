from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from app.db.models.base import Base
from app.db.models.laike import LaikeOrder, LaikeWebhookEvent
from app.laike.contracts import SyncResult
from app.laike.repositories import LaikeRepository


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_laike_sync_models_expose_only_required_persistence_fields():
    assert {
        column.name for column in inspect(LaikeWebhookEvent).columns
    } >= {"source", "error_reason"}
    assert {
        column.name for column in inspect(LaikeOrder).columns
    } >= {
        "subject_id",
        "product_id",
        "original_created_at",
        "normalized_created_at",
        "original_updated_at",
        "normalized_updated_at",
        "first_discovered_at",
        "last_updated_at",
        "created_at",
    }


def test_repository_webhook_defaults_and_redacts_signature_values():
    session_factory = _session_factory()

    with session_factory() as session:
        repository = LaikeRepository(session)
        event = repository.insert_webhook_event(
            "evt-defaults",
            {"event_id": "evt-defaults"},
            {"X-Signature": "secret-signature", "X-Trace": "trace-001"},
            True,
        )
        session.commit()

    assert event.source == "laike"
    assert event.error_reason is None
    assert event.headers_json == {"X-Trace": "trace-001"}
    assert "secret-signature" not in repr(event)


def test_repository_webhook_redacts_all_sensitive_header_categories():
    session_factory = _session_factory()
    headers = {
        "Authorization": "Bearer demo-auth",
        "Cookie": "session=demo-cookie",
        "X-Access-Token": "demo-token",
        "X-App-Secret": "demo-secret",
        "X-Signature": "demo-signature",
        "X-Password": "demo-password",
        "X-Api-Key": "demo-api-key",
        "X-Credential": "demo-credential",
        "X-Trace": "trace-001",
    }

    with session_factory() as session:
        event = LaikeRepository(session).insert_webhook_event(
            "evt-sensitive-headers", {}, headers, True
        )
        session.commit()

    assert event.headers_json == {"X-Trace": "trace-001"}
    assert all(value not in repr(event) for value in headers.values() if value != "trace-001")


def test_repository_webhook_accepts_source_and_error_reason():
    session_factory = _session_factory()

    with session_factory() as session:
        event = LaikeRepository(session).insert_webhook_event(
            "evt-invalid",
            {"event_id": "evt-invalid"},
            {"X-Trace": "trace-002"},
            False,
            source="provider-a",
            error_reason="invalid signature",
        )
        session.commit()

    assert event.source == "provider-a"
    assert event.error_reason == "invalid signature"


def test_repository_upsert_updates_mapping_and_times_but_preserves_first_discovery():
    session_factory = _session_factory()

    with session_factory() as session:
        repository = LaikeRepository(session)
        first = repository.upsert_order(
            "order-001",
            {"order_id": "order-001", "status": "paid"},
            "paid",
            "2026-09-11T12:00:00+08:00",
            subject_id="subject-001",
            product_id="product-001",
            original_created_at="2026-09-11T12:00:00+08:00",
            normalized_created_at="2026-09-11T04:00:00Z",
            original_updated_at="2026-09-11T12:01:00+08:00",
            normalized_updated_at="2026-09-11T04:01:00Z",
        )
        session.commit()
        first_discovered_at = _as_utc(first.first_discovered_at)
        first_last_updated_at = _as_utc(first.last_updated_at)

        time.sleep(0.001)
        second = repository.upsert_order(
            "order-001",
            {"order_id": "order-001", "status": "completed"},
            "completed",
            "2026-09-11T12:00:00+08:00",
            subject_id="subject-002",
            product_id="product-002",
            original_created_at={"raw": "2026-09-11T12:00:00+08:00"},
            normalized_created_at=None,
            original_updated_at="2026-09-11T13:00:00+08:00",
            normalized_updated_at="2026-09-11T05:00:00Z",
        )
        session.commit()

        persisted = session.scalar(
            select(LaikeOrder).where(LaikeOrder.provider_order_id == "order-001")
        )

    assert persisted is second
    assert persisted.payload_json == {
        "order_id": "order-001",
        "status": "completed",
    }
    assert persisted.status == "completed"
    assert persisted.subject_id == "subject-002"
    assert persisted.product_id == "product-002"
    assert persisted.original_created_at == {
        "raw": "2026-09-11T12:00:00+08:00"
    }
    assert persisted.normalized_created_at == "2026-09-11T04:00:00Z"
    assert persisted.original_updated_at == "2026-09-11T13:00:00+08:00"
    assert persisted.normalized_updated_at == "2026-09-11T05:00:00Z"
    assert _as_utc(persisted.first_discovered_at) == first_discovered_at
    assert _as_utc(persisted.last_updated_at) > first_last_updated_at
    assert persisted.created_at == "2026-09-11T12:00:00+08:00"


def test_sync_result_new_fields_are_opt_in_for_legacy_model_dump_shape():
    legacy = SyncResult(success=True, processed_count=1, failed_count=0)
    assert legacy.model_dump() == {
        "success": True,
        "processed_count": 1,
        "failed_count": 0,
    }

    current = SyncResult(
        success=True,
        event_id="evt-001",
        reason=None,
        fetched_count=2,
        succeeded_count=1,
        duplicate_count=1,
    )
    assert current.model_dump() == {
        "success": True,
        "processed_count": 0,
        "failed_count": 0,
        "event_id": "evt-001",
        "reason": None,
        "fetched_count": 2,
        "succeeded_count": 1,
        "duplicate_count": 1,
    }
