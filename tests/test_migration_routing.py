import httpx
import pytest

from app.api.migration import MigrationRegistry
from app.core.settings import Settings
from app.main import create_app


async def request(
    app,
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            headers=headers,
            content=content,
        )


async def python_probe(request):
    return {"source": "python"}


def test_registry_resolves_registered_method_only():
    registry = MigrationRegistry()
    registry.register("Demo", "probe", ["GET"], python_probe)

    assert registry.resolve("Demo", "probe", "GET") is python_probe
    assert registry.resolve("Demo", "probe", "POST") is None


def test_registry_does_not_resolve_a_route_when_its_module_is_disabled():
    registry = MigrationRegistry(module_enabled=lambda module: False)
    registry.register("Demo", "probe", ["GET"], python_probe, module="order")

    assert registry.resolve("Demo", "probe", "GET") is None
    assert registry.routes() == [
        {
            "controller": "Demo",
            "action": "probe",
            "method": "GET",
            "module": "order",
        }
    ]


def test_registry_resolves_a_route_when_its_module_is_enabled():
    registry = MigrationRegistry(module_enabled=lambda module: module == "order")
    registry.register("Demo", "probe", ["GET"], python_probe, module="order")

    assert registry.resolve("Demo", "probe", "GET") is python_probe


@pytest.mark.asyncio
async def test_registered_route_is_handled_by_python():
    registry = MigrationRegistry()
    registry.register("Demo", "probe", ["GET"], python_probe)
    app = create_app(
        Settings(app_env="test", database_url=None),
        registry=registry,
    )

    response = await request(app, "/apiv1/Demo/probe")

    assert response.status_code == 200
    assert response.json() == {"source": "python"}


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_unregistered_route_without_php_baseline_returns_not_migrated():
    app = create_app(Settings(app_env="test", database_url=None))

    response = await request(app, "/apiv1/Demo/list")

    assert response.status_code == 404
    assert response.json() == {
        "code": 0,
        "msg": "接口尚未迁移",
        "data": None,
    }


@pytest.mark.asyncio
async def test_configured_php_baseline_is_ignored_at_runtime():
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
        )
    )

    response = await request(app, "/apiv1/Demo/list")

    assert response.status_code == 404
    assert response.json() == {
        "code": 0,
        "msg": "接口尚未迁移",
        "data": None,
    }


@pytest.mark.asyncio
async def test_nested_unregistered_route_returns_the_same_legacy_error_envelope():
    app = create_app(Settings(app_env="test", database_url=None))

    response = await request(app, "/apiv1/user/departments/index")

    assert response.status_code == 404
    assert response.json() == {
        "code": 0,
        "msg": "接口尚未迁移",
        "data": None,
    }
