from __future__ import annotations

import json
from pathlib import Path

from app.core.settings import Settings
from app.laike.client import DouyinLaikeClient
from app.main import create_app


ROOT = Path(__file__).parents[1]


def test_official_laike_fixtures_are_redacted_and_use_demo_identifiers():
    fixture_dir = ROOT / "contracts/fixtures/laike"
    token_rows = [
        json.loads(line)
        for line in (fixture_dir / "douyin-token.jsonl").read_text().splitlines()
        if line.strip()
    ]
    order_rows = [
        json.loads(line)
        for line in (fixture_dir / "douyin-order-query.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]

    assert token_rows[0]["request"]["client_key"] == "[REDACTED]"
    assert token_rows[0]["request"]["client_secret"] == "[REDACTED]"
    assert token_rows[0]["response"]["data"]["access_token"] == "[REDACTED]"
    order = order_rows[0]["response"]["data"]["orders"][0]
    assert order["order_id"].startswith("DEMO-")
    assert order["products"][0]["product_id"].startswith("DEMO-")


def test_official_settings_keep_safe_defaults_and_never_reuse_business_database():
    settings = Settings(_env_file=None)

    assert settings.laike_base_url == "https://open.douyin.com"
    assert settings.laike_orders_path == "/goodlife/v1/trade/order/query/"
    assert settings.laike_database_url is None
    assert settings.laike_sync_mode == "observe"
    assert settings.laike_reconcile_enabled is False


def test_app_uses_official_client_and_independent_sync_database():
    app = create_app(
        Settings(
            _env_file=None,
            database_url="sqlite+pysqlite:///business.db",
            laike_database_url="sqlite+pysqlite:///laike.db",
            laike_app_id="DEMO-APP",
            laike_app_secret="DEMO-SECRET",
        )
    )

    assert isinstance(app.state.laike_client, DouyinLaikeClient)
    assert app.state.database.database_url != app.state.laike_database.database_url
