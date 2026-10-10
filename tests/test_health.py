import httpx
import pytest

from app.api.health import require_loopback
from app.core.settings import Settings
from app.main import create_app


def local_app(settings: Settings):
    app = create_app(settings)
    app.dependency_overrides[require_loopback] = lambda: None
    return app


async def request(app, path: str, client=("127.0.0.1", 123)):
    transport = httpx.ASGITransport(app=app, client=client)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as http_client:
        return await http_client.get(path)


@pytest.mark.asyncio
async def test_live_health_is_available_without_database():
    app = local_app(
        Settings(
            app_env="test",
            database_url=None,
        )
    )

    response = await request(app, "/internal/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_health_reports_unconfigured_database():
    app = local_app(
        Settings(
            app_env="test",
            database_url=None,
        )
    )

    response = await request(app, "/internal/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "database is not configured"


@pytest.mark.asyncio
async def test_ready_health_checks_configured_sqlite_database():
    app = local_app(
        Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
        )
    )

    response = await request(app, "/internal/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok"},
    }


@pytest.mark.asyncio
async def test_internal_health_rejects_non_loopback_request():
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
        )
    )

    response = await request(app, "/internal/health/live", client=("10.0.0.8", 123))

    assert response.status_code == 403
    assert response.json()["detail"] == "internal endpoint is local-only"
