from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.settings import Settings
from app.main import create_app
from tools.contract_inventory import route_operation


ROOT = Path(__file__).parents[1]


def _routes(operation: str) -> list[str]:
    manifest = json.loads(
        (ROOT / "contracts/api-manifest.json").read_text(encoding="utf-8")
    )
    return [
        route["path"]
        for route in manifest["discovered_routes"]
        if route_operation(route) == operation
    ]


def _app():
    return create_app(
        Settings(
            _env_file=None,
            app_env="test",
            environment="test",
            database_url=None,
            demo_login_enabled=True,
        )
    )


async def _post(app, path: str):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            path,
            json={},
            headers={"authorization": "Bearer DEMO-local-token"},
        )


@pytest.mark.asyncio
async def test_all_discovered_write_routes_are_implemented():
    app = _app()
    routes = _routes("write")

    assert len(routes) == 90
    for path in routes:
        response = await _post(app, path)
        # 所有写路由均已由业务模块接管，不再返回 404 未迁移
        assert response.status_code != 404, path
