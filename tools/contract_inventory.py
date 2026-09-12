from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
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
            route = match.group(0).lower()
            routes.add(f"/apiv1/{route}")

    return [_route_record(path) for path in sorted(routes)]


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


def _route_record(path: str) -> dict[str, Any]:
    route = path.removeprefix("/apiv1/")
    controller, action = route.split("/", 1)
    return {
        "path": path,
        "method": "UNKNOWN",
        "controller": controller,
        "action": action,
        "module": _module_for_route(route),
        "status": "discovered",
        "source": "frontend",
    }


def _module_for_route(route: str) -> str:
    for prefix, module in _MODULE_PREFIXES:
        if route.startswith(prefix):
            return module
    raise ValueError(f"unclassified legacy route: {route}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract legacy API route evidence from a frontend archive"
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_frontend_api_inventory(args.archive, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
