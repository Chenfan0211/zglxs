from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.api.migration import MigrationRegistry
from app.core.settings import Settings
from app.domain.routes import register_business_routes


_MODULES = {"organization", "live", "order", "finance", "system"}
_MODULE_SWITCHES = {
    "organization": "MIGRATION_ORGANIZATION_ENABLED",
    "live": "MIGRATION_LIVE_ENABLED",
    "order": "MIGRATION_ORDER_ENABLED",
    "finance": "MIGRATION_FINANCE_ENABLED",
    "system": "MIGRATION_SYSTEM_ENABLED",
}
_PROOF_FIELDS = (
    "registered",
    "http_status_codes_passed",
    "response_schema_passed",
    "permission_cases_passed",
    "error_cases_passed",
    "database_effects_passed",
    "query_side_effects_passed",
    "transaction_rollback_passed",
    "idempotency_passed",
    "concurrency_passed",
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
    registered = _registered_route_index()
    entries = proof.get("routes")
    if not isinstance(entries, list) or not entries:
        raise PromotionError("proof routes must be a non-empty list")

    promotions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        route = _validate_proof_entry(entry, manifest_path, proof_path)
        key = _route_key(route)
        if key in seen:
            raise PromotionError(f"duplicate proof route: {_display(key)}")
        seen.add(key)
        if key in migrated:
            raise PromotionError(f"route already migrated: {_display(key)}")
        if key not in discovered:
            raise PromotionError(f"route is not discovered: {_display(key)}")
        registered_route = registered.get(key)
        if registered_route is None:
            raise PromotionError(
                f"route is not registered in application code: {_display(key)}"
            )
        if registered_route.get("module") != route["module"]:
            raise PromotionError(f"registered module mismatch for {_display(key)}")
        if not _module_is_enabled(route["module"]):
            raise PromotionError(
                f"module switch is disabled for {_display(key)}"
            )
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


def _validate_proof_entry(
    entry: Any,
    manifest_path: Path,
    proof_path: Path,
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise PromotionError("proof route must be an object")
    key = _route_key(entry)
    module = entry.get("module")
    if module not in _MODULES:
        raise PromotionError(f"unknown migration module: {module}")
    expected_switch = _MODULE_SWITCHES[module]
    if entry.get("module_switch") != expected_switch:
        raise PromotionError(
            f"missing or invalid module switch for {_display(key)}: {expected_switch}"
        )
    if entry.get("response_mismatches") != []:
        raise PromotionError(f"response mismatches for {_display(key)}")
    for field in _PROOF_FIELDS:
        if entry.get(field) is not True:
            raise PromotionError(f"missing safety proof: {field} for {_display(key)}")
    registered_route = entry.get("registered_route")
    if not isinstance(registered_route, dict):
        raise PromotionError(f"registered_route is required for {_display(key)}")
    if _route_key(registered_route) != key:
        raise PromotionError(f"registered route mismatch for {_display(key)}")
    _validate_proof_files(entry.get("proof_files"), manifest_path, proof_path, key)
    return {
        "method": key[0],
        "controller": key[1],
        "action": key[2],
        "module": module,
        "module_switch": expected_switch,
        "status": "verified",
        **{field: entry[field] for field in _PROOF_FIELDS},
        "response_mismatches": [],
        "proof_files": list(entry["proof_files"]),
    }


def _registered_route_index() -> dict[tuple[str, str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for route in _load_registered_business_routes():
        if not isinstance(route, dict):
            raise PromotionError("application registry contains a non-object route")
        key = _route_key(route)
        if key in indexed:
            raise PromotionError(f"duplicate application route: {_display(key)}")
        indexed[key] = route
    return indexed


def _load_registered_business_routes() -> list[dict[str, str]]:
    settings = Settings(_env_file=None)
    registry = MigrationRegistry(module_enabled=settings.formal_migration_enabled)
    register_business_routes(registry, settings)
    return registry.routes()


def _module_is_enabled(module: str) -> bool:
    return Settings(_env_file=None).formal_migration_enabled(module)


def _validate_proof_files(
    proof_files: Any,
    manifest_path: Path,
    proof_path: Path,
    key: tuple[str, str, str],
) -> None:
    if not isinstance(proof_files, list) or not proof_files:
        raise PromotionError(f"proof_files are required for {_display(key)}")
    roots = (Path.cwd(), manifest_path.parent, proof_path.parent)
    for value in proof_files:
        if not isinstance(value, str) or not value.strip():
            raise PromotionError(f"invalid proof file for {_display(key)}")
        path = Path(value)
        candidates = [path] if path.is_absolute() else [root / path for root in roots]
        if not any(candidate.is_file() and candidate.stat().st_size > 0 for candidate in candidates):
            raise PromotionError(f"proof file does not exist: {value}")


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
