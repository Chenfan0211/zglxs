from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.contracts import ContractCase
from app.core.settings import Settings
from tools.contract_inventory import (
    extract_frontend_api_routes,
    write_frontend_api_inventory,
)


ARCHIVE = Path(r"C:\Users\Administrator\OneDrive\Desktop\wwwroot.zip")


def test_settings_keep_formal_migration_modules_disabled_by_default():
    settings = Settings(_env_file=None)

    assert settings.migration_organization_enabled is False
    assert settings.migration_live_enabled is False
    assert settings.migration_order_enabled is False
    assert settings.migration_finance_enabled is False
    assert settings.migration_system_enabled is False
    assert settings.formal_migration_enabled("order") is False


def test_settings_enable_only_the_requested_formal_migration_module():
    settings = Settings(
        _env_file=None,
        migration_order_enabled=True,
        migration_finance_enabled=False,
    )

    assert settings.formal_migration_enabled("order") is True
    assert settings.formal_migration_enabled("finance") is False

    with pytest.raises(ValueError, match="unknown migration module"):
        settings.formal_migration_enabled("unknown")


def test_contract_case_serializes_a_legacy_request_without_sensitive_values():
    case = ContractCase(
        request_id="demo-organization-001",
        method="POST",
        controller="user",
        action="staff/index",
        query={"page": 1},
        path={},
        body={"status": "active"},
        headers={"X-Demo": "1"},
        cookies={"session": "[REDACTED]"},
    )

    assert case.to_record() == {
        "request_id": "demo-organization-001",
        "method": "POST",
        "controller": "user",
        "action": "staff/index",
        "request": {
            "query": {"page": 1},
            "path": {},
            "body": {"status": "active"},
            "headers": {"X-Demo": "1"},
            "cookies": {"session": "[REDACTED]"},
        },
    }
    assert "password" not in json.dumps(case.to_record()).lower()


@pytest.mark.skipif(not ARCHIVE.exists(), reason="local wwwroot archive is unavailable")
def test_frontend_inventory_extracts_real_legacy_routes_from_archive():
    with zipfile.ZipFile(ARCHIVE) as archive:
        routes = extract_frontend_api_routes(archive)

    paths = {route["path"] for route in routes}
    assert "/apiv1/user/departments/index" in paths
    assert "/apiv1/user/staff/index" in paths
    assert "/apiv1/user/order/tradelist" in paths
    assert "/apiv1/financial/statistic" in paths
    assert "/apiv1/console/center" in paths
    assert all(path.startswith("/apiv1/") for path in paths)
    assert all("packages/" not in path for path in paths)


def test_frontend_inventory_preserves_route_shape_without_registering_migration():
    with zipfile.ZipFile(ARCHIVE) as archive:
        routes = extract_frontend_api_routes(archive)

    staff_index = next(
        route for route in routes if route["path"] == "/apiv1/user/staff/index"
    )
    assert staff_index["controller"] == "user"
    assert staff_index["action"] == "staff/index"
    assert staff_index["method"] == "UNKNOWN"
    assert staff_index["status"] == "discovered"


def test_frontend_inventory_writer_outputs_json_without_promoting_routes(tmp_path):
    archive_path = tmp_path / "wwwroot.zip"
    output_path = tmp_path / "frontend-routes.json"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "life.localhost.com/static/js/app.js",
            'request("user/staff/index"); request("user/order/tradelist");',
        )

    write_frontend_api_inventory(archive_path, output_path)

    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert [record["path"] for record in records] == [
        "/apiv1/user/order/tradelist",
        "/apiv1/user/staff/index",
    ]
    assert all(record["status"] == "discovered" for record in records)
