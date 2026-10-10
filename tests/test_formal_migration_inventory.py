from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.contracts import ContractCase
from app.core.settings import Settings
from tools.contract_inventory import (
    build_interface_gap_matrix,
    classify_route,
    extract_frontend_api_routes,
    merge_discovered_routes,
    route_operation,
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
    assert staff_index["module"] == "organization"
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


def test_frontend_inventory_preserves_exact_route_casing(tmp_path):
    archive_path = tmp_path / "wwwroot.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "life.localhost.com/static/js/app.js",
            (
                'request("user/getInfo"); request("user/getinfo"); '
                'request("user/resetToken"); request("user/setSystemUpNum");'
            ),
        )

    with zipfile.ZipFile(archive_path) as archive:
        records = extract_frontend_api_routes(archive)

    by_path = {record["path"]: record for record in records}
    assert set(by_path) == {
        "/apiv1/user/getInfo",
        "/apiv1/user/getinfo",
        "/apiv1/user/resetToken",
        "/apiv1/user/setSystemUpNum",
    }
    assert by_path["/apiv1/user/getInfo"]["action"] == "getInfo"
    assert by_path["/apiv1/user/getInfo"]["normalized_path"] == (
        "/apiv1/user/getinfo"
    )
    assert by_path["/apiv1/user/resetToken"]["normalized_path"] == (
        "/apiv1/user/resettoken"
    )


def test_merge_discovered_routes_is_idempotent_and_never_promotes(tmp_path):
    manifest_path = tmp_path / "api-manifest.json"
    inventory_path = tmp_path / "frontend-route-inventory.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 2,
                "migrated_routes": [],
                "discovered_routes": [],
            }
        ),
        encoding="utf-8",
    )
    inventory_path.write_text(
        json.dumps(
            [
                {
                    "path": "/apiv1/user/staff/index",
                    "method": "UNKNOWN",
                    "controller": "user",
                    "action": "staff/index",
                    "module": "organization",
                    "status": "discovered",
                    "source": "frontend",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert merge_discovered_routes(manifest_path, inventory_path) == 1
    assert merge_discovered_routes(manifest_path, inventory_path) == 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["migrated_routes"] == []
    assert manifest["discovered_routes"] == [
        {
            "path": "/apiv1/user/staff/index",
            "method": "UNKNOWN",
            "controller": "user",
            "action": "staff/index",
            "module": "organization",
            "status": "discovered",
            "source": "frontend",
        }
    ]


@pytest.mark.parametrize(
    ("path", "module", "expected"),
    [
        ("/apiv1/user/user/login", "organization", "authentication"),
        ("/apiv1/user/staff/index", "organization", "organization"),
        ("/apiv1/console/center", "live", "live"),
        ("/apiv1/user/order/tradelist", "order", "order_read"),
        ("/apiv1/user/order/claim", "order", "order_write"),
        ("/apiv1/financial/statistic", "finance", "finance_read"),
        ("/apiv1/user/mobiles/calllog", "system", "system_integration"),
    ],
)
def test_classify_route_builds_stable_migration_categories(path, module, expected):
    assert classify_route({"path": path, "module": module}) == expected


def test_gap_matrix_reports_fixture_coverage_without_promoting_routes(tmp_path):
    manifest_path = tmp_path / "api-manifest.json"
    fixture_path = tmp_path / "read-model.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 2,
                "migrated_routes": [],
                "discovered_routes": [
                    {
                        "path": "/apiv1/user/staff/index",
                        "method": "UNKNOWN",
                        "controller": "user",
                        "action": "staff/index",
                        "module": "organization",
                        "status": "discovered",
                        "source": "frontend",
                    },
                    {
                        "path": "/apiv1/user/order/claim",
                        "method": "UNKNOWN",
                        "controller": "user",
                        "action": "order/claim",
                        "module": "order",
                        "status": "discovered",
                        "source": "frontend",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    fixture_path.write_text(
        json.dumps(
            {
                "version": 1,
                "source": "local-demo",
                "routes": {"user/staff/index": {"status_code": 200, "body": {}}},
            }
        ),
        encoding="utf-8",
    )

    matrix = build_interface_gap_matrix(manifest_path, fixture_path)

    assert matrix["totals"] == {
        "discovered": 2,
        "migrated": 0,
        "fixture_covered": 1,
        "pending_fixture": 1,
    }
    routes = {route["path"]: route for route in matrix["routes"]}
    assert routes["/apiv1/user/staff/index"]["category"] == "organization"
    assert routes["/apiv1/user/staff/index"]["fixture_covered"] is True
    assert routes["/apiv1/user/order/claim"]["category"] == "order_write"
    assert routes["/apiv1/user/order/claim"]["fixture_covered"] is False


@pytest.mark.parametrize(
    ("path", "module", "expected"),
    [
        ("/apiv1/user/user/login", "organization", "authentication"),
        ("/apiv1/user/staff/index", "organization", "read"),
        ("/apiv1/user/staff/updateauthinfo", "organization", "write"),
        ("/apiv1/console/liveroomrank", "live", "read"),
        ("/apiv1/console/startwork", "live", "write"),
        ("/apiv1/user/order/refundlist", "order", "read"),
        ("/apiv1/user/order/claim", "order", "write"),
        ("/apiv1/financial/statistic", "finance", "read"),
        ("/apiv1/user/mobiles/sendsms", "system", "write"),
    ],
)
def test_route_operation_separates_read_write_and_authentication(
    path, module, expected
):
    assert route_operation({"path": path, "module": module}) == expected


def test_repository_manifest_has_68_read_routes_and_no_formal_migrations():
    root = Path(__file__).parents[1]
    matrix = build_interface_gap_matrix(
        root / "contracts/api-manifest.json",
        root / "contracts/fixtures/read-model.json",
    )

    assert matrix["operation_totals"] == {
        "authentication": 8,
        "read": 68,
        "write": 90,
    }
    assert matrix["totals"]["migrated"] == 0
    assert all("operation" in route for route in matrix["routes"])
