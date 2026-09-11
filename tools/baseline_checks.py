from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


def inspect_wwwroot_zip(source_zip: Path) -> dict[str, object]:
    business_php_files: list[str] = []
    encrypted_php_files: list[str] = []
    business_sql_files: list[str] = []
    frontend_uses_absolute_api = False

    with ZipFile(source_zip) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.startswith("fendan.localhost.com/application/") and name.endswith(
                ".php"
            ):
                if "/api/controller/" in name or "/common/model/" in name:
                    business_php_files.append(name)
                    if not archive.read(info).startswith(b"<?php"):
                        encrypted_php_files.append(name)
            if name.endswith(".sql") and "/thinkphp/" not in name and "/vendor/" not in name:
                if not name.endswith("/application/admin/command/Install/fastadmin.sql"):
                    business_sql_files.append(name)
            if name.startswith("life.localhost.com/") and name.endswith(
                (".js", ".html")
            ):
                text = archive.read(info).decode("utf-8", errors="ignore")
                frontend_uses_absolute_api |= "BASE_API_URI= '//" in text

    blockers: list[str] = []
    if encrypted_php_files:
        blockers.append("encrypted_business_php")
    if not business_sql_files:
        blockers.append("missing_business_schema")

    return {
        "business_php_files": len(business_php_files),
        "encrypted_php_files": len(encrypted_php_files),
        "business_sql_files": business_sql_files,
        "frontend_uses_absolute_api": frontend_uses_absolute_api,
        "blockers": blockers,
    }
