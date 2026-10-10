from __future__ import annotations

import copy
import json

import pytest

import tools.promote_routes as promote_routes
from tools.promote_routes import PromotionError, promote_verified_routes


@pytest.fixture(autouse=True)
def registered_business_route(monkeypatch):
    monkeypatch.setattr(
        promote_routes,
        "_load_registered_business_routes",
        lambda: [
            {
                "method": "POST",
                "controller": "user",
                "action": "staff/index",
                "module": "organization",
            }
        ],
    )
    monkeypatch.setattr(promote_routes, "_module_is_enabled", lambda module: True)


def manifest() -> dict:
    return {
        "version": 2,
        "fallback_enabled_by_default": False,
        "migrated_routes": [],
        "discovered_routes": [
            {
                "method": "POST",
                "controller": "user",
                "action": "staff/index",
                "module": "organization",
            }
        ],
    }


def proof(**overrides) -> dict:
    record = {
        "method": "POST",
        "controller": "user",
        "action": "staff/index",
        "module": "organization",
        "module_switch": "MIGRATION_ORGANIZATION_ENABLED",
        "registered": True,
        "registered_route": {
            "method": "POST",
            "controller": "user",
            "action": "staff/index",
        },
        "response_mismatches": [],
        "http_status_codes_passed": True,
        "response_schema_passed": True,
        "permission_cases_passed": True,
        "error_cases_passed": True,
        "database_effects_passed": True,
        "query_side_effects_passed": True,
        "transaction_rollback_passed": True,
        "idempotency_passed": True,
        "concurrency_passed": True,
        "proof_files": ["php.jsonl", "python.jsonl"],
    }
    record.update(overrides)
    return {"routes": [record]}


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def write_proof_inputs(tmp_path):
    for name in ("php.jsonl", "python.jsonl"):
        (tmp_path / name).write_text('{"request_id":"case-1"}\n', encoding="utf-8")


def test_promote_verified_routes_moves_only_fully_verified_route(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)
    write_json(proof_path, proof())

    promoted = promote_verified_routes(manifest_path, proof_path)

    assert promoted == 1
    result = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert result["migrated_routes"] == [
        {
            "method": "POST",
            "controller": "user",
            "action": "staff/index",
            "module": "organization",
            "module_switch": "MIGRATION_ORGANIZATION_ENABLED",
            "status": "verified",
            "registered": True,
            "response_mismatches": [],
            "http_status_codes_passed": True,
            "response_schema_passed": True,
            "permission_cases_passed": True,
            "error_cases_passed": True,
            "database_effects_passed": True,
            "query_side_effects_passed": True,
            "transaction_rollback_passed": True,
            "idempotency_passed": True,
            "concurrency_passed": True,
            "proof_files": ["php.jsonl", "python.jsonl"],
        }
    ]
    assert result["discovered_routes"] == []


def test_promote_verified_routes_rejects_any_response_mismatch_without_changes(tmp_path):
    manifest_value = manifest()
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest_value)
    write_proof_inputs(tmp_path)
    write_json(proof_path, proof(response_mismatches=[{"kind": "response.body"}]))

    with pytest.raises(PromotionError, match="response mismatches"):
        promote_verified_routes(manifest_path, proof_path)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest_value


@pytest.mark.parametrize(
    "field",
    [
        "registered",
        "http_status_codes_passed",
        "response_schema_passed",
        "permission_cases_passed",
        "database_effects_passed",
        "query_side_effects_passed",
        "transaction_rollback_passed",
        "concurrency_passed",
    ],
)
def test_promote_verified_routes_requires_each_safety_proof(tmp_path, field):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)
    invalid = proof(**{field: False})
    write_json(proof_path, invalid)

    with pytest.raises(PromotionError):
        promote_verified_routes(manifest_path, proof_path)


def test_promote_verified_routes_rejects_duplicate_or_unlisted_route(tmp_path):
    manifest_value = manifest()
    manifest_value["migrated_routes"] = [manifest_value["discovered_routes"][0]]
    manifest_value["discovered_routes"] = []
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest_value)
    write_proof_inputs(tmp_path)
    write_json(proof_path, proof())

    with pytest.raises(PromotionError, match="already migrated"):
        promote_verified_routes(manifest_path, proof_path)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest_value


def test_promote_verified_routes_rejects_unknown_module(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)
    write_json(proof_path, proof(module="unknown"))

    with pytest.raises(PromotionError, match="unknown migration module"):
        promote_verified_routes(manifest_path, proof_path)


@pytest.mark.parametrize("field", ["error_cases_passed", "idempotency_passed"])
def test_promote_verified_routes_requires_behavioral_safety_proof(tmp_path, field):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)
    write_json(proof_path, proof(**{field: False}))

    with pytest.raises(PromotionError, match="missing safety proof"):
        promote_verified_routes(manifest_path, proof_path)


def test_promote_verified_routes_requires_registered_route_and_evidence_files(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)

    write_json(proof_path, proof(registered_route=None))
    with pytest.raises(PromotionError, match="registered_route"):
        promote_verified_routes(manifest_path, proof_path)

    write_json(proof_path, proof(proof_files=["missing.jsonl"]))
    with pytest.raises(PromotionError, match="proof file"):
        promote_verified_routes(manifest_path, proof_path)


def test_promote_verified_routes_rejects_registered_route_mismatch(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)
    write_json(
        proof_path,
        proof(registered_route={"method": "GET", "controller": "user", "action": "staff/index"}),
    )

    with pytest.raises(PromotionError, match="registered route mismatch"):
        promote_verified_routes(manifest_path, proof_path)


def test_promote_verified_routes_rejects_proof_for_route_not_registered_in_code(
    tmp_path,
    monkeypatch,
):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)
    write_json(proof_path, proof())
    monkeypatch.setattr(promote_routes, "_load_registered_business_routes", lambda: [])

    with pytest.raises(PromotionError, match="not registered in application code"):
        promote_verified_routes(manifest_path, proof_path)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest()


def test_promote_verified_routes_rejects_disabled_module_without_changes(
    tmp_path,
    monkeypatch,
):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_proof_inputs(tmp_path)
    write_json(proof_path, proof())
    monkeypatch.setattr(promote_routes, "_module_is_enabled", lambda module: False)

    with pytest.raises(PromotionError, match="module switch is disabled"):
        promote_verified_routes(manifest_path, proof_path)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest()
