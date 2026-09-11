import json
import subprocess
import sys
from pathlib import Path

from tools.contract_tools import ContractMismatch, compare_recordings


ROOT = Path(__file__).parents[1]


def test_compare_recordings_reports_case_insensitive_header_mismatch():
    php = {
        "status_code": 200,
        "headers": {
            "Content-Type": "application/json",
            "X-Request-Id": "php-request",
        },
        "body": {"ok": True},
    }
    python = {
        "status_code": 200,
        "headers": {
            "content-type": "application/json",
            "x-request-id": "python-request",
        },
        "body": {"ok": True},
    }

    assert compare_recordings(php, python, {}) == [
        ContractMismatch(
            kind="response.headers",
            expected={
                "content-type": "application/json",
                "x-request-id": "php-request",
            },
            actual={
                "content-type": "application/json",
                "x-request-id": "python-request",
            },
        )
    ]


def test_compare_recordings_normalizes_headers_and_database_effects():
    php = {
        "status_code": 200,
        "headers": {
            "X-Request-Id": "php-request",
            "Content-Type": "application/json",
        },
        "body": {"ok": True},
        "database": {"updated_at": "php-time"},
    }
    python = {
        "status_code": 200,
        "headers": {
            "x-request-id": "python-request",
            "content-type": "application/json",
        },
        "body": {"ok": True},
        "database": {"updated_at": "python-time"},
    }

    assert compare_recordings(
        php,
        python,
        {
            "replace_paths": {
                "$.x-request-id": "<request-id>",
                "$.updated_at": "<timestamp>",
            }
        },
    ) == []


def test_compare_recordings_treats_missing_headers_as_empty():
    php = {"status_code": 204, "body": None}
    python = {"status_code": 204, "headers": {}, "body": None}

    assert compare_recordings(php, python, {}) == []


def test_cli_keeps_zero_for_match_and_one_for_mismatch(tmp_path: Path):
    php_path = tmp_path / "php.jsonl"
    python_path = tmp_path / "python.jsonl"
    php_path.write_text(
        json.dumps(
            {
                "request_id": "request-1",
                "status_code": 200,
                "headers": {"X-Trace": "same"},
                "body": {"ok": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    python_path.write_text(
        json.dumps(
            {
                "request_id": "request-1",
                "status_code": 200,
                "headers": {"x-trace": "same"},
                "body": {"ok": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        "-m",
        "tools.compare_contracts",
        "--php",
        str(php_path),
        "--python",
        str(python_path),
    ]
    assert subprocess.run(command, cwd=ROOT, check=False).returncode == 0

    python_path.write_text(
        python_path.read_text(encoding="utf-8").replace("same", "different"),
        encoding="utf-8",
    )
    assert subprocess.run(command, cwd=ROOT, check=False).returncode == 1


def test_laike_units_use_shared_environment_file_for_all_switches():
    env_example = (ROOT / "deploy/env/api.env.example").read_text(encoding="utf-8")
    required = (
        "LAIKE_WEBHOOK_ENABLED",
        "LAIKE_RECONCILE_ENABLED",
        "LAIKE_WRITE_ENABLED",
        "LAIKE_SYNC_MODE",
    )

    for key in required:
        assert f"{key}=" in env_example

    for service in ("douyin-order-worker.service", "douyin-order-scheduler.service"):
        text = (ROOT / "deploy/systemd" / service).read_text(encoding="utf-8")
        assert (
            "EnvironmentFile=/srv/douyin-order-python/shared/env/api.env" in text
        )
        for key in required:
            assert key in text
        assert "Environment=LAIKE_" not in text


def test_deployment_check_has_disabled_webhook_post_safety_probe():
    text = (ROOT / "deploy/scripts/check-deploy.sh").read_text(encoding="utf-8")

    assert "-X POST" in text
    assert "/internal/laike/webhook" in text
    assert "LAIKE_WEBHOOK_ENABLED" in text
    assert "--data '{}'" in text
    assert "signature" not in text.lower()
    assert "order_id" not in text.lower()


def test_docs_declare_external_prerequisites_safe_defaults_and_manifest_gate():
    docs = "\n".join(
        (
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs/migration-status.md").read_text(encoding="utf-8"),
            (ROOT / "contracts/README.md").read_text(encoding="utf-8"),
        )
    )

    for declaration in (
        "真实 PHP 基线",
        "脱敏业务数据库快照",
        "真实 HAR",
        "真实 Webhook 路径",
        "真实签名",
        "事件 ID",
        "订单 ID",
        "测试凭据",
        "migrated_routes 保持为空",
        "PHP/Python 回放和数据库副作用比较全部通过",
        "LAIKE_SYNC_MODE=observe",
        "LAIKE_WEBHOOK_ENABLED=false",
        "LAIKE_RECONCILE_ENABLED=false",
        "LAIKE_WRITE_ENABLED=false",
    ):
        assert declaration in docs

    assert "Bearer " not in docs
    assert "phone=" not in docs.lower()
    assert "address=" not in docs.lower()
