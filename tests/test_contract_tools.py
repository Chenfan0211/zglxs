import json
from pathlib import Path

import pytest

from tools.contract_tools import (
    ContractMismatch,
    compare_recordings,
    load_recordings,
    normalize_value,
)


def test_normalize_value_replaces_registered_dynamic_fields():
    value = {
        "token": "real-token",
        "created_at": "2026-09-11T10:00:00Z",
        "data": [{"id": 12, "name": "DEMO"}],
    }

    normalized = normalize_value(
        value,
        {
            "ignore_paths": ["$.token"],
            "replace_paths": {"$.created_at": "<timestamp>"},
        },
    )

    assert normalized == {
        "created_at": "<timestamp>",
        "data": [{"id": 12, "name": "DEMO"}],
    }


def test_compare_recordings_reports_response_and_database_mismatches():
    php = {
        "status_code": 200,
        "body": {"code": 1, "data": {"count": 1}},
        "database": {"dydd_order": [{"id": 1, "status": "new"}]},
    }
    python = {
        "status_code": 200,
        "body": {"code": 1, "data": {"count": 2}},
        "database": {"dydd_order": [{"id": 1, "status": "assigned"}]},
    }

    mismatches = compare_recordings(php, python, {})

    assert mismatches == [
        ContractMismatch(
            kind="response.body",
            expected={"code": 1, "data": {"count": 1}},
            actual={"code": 1, "data": {"count": 2}},
        ),
        ContractMismatch(
            kind="database",
            expected={"dydd_order": [{"id": 1, "status": "new"}]},
            actual={"dydd_order": [{"id": 1, "status": "assigned"}]},
        ),
    ]


def test_load_recordings_reads_jsonl_by_request_id(tmp_path: Path):
    path = tmp_path / "recordings.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"request_id": "one", "status_code": 200}),
                json.dumps({"request_id": "two", "status_code": 201}),
            ]
        ),
        encoding="utf-8",
    )

    recordings = load_recordings(path)

    assert recordings["one"]["status_code"] == 200
    assert recordings["two"]["status_code"] == 201


def test_compare_recordings_rejects_missing_response_fields():
    with pytest.raises(ValueError, match="status_code"):
        compare_recordings({}, {"status_code": 200}, {})
