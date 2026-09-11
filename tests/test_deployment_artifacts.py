from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_nginx_and_systemd_artifacts_match_test_deployment_ports():
    nginx = (ROOT / "deploy/nginx/douyin-order-python.conf").read_text(
        encoding="utf-8"
    )

    assert "listen 18084;" in nginx
    assert "proxy_pass http://127.0.0.1:18083;" in nginx
    assert "location /apiv1/" in nginx
    assert "location ~* /(?:\\.env|.*\\.log|.*\\.bak|.*\\.sql)" in nginx
    assert "18081" not in nginx
    assert "18082" not in nginx

    for service in (
        "douyin-order-api.service",
        "douyin-order-worker.service",
        "douyin-order-scheduler.service",
    ):
        text = (
            ROOT / "deploy/systemd" / service
        ).read_text(encoding="utf-8")
        assert "User=douyin-order" in text
        assert "WorkingDirectory=/srv/douyin-order-python/current" in text
        assert "Restart=always" in text


def test_release_scripts_require_a_release_and_support_rollback():
    publish = (ROOT / "deploy/scripts/publish.sh").read_text(encoding="utf-8")
    rollback = (ROOT / "deploy/scripts/rollback.sh").read_text(encoding="utf-8")

    assert "releases/" in publish
    assert "ln -sfn" in publish
    assert "nginx -t" in publish
    assert "systemctl reload nginx" in publish
    assert "current" in rollback
    assert "readlink" in rollback


def test_deployment_check_script_probes_frontend_api_and_internal_endpoints():
    check = (ROOT / "deploy/scripts/check-deploy.sh").read_text(
        encoding="utf-8"
    )

    assert "18084" in check
    assert "/internal/health/live" in check
    assert "/internal/migration/status" in check
    assert "curl" in check
