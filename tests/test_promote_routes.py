from __future__ import annotations

import copy
import json

import pytest

from tools.promote_routes import PromotionError, promote_verified_routes


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
        "registered": True,
        "response_mismatches": [],
        "permission_cases_passed": True,
        "database_effects_passed": True,
        "transaction_rollback_passed": True,
    }
    record.update(overrides)
    return {"routes": [record]}


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_promote_verified_routes_moves_only_fully_verified_route(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
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
        }
    ]
    assert result["discovered_routes"] == []


def test_promote_verified_routes_rejects_any_response_mismatch_without_changes(tmp_path):
    manifest_value = manifest()
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest_value)
    write_json(proof_path, proof(response_mismatches=[{"kind": "response.body"}]))

    with pytest.raises(PromotionError, match="response mismatches"):
        promote_verified_routes(manifest_path, proof_path)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest_value


@pytest.mark.parametrize(
    "field",
    [
        "registered",
        "permission_cases_passed",
        "database_effects_passed",
        "transaction_rollback_passed",
    ],
)
def test_promote_verified_routes_requires_each_safety_proof(tmp_path, field):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
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
    write_json(proof_path, proof())

    with pytest.raises(PromotionError, match="already migrated"):
        promote_verified_routes(manifest_path, proof_path)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest_value


def test_promote_verified_routes_rejects_unknown_module(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    proof_path = tmp_path / "proof.json"
    write_json(manifest_path, manifest())
    write_json(proof_path, proof(module="unknown"))

    with pytest.raises(PromotionError, match="unknown migration module"):
        promote_verified_routes(manifest_path, proof_path)
