import httpx
import pytest
from fastapi import Response

from app.api.migration import MigrationRegistry
from app.core.settings import Settings
from app.integrations.php_baseline import PhpBaselineProxy
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


class FakePhpProxy:
    async def forward(self, request, controller, action):
        return Response(
            content=b'{"source":"php","controller":"Demo","action":"list"}',
            media_type="application/json",
            status_code=201,
        )


def test_registry_resolves_registered_method_only():
    registry = MigrationRegistry()
    registry.register("Demo", "probe", ["GET"], python_probe)

    assert registry.resolve("Demo", "probe", "GET") is python_probe
    assert registry.resolve("Demo", "probe", "POST") is None


@pytest.mark.asyncio
async def test_registered_route_is_handled_by_python():
    registry = MigrationRegistry()
    registry.register("Demo", "probe", ["GET"], python_probe)
    app = create_app(
        Settings(app_env="test", database_url=None, php_baseline_url=None),
        registry=registry,
    )

    response = await request(app, "/apiv1/Demo/probe")

    assert response.status_code == 200
    assert response.json() == {"source": "python"}


@pytest.mark.asyncio
async def test_unregistered_route_falls_back_to_php_proxy():
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url="http://127.0.0.1:18085",
            php_baseline_timeout_seconds=1,
        ),
        php_proxy=FakePhpProxy(),
    )

    response = await request(app, "/apiv1/Demo/list")

    assert response.status_code == 201
    assert response.json()["source"] == "php"


@pytest.mark.asyncio
async def test_unregistered_route_without_php_baseline_returns_not_migrated():
    app = create_app(
        Settings(app_env="test", database_url=None, php_baseline_url=None)
    )

    response = await request(app, "/apiv1/Demo/list")

    assert response.status_code == 404
    assert response.json() == {
        "code": 0,
        "msg": "接口尚未迁移",
        "data": None,
        "detail": "API route is not migrated",
    }


@pytest.mark.asyncio
async def test_nested_unregistered_route_returns_the_same_legacy_error_envelope():
    app = create_app(
        Settings(app_env="test", database_url=None, php_baseline_url=None)
    )

    response = await request(app, "/apiv1/user/departments/index")

    assert response.status_code == 404
    assert response.json() == {
        "code": 0,
        "msg": "接口尚未迁移",
        "data": None,
        "detail": "API route is not migrated",
    }


@pytest.mark.asyncio
async def test_php_proxy_preserves_request_and_upstream_response():
    seen = {}

    async def upstream(request):
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = await request.aread()
        return httpx.Response(
            202,
            headers={"content-type": "application/json"},
            content=b'{"source":"php"}',
        )

    proxy = PhpBaselineProxy(
        "http://127.0.0.1:18085",
        timeout=1,
        transport=httpx.MockTransport(upstream),
    )
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url="http://127.0.0.1:18085",
            php_baseline_timeout_seconds=1,
        ),
        php_proxy=proxy,
    )

    response = await request(
        app,
        "/apiv1/Demo/list?status=1",
        method="POST",
        headers={"authorization": "Bearer DEMO"},
        content=b'{"id":"DEMO-1"}',
    )

    assert response.status_code == 202
    assert response.json() == {"source": "php"}
    assert seen == {
        "method": "POST",
        "url": "http://127.0.0.1:18085/apiv1/Demo/list?status=1",
        "authorization": "Bearer DEMO",
        "body": b'{"id":"DEMO-1"}',
    }


@pytest.mark.asyncio
async def test_php_proxy_preserves_response_headers_and_cookies():
    async def upstream(request):
        return httpx.Response(
            200,
            headers=[
                ("content-type", "application/json"),
                ("set-cookie", "session_id=PHP-DEMO; Path=/; HttpOnly"),
                ("x-baseline-route", "Demo/list"),
            ],
            content=b'{"source":"php"}',
        )

    proxy = PhpBaselineProxy(
        "http://127.0.0.1:18085",
        timeout=1,
        transport=httpx.MockTransport(upstream),
    )
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url="http://127.0.0.1:18085",
            php_baseline_timeout_seconds=1,
        ),
        php_proxy=proxy,
    )

    response = await request(app, "/apiv1/Demo/list")

    assert response.status_code == 200
    assert response.headers["x-baseline-route"] == "Demo/list"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-length"] == "16"
    assert response.cookies["session_id"] == "PHP-DEMO"


@pytest.mark.asyncio
async def test_php_proxy_returns_stable_error_when_baseline_is_unavailable():
    async def upstream(request):
        raise httpx.ConnectError("offline", request=request)

    proxy = PhpBaselineProxy(
        "http://127.0.0.1:18085",
        timeout=1,
        transport=httpx.MockTransport(upstream),
    )
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url="http://127.0.0.1:18085",
            php_baseline_timeout_seconds=1,
        ),
        php_proxy=proxy,
    )

    response = await request(app, "/apiv1/Demo/list")

    assert response.status_code == 502
    assert response.json() == {
        "code": 0,
        "msg": "PHP baseline unavailable",
        "data": None,
        "detail": "PHP baseline unavailable",
    }
