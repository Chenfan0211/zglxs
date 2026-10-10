from pathlib import Path


ROOT = Path(__file__).parents[1]


def _runtime_text_files() -> list[Path]:
    roots = [ROOT / "app", ROOT / "frontend", ROOT / "deploy", ROOT / "tools"]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and "node_modules" not in path.parts
            and "dist" not in path.parts
            and path.suffix.lower() in {".py", ".js", ".json", ".html", ".css"}
        )
    return files


def test_runtime_surfaces_have_no_php_proxy_or_remote_business_endpoint():
    forbidden = (
        "PhpBaselineProxy",
        "PHP_BASELINE_URL",
        "111.230.104.153",
        "192.168.28.188",
        "18082",
    )

    violations = []
    for path in _runtime_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for value in forbidden:
            if value.casefold() in text.casefold():
                violations.append(f"{path}: {value}")

    assert violations == []


def test_contract_inventory_cli_writes_gap_matrix_without_promoting(tmp_path):
    from tools.contract_inventory import main
    import json

    manifest = tmp_path / "manifest.json"
    fixtures = tmp_path / "read-model.json"
    output = tmp_path / "gap.json"
    manifest.write_text(
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
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    fixtures.write_text(
        json.dumps(
            {"version": 1, "source": "local-demo", "routes": {"user/staff/index": {}}}
        ),
        encoding="utf-8",
    )

    assert main(
        [
            "--manifest",
            str(manifest),
            "--fixtures",
            str(fixtures),
            "--gap-output",
            str(output),
        ]
    ) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["totals"] == {
        "discovered": 1,
        "migrated": 0,
        "fixture_covered": 1,
        "pending_fixture": 0,
    }
    assert json.loads(manifest.read_text(encoding="utf-8"))["migrated_routes"] == []

