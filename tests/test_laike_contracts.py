from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.laike.contracts import (
    LaikePage,
    NormalizedOrder,
    SyncResult,
    WebhookVerification,
)
from app.laike.normalizer import normalize_order


def test_laike_settings_are_disabled_and_have_safe_defaults(monkeypatch):
    for key in tuple(os.environ):
        if key.startswith("LAIKE_"):
            monkeypatch.delenv(key, raising=False)

    settings = Settings()

    assert settings.laike_sync_mode == "observe"
    assert settings.laike_webhook_enabled is False
    assert settings.laike_reconcile_enabled is False
    assert settings.laike_write_enabled is False
    assert settings.laike_webhook_secret is None
    assert settings.laike_app_id is None
    assert settings.laike_app_secret is None
    assert settings.laike_access_token is None
    assert settings.laike_max_retries == 3


def test_protocol_objects_have_stable_shapes():
    page = LaikePage(items=[], next_cursor=None, has_more=False)
    verification = WebhookVerification(verified=True, reason=None)
    result = SyncResult(success=True, processed_count=1, failed_count=0)

    assert page.model_dump() == {"items": [], "next_cursor": None, "has_more": False}
    assert verification.model_dump() == {"verified": True, "reason": None}
    assert result.model_dump() == {
        "success": True,
        "processed_count": 1,
        "failed_count": 0,
    }


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (LaikePage, {"items": [], "unexpected": True}),
        (WebhookVerification, {"verified": True, "unexpected": True}),
        (NormalizedOrder, {"unexpected": True}),
        (SyncResult, {"success": True, "unexpected": True}),
    ],
)
def test_protocol_objects_reject_unknown_fields(model, data):
    with pytest.raises(ValidationError):
        model(**data)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (LaikePage, {"items": [], "has_more": 1}),
        (WebhookVerification, {"verified": 1}),
        (NormalizedOrder, {"payload_json": []}),
        (SyncResult, {"success": 1}),
    ],
)
def test_protocol_objects_reject_invalid_key_types(model, data):
    with pytest.raises(ValidationError):
        model(**data)


def test_normalize_order_reads_only_stable_keys_and_preserves_payload():
    payload = {
        "order_id": "ORDER-001",
        "status": "paid",
        "created_at": "2026-09-11T12:00:00+08:00",
        "unknown_business_field": {"keep": True},
    }

    order = normalize_order(payload)

    assert isinstance(order, NormalizedOrder)
    assert order.order_id == "ORDER-001"
    assert order.status == "paid"
    assert order.created_at == "2026-09-11T12:00:00+08:00"
    assert order.payload_json == payload
    assert "unknown_business_field" not in order.model_fields_set


def test_normalize_order_allows_missing_order_id_without_guessing():
    payload = {"status": "paid", "id": "do-not-promote"}

    order = normalize_order(payload)

    assert order.order_id is None
    assert order.payload_json == payload


def test_normalize_order_redacted_log_metadata_contains_no_secrets():
    payload = {
        "order_id": "ORDER-001",
        "access_token": "secret-token",
        "app_secret": "secret-app",
        "buyer_phone": "13800000000",
    }

    order = normalize_order(payload)
    metadata = order.log_metadata()

    assert metadata == {"order_id": "ORDER-001", "has_payload": True}
    assert "secret-token" not in repr(metadata)
    assert "13800000000" not in repr(metadata)
