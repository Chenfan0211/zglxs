from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from collections.abc import Mapping
from typing import Any


_API_ROUTE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(?:console|financial|user|collect|common|index)"
    r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+"
    r"(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)

_MODULE_PREFIXES = (
    ("financial/", "finance"),
    ("console/", "live"),
    ("collect/", "order"),
    ("user/order/", "order"),
    ("user/followstatus/", "order"),
    ("user/liveroom", "live"),
    ("user/customgroupliverooms/", "live"),
    ("user/accounts/", "organization"),
    ("user/departments/", "organization"),
    ("user/staff/", "organization"),
    ("user/customservice", "organization"),
    ("user/user/", "organization"),
    ("user/notices/", "system"),
    ("user/mobiles/", "system"),
    ("user/sms/", "system"),
    ("user/usertablecolumns/", "system"),
    ("user/", "organization"),
    ("common/", "system"),
    ("index/", "system"),
)


def extract_frontend_api_routes(
    archive: zipfile.ZipFile,
) -> list[dict[str, Any]]:
    """Extract route evidence from compiled frontend JavaScript.

    The inventory intentionally records the HTTP method as UNKNOWN. A method
    is only known after observing the PHP request or a browser HAR.
    """

    routes: set[str] = set()
    for name in archive.namelist():
        normalized = name.replace("\\", "/")
        if "/static/js/" not in normalized or not normalized.endswith(".js"):
            continue
        source = archive.read(name).decode("utf-8", errors="ignore")
        for match in _API_ROUTE.finditer(source):
            route = match.group(0)
            routes.add(f"/apiv1/{route}")

    return [_route_record(path) for path in sorted(routes, key=lambda value: (value.casefold(), value))]


