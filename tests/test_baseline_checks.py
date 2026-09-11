from pathlib import Path
from zipfile import ZipFile

from tools.baseline_checks import inspect_wwwroot_zip


def test_inspect_wwwroot_zip_reports_missing_schema_and_encrypted_php(tmp_path: Path):
    source = tmp_path / "wwwroot.zip"
    encrypted = b"\x15\x0c\x00not-php"
    with ZipFile(source, "w") as archive:
        archive.writestr("fendan.localhost.com/application/api/controller/v1/Common.php", encrypted)
        archive.writestr("fendan.localhost.com/application/admin/command/Install/fastadmin.sql", "-- framework")
        archive.writestr(
            "life.localhost.com/js/config.js",
            "var BASE_API_URI= '//111.230.104.153:8090/apiv1'",
        )

    report = inspect_wwwroot_zip(source)

    assert report["business_php_files"] == 1
    assert report["encrypted_php_files"] == 1
    assert report["business_sql_files"] == []
    assert report["frontend_uses_absolute_api"] is True
    assert "missing_business_schema" in report["blockers"]
    assert "encrypted_business_php" in report["blockers"]


def test_checked_in_baseline_inventory_contains_no_credentials():
    inventory = (
        Path(__file__).parents[1] / "contracts/baseline-inventory.json"
    ).read_text(encoding="utf-8")

    assert "password" not in inventory.lower()
    assert "token" not in inventory.lower()
    assert '"business_php_files": 61' in inventory
