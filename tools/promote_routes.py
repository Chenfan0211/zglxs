from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_MODULES = {"organization", "live", "order", "finance", "system"}
_PROOF_FIELDS = (
    "registered",
    "permission_cases_passed",
    "database_effects_passed",
    "transaction_rollback_passed",
)


class PromotionError(ValueError):
    pass


def promote_verified_routes(
    manifest_path: Path,
    proof_path: Path,
) -> int:
    manifest = _load_object(manifest_path, "manifest")
    proof = _load_object(proof_path, "proof")
    discovered = _route_index(manifest, "discovered_routes")
    migrated = _route_index(manifest, "migrated_routes")
    entries = proof.get("routes")
    if not isinstance(entries, list) or not entries:
        raise PromotionError("proof routes must be a non-empty list")

    promotions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        route = _validate_proof_entry(entry)
        key = _route_key(route)
        if key in seen:
            raise PromotionError(f"duplicate proof route: {_display(key)}")
        seen.add(key)
        if key in migrated:
            raise PromotionError(f"route already migrated: {_display(key)}")
        if key not in discovered:
            raise PromotionError(f"route is not discovered: {_display(key)}")
        promotions.append(route)

    manifest["migrated_routes"].extend(promotions)
    manifest["discovered_routes"] = [
        route for key, route in discovered.items() if key not in seen
    ]
    _write_object(manifest_path, manifest)
    return len(promotions)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotionError(f"unable to read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise PromotionError(f"{label} must be a JSON object")
    return value


def _route_index(manifest: dict[str, Any], field: str) -> dict[tuple[str, str, str], dict[str, Any]]:
    routes = manifest.get(field)
    if not isinstance(routes, list):
        raise PromotionError(f"manifest {field} must be a list")
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for route in routes:
        if not isinstance(route, dict):
            raise PromotionError(f"manifest {field} contains a non-object route")
        key = _route_key(route)
        if key in indexed:
            raise PromotionError(f"duplicate manifest route: {_display(key)}")
        indexed[key] = route
    return indexed


def _validate_proof_entry(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise PromotionError("proof route must be an object")
    key = _route_key(entry)
    module = entry.get("module")
    if module not in _MODULES:
        raise PromotionError(f"unknown migration module: {module}")
    if entry.get("response_mismatches") != []:
        raise PromotionError(f"response mismatches for {_display(key)}")
    for field in _PROOF_FIELDS:
        if entry.get(field) is not True:
            raise PromotionError(f"missing safety proof: {field} for {_display(key)}")
    return {
        "method": key[0],
        "controller": key[1],
        "action": key[2],
        "module": module,
    }


def _route_key(route: dict[str, Any]) -> tuple[str, str, str]:
    values = (route.get("method"), route.get("controller"), route.get("action"))
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise PromotionError("route requires non-empty method, controller and action")
    return values[0].upper(), values[1], values[2]


def _display(key: tuple[str, str, str]) -> str:
    return f"{key[0]} /apiv1/{key[1]}/{key[2]}"


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote routes with complete PHP/Python verification proof"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--proof", required=True, type=Path)
    args = parser.parse_args()
    print(promote_verified_routes(args.manifest, args.proof))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