def write_frontend_api_inventory(
    archive_path: str | Path,
    output_path: str | Path,
) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        records = extract_frontend_api_routes(archive)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def merge_discovered_routes(
    manifest_path: str | Path,
    inventory_path: str | Path,
) -> int:
    manifest_file = Path(manifest_path)
    inventory_file = Path(inventory_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("contract manifest must be a JSON object")
    if not isinstance(inventory, list):
        raise ValueError("frontend route inventory must be a JSON array")

    discovered = manifest.get("discovered_routes")
    migrated = manifest.get("migrated_routes")
    if not isinstance(discovered, list) or not isinstance(migrated, list):
        raise ValueError("contract manifest route fields must be JSON arrays")

    known_paths = {
        route.get("path")
        for route in (*discovered, *migrated)
        if isinstance(route, dict)
    }
    additions = []
    for route in inventory:
        if not isinstance(route, dict) or not isinstance(route.get("path"), str):
            raise ValueError("frontend inventory contains an invalid route")
        if route["path"] in known_paths:
            continue
        additions.append(route)
        known_paths.add(route["path"])

    if additions:
        discovered.extend(additions)
        discovered.sort(key=lambda route: route["path"])
        manifest_file.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return len(additions)


def _route_record(path: str) -> dict[str, Any]:
    route = path.removeprefix("/apiv1/")
    controller, action = route.split("/", 1)
    return {
        "path": path,
        "normalized_path": path.lower(),
        "method": "UNKNOWN",
        "controller": controller,
        "action": action,
        "module": _module_for_route(route.lower()),
        "status": "discovered",
        "source": "frontend",
    }


def _module_for_route(route: str) -> str:
    for prefix, module in _MODULE_PREFIXES:
        if route.startswith(prefix):
            return module
    raise ValueError(f"unclassified legacy route: {route}")


_ORDER_WRITE_ACTIONS = {
    "add",
    "addfollow",
    "batchaddfollow",
    "batchallocation",
    "batchallocationmaintenance",
    "batchchangeanchor",
    "batchchangeconsole",
    "batchchangefollowstatus",
    "changestatus",
    "changecostinfo",
    "claim",
    "confirm",
    "del",
    "edit",
    "publicbatchallocation",
    "release",
    "setfollowday",
    "updatefollowstatus",
    "updatelockflg",
    "updatememo",
    "updatetel",
}

_WRITE_ACTIONS = _ORDER_WRITE_ACTIONS | {
    "addseat",
    "change",
    "changenoticeflg",
    "changeview",
    "changerenewstatus",
    "changestatus",
    "changecustomstatus",
    "changepwd",
    "consoleendwork",
    "consolestartwork",
    "createcall",
    "delseat",
    "delwechat",
    "editseat",
    "productadd",
    "productadd2",
    "productdel",
    "productedit",
    "productedit2",
    "productupdateorder",
    "send",
    "sendsms",
    "setsystemupnum",
    "setworktime",
    "startwork",
    "endwork",
    "updateauthinfo",
    "updateconfiginfo",
    "updatemobilecheckinfo",
    "updatesmsinfo",
    "updatesmstemplete",
    "updatewechat",
}


def classify_route(route: Mapping[str, Any]) -> str:
    """Return the migration work category for a discovered route."""

    path = str(route.get("path", "")).removeprefix("/apiv1/").lower()
    module = str(route.get("module", "")).lower()
    controller, _, action = path.partition("/")
    leaf = action.rsplit("/", 1)[-1]

    if path in {
        "common/captcha",
        "user/login",
        "user/logout",
        "user/register",
        "user/user/login",
        "user/user/logout",
        "user/user/register",
        "user/resettoken",
    }:
        return "authentication"
    if module == "organization":
        return "organization"
    if module == "live":
        return "live"
    if module == "finance":
        return "finance_read"
    if module == "order":
        return "order_write" if leaf in _ORDER_WRITE_ACTIONS else "order_read"
    if controller == "user" and action.startswith("mobiles/"):
        return "system_integration"
    return "system_integration"


def route_operation(route: Mapping[str, Any]) -> str:
    """Classify a discovered route as authentication, read, or write."""

    if classify_route(route) == "authentication":
        return "authentication"
    path = str(route.get("path", "")).removeprefix("/apiv1/")
    leaf = path.rsplit("/", 1)[-1].lower()
    return "write" if leaf in _WRITE_ACTIONS else "read"


def build_interface_gap_matrix(
    manifest_path: str | Path,
    fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a read-only coverage matrix for discovered and migrated routes."""

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("contract manifest must be a JSON object")
    discovered = manifest.get("discovered_routes", [])
    migrated = manifest.get("migrated_routes", [])
    if not isinstance(discovered, list) or not isinstance(migrated, list):
        raise ValueError("contract manifest route fields must be JSON arrays")

    fixture_routes: set[str] = set()
    if fixture_path is not None:
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        if not isinstance(fixture, dict) or fixture.get("source") != "local-demo":
            raise ValueError("read model fixture source must be local-demo")
        routes = fixture.get("routes", {})
        if not isinstance(routes, dict):
            raise ValueError("read model fixture routes must be a JSON object")
        fixture_routes = {str(route).strip("/") for route in routes}

    entries: list[dict[str, Any]] = []
    for status, routes in (("discovered", discovered), ("migrated", migrated)):
        for route in routes:
            if not isinstance(route, dict) or not isinstance(route.get("path"), str):
                raise ValueError("contract manifest contains an invalid route")
            legacy_path = route["path"].removeprefix("/apiv1/")
            entries.append(
                {
                    "path": route["path"],
                    "method": route.get("method", "UNKNOWN"),
                    "controller": route.get("controller"),
                    "action": route.get("action"),
                    "module": route.get("module"),
                    "status": status,
                    "category": classify_route(route),
                    "operation": route_operation(route),
                    "fixture_covered": legacy_path in fixture_routes,
                }
            )
    entries.sort(key=lambda route: (route["path"].casefold(), route["path"]))
    discovered_count = len(discovered)
    migrated_count = len(migrated)
    fixture_count = sum(
        1 for route in entries if route["status"] == "discovered" and route["fixture_covered"]
    )
    category_totals: dict[str, dict[str, int]] = {}
    for route in entries:
        category = route["category"]
        totals = category_totals.setdefault(
            category,
            {"discovered": 0, "migrated": 0, "fixture_covered": 0},
        )
        totals[route["status"]] += 1
        if route["fixture_covered"]:
            totals["fixture_covered"] += 1
    for totals in category_totals.values():
        totals["pending_fixture"] = totals["discovered"] - totals["fixture_covered"]

    operation_totals = {
        operation: sum(1 for route in entries if route["operation"] == operation)
        for operation in ("authentication", "read", "write")
    }

    return {
        "totals": {
            "discovered": discovered_count,
            "migrated": migrated_count,
            "fixture_covered": fixture_count,
            "pending_fixture": discovered_count - fixture_count,
        },
        "fixture_routes_total": len(fixture_routes),
        "fixture_only_routes": sorted(
            fixture_routes
            - {
                route["path"].removeprefix("/apiv1/")
                for route in entries
            }
        ),
        "category_totals": category_totals,
        "operation_totals": operation_totals,
        "routes": entries,
    }


def write_interface_gap_matrix(
    manifest_path: str | Path,
    output_path: str | Path,
    fixture_path: str | Path | None = None,
) -> None:
    """Write a JSON coverage matrix without changing the manifest."""

    matrix = build_interface_gap_matrix(manifest_path, fixture_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract legacy API route evidence from a frontend archive"
    )
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--gap-output", type=Path)
    args = parser.parse_args(argv)

    if args.archive is not None:
        if args.output is None:
            parser.error("--output is required when an archive is provided")
        write_frontend_api_inventory(args.archive, args.output)
        if args.manifest:
            merge_discovered_routes(args.manifest, args.output)
    elif args.output is not None or args.manifest is None:
        parser.error("provide an archive with --output, or --manifest for gap analysis")

    if args.gap_output is not None:
        if args.manifest is None:
            parser.error("--manifest is required with --gap-output")
        write_interface_gap_matrix(args.manifest, args.gap_output, args.fixtures)
    elif args.fixtures is not None:
        parser.error("--fixtures requires --gap-output")

    if args.archive is None and args.gap_output is None:
        parser.error("nothing to do: provide an archive or --gap-output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
