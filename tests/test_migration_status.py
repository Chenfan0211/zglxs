import httpx
import pytest

from app.api.health import require_loopback
from app.api.migration import MigrationRegistry
from app.core.settings import Settings
from app.main import create_app


async def request(app, path: str):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def probe(request):
    return {"ok": True}


@pytest.mark.asyncio
async def test_migration_status_reports_routes_and_fallback():
    registry = MigrationRegistry()
    registry.register("Common", "config", ["GET"], probe)
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url="http://127.0.0.1:18085",
        ),
        registry=registry,
    )
    app.dependency_overrides[require_loopback] = lambda: None

    response = await request(app, "/internal/migration/status")

    assert response.status_code == 200
    assert response.json() == {
        "migrated_route_count": 1,
        "fallback_enabled": True,
        "manifest_path": "contracts/api-manifest.json",
    }
