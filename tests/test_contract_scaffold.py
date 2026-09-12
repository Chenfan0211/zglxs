from __future__ import annotations

import json

import pytest

from tools.contract_scaffold import (
    CONTRACT_MODULES,
    scaffold_fixture_directory,
)


def test_scaffold_creates_redacted_contract_fixture_layout(tmp_path):
    created = scaffold_fixture_directory(tmp_path, "organization")
    fixture_dir = tmp_path / "organization"

    assert {path.name for path in created} == {
        "cases.jsonl",
        "php.jsonl",
        "python.jsonl",
        "normalization.json",
        "database-before.json",
        "database-after.json",
        "proof.json",
    }
    assert (fixture_dir / "cases.jsonl").read_text(encoding="utf-8") == ""
    assert json.loads((fixture_dir / "normalization.json").read_text(encoding="utf-8")) == {
        "ignore_paths": [],
        "replace_paths": {},
    }
    assert json.loads((fixture_dir / "proof.json").read_text(encoding="utf-8")) == {
        "routes": []
    }


def test_scaffold_is_idempotent_and_does_not_overwrite_evidence(tmp_path):
    scaffold_fixture_directory(tmp_path, "order")
    cases = tmp_path / "cases.jsonl"
    cases.write_text('{"request_id":"redacted-case"}\n', encoding="utf-8")

    scaffold_fixture_directory(tmp_path, "order")

    assert cases.read_text(encoding="utf-8") == '{"request_id":"redacted-case"}\n'


def test_scaffold_rejects_unknown_module(tmp_path):
    with pytest.raises(ValueError, match="unknown contract module"):
        scaffold_fixture_directory(tmp_path, "live")


def test_contract_modules_are_limited_to_formal_migration_scope():
    assert CONTRACT_MODULES == ("organization", "order", "finance")
