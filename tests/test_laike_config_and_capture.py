import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


ROOT = Path(__file__).parents[1]
CAPTURE_PATH = ROOT / "tools/laike_capture.py"


def load_capture_module():
    assert CAPTURE_PATH.is_file(), "tools/laike_capture.py is missing"
    spec = importlib.util.spec_from_file_location("tools.laike_capture", CAPTURE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_settings_exposes_laike_contract_with_secure_defaults():
    settings = Settings(_env_file=None)

    assert {
        "test_database_url",
        "laike_base_url",
        "laike_orders_path",
        "laike_app_id",
        "laike_app_secret",
        "laike_access_token",
        "laike_webhook_secret",
        "laike_webhook_signature_header",
        "laike_webhook_event_id_header",
        "laike_sync_mode",
        "laike_webhook_enabled",
        "laike_reconcile_enabled",
        "laike_write_enabled",
        "laike_max_retries",
        "laike_overlap_seconds",
    }.issubset(Settings.model_fields)
    assert settings.laike_sync_mode == "observe"
    assert settings.laike_webhook_enabled is False
    assert settings.laike_reconcile_enabled is False
    assert settings.laike_write_enabled is False
    assert settings.laike_webhook_signature_header == "X-Laike-Signature"
    assert settings.laike_webhook_event_id_header == "X-Laike-Event-Id"
    assert settings.laike_max_retries == 5
    assert settings.laike_overlap_seconds == 300


def test_settings_rejects_unknown_sync_mode():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, laike_sync_mode="invalid")


def test_settings_normalizes_blank_laike_values_to_none_and_parses_booleans():
    settings = Settings(
        _env_file=None,
        test_database_url=" ",
        laike_base_url="",
        laike_orders_path=" ",
        laike_app_id="",
        laike_app_secret=" ",
        laike_access_token="",
        laike_webhook_secret=" ",
        laike_webhook_enabled="true",
        laike_reconcile_enabled="1",
        laike_write_enabled="false",
    )

    assert settings.test_database_url is None
    assert settings.laike_base_url is None
    assert settings.laike_orders_path is None
    assert settings.laike_app_id is None
    assert settings.laike_app_secret is None
    assert settings.laike_access_token is None
    assert settings.laike_webhook_secret is None
    assert settings.laike_webhook_enabled is True
    assert settings.laike_reconcile_enabled is True
    assert settings.laike_write_enabled is False


def test_sanitize_payload_redacts_sensitive_keys_recursively():
    capture = load_capture_module()
    payload = {
        "order_id": "DEMO-ORDER-001",
        "Customer": {
            "phoneNumber": "00000000000",
            "name": "Demo User",
            "items": [{"Authorization": "Bearer demo-token", "quantity": 1}],
        },
        "notes": ["keep this", 7, None],
    }

    assert capture.sanitize_payload(payload) == {
        "order_id": "DEMO-ORDER-001",
        "Customer": {
            "phoneNumber": "[REDACTED]",
            "name": "Demo User",
            "items": [{"Authorization": "[REDACTED]", "quantity": 1}],
        },
        "notes": ["keep this", 7, None],
    }


def test_append_jsonl_creates_parent_and_writes_sanitized_object(tmp_path):
    capture = load_capture_module()
    target = tmp_path / "nested" / "capture.jsonl"

    capture.append_jsonl(
        target,
        {"request_id": "demo-request-001", "secret": "do-not-store", "value": "保留"},
    )

    assert target.read_text(encoding="utf-8") == (
        '{"request_id": "demo-request-001", "secret": "[REDACTED]", '
        '"value": "保留"}\n'
    )
    assert json.loads(target.read_text(encoding="utf-8"))["secret"] == "[REDACTED]"


def test_append_jsonl_rejects_non_object_records(tmp_path):
    capture = load_capture_module()

    with pytest.raises(TypeError):
        capture.append_jsonl(tmp_path / "capture.jsonl", ["not", "an", "object"])


def test_laike_fixtures_are_demo_only_jsonl_records_with_request_ids():
    fixture_dir = ROOT / "contracts/fixtures/laike"
    fixture_names = (
        "accounts.jsonl",
        "products.jsonl",
        "sync-orders.jsonl",
        "webhooks.jsonl",
        "errors.jsonl",
    )

    for fixture_name in fixture_names:
        lines = (fixture_dir / fixture_name).read_text(encoding="utf-8").splitlines()
        assert lines
        for line in lines:
            record = json.loads(line)
            assert isinstance(record, dict)
            assert record["request_id"]
            assert "DEMO-" in json.dumps(record)
            assert "password" not in line.lower()
            assert "private_key" not in line.lower()

    normalization = json.loads(
        (fixture_dir / "normalization.json").read_text(encoding="utf-8")
    )
    assert normalization["ignore_paths"]
    assert normalization["replace_paths"]


def test_api_manifest_uses_version_two_and_non_sensitive_route_sections():
    manifest = json.loads(
        (ROOT / "contracts/api-manifest.json").read_text(encoding="utf-8")
    )
    template = manifest["route_record_template"]

    assert manifest["version"] == 2
    assert manifest["migrated_routes"] == []
    assert set(template["request"]) >= {"headers"}
    assert set(template["identifiers"]) >= {"order_id", "subject_id", "product_id"}
    assert set(template["pagination"]) >= {"cursor", "start_time", "end_time"}
    assert "sync_effects" in template
    assert "normalization_rules" in template
    assert any("PHP/Python" in note for note in manifest["notes"])
