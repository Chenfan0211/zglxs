from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContractMismatch:
    kind: str
    expected: Any
    actual: Any


def load_recordings(path: Path) -> dict[str, dict[str, Any]]:
    recordings: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            request_id = record.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                raise ValueError(f"recording line {line_number} is missing request_id")
            recordings[request_id] = record
    return recordings


def normalize_value(value: Any, rules: Mapping[str, Any]) -> Any:
    normalized = copy.deepcopy(value)
    for path in rules.get("ignore_paths", []):
        _delete_path(normalized, path)
    for path, replacement in rules.get("replace_paths", {}).items():
        _replace_path(normalized, path, replacement)
    return normalized


def compare_recordings(
    php_recording: Mapping[str, Any],
    python_recording: Mapping[str, Any],
    normalization_rules: Mapping[str, Any],
) -> list[ContractMismatch]:
    _require_keys(php_recording, "php")
    _require_keys(python_recording, "python")

    expected_body = normalize_value(php_recording.get("body"), normalization_rules)
    actual_body = normalize_value(python_recording.get("body"), normalization_rules)
    expected_db = normalize_value(php_recording.get("database", {}), normalization_rules)
    actual_db = normalize_value(python_recording.get("database", {}), normalization_rules)

    mismatches: list[ContractMismatch] = []
    if php_recording["status_code"] != python_recording["status_code"]:
        mismatches.append(
            ContractMismatch(
                kind="response.status_code",
                expected=php_recording["status_code"],
                actual=python_recording["status_code"],
            )
        )
    if expected_body != actual_body:
        mismatches.append(
            ContractMismatch(
                kind="response.body",
                expected=expected_body,
                actual=actual_body,
            )
        )
    if expected_db != actual_db:
        mismatches.append(
            ContractMismatch(
                kind="database",
                expected=expected_db,
                actual=actual_db,
            )
        )
    return mismatches


def _require_keys(recording: Mapping[str, Any], label: str) -> None:
    for key in ("status_code", "body"):
        if key not in recording:
            raise ValueError(f"{label} recording is missing {key}")


def _delete_path(value: Any, path: str) -> None:
    parent, key = _resolve_parent(value, path)
    if isinstance(parent, dict):
        parent.pop(key, None)


def _replace_path(value: Any, path: str, replacement: Any) -> None:
    parent, key = _resolve_parent(value, path)
    if isinstance(parent, dict) and key in parent:
        parent[key] = replacement


def _resolve_parent(value: Any, path: str) -> tuple[Any, str]:
    if not path.startswith("$."):
        raise ValueError(f"only simple $.field paths are supported: {path}")
    parts = path[2:].split(".")
    parent = value
    for part in parts[:-1]:
        if isinstance(parent, dict):
            parent = parent.get(part)
        else:
            parent = None
        if parent is None:
            break
    return parent, parts[-1]
