import inspect
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.health import create_health_router, require_loopback
from app.api.migration import MigrationRegistry
from app.core.settings import Settings
from app.db.session import Database
from app.integrations.php_baseline import PhpBaselineProxy
from app.laike.client import HmacLaikeClient, LaikeClient
from app.laike.service import LaikeSyncService
from app.laike.webhook import create_laike_webhook_router


def create_app(
    settings: Settings | None = None,
    registry: MigrationRegistry | None = None,
    php_proxy: PhpBaselineProxy | None = None,
    laike_client: LaikeClient | None = None,
    laike_session_factory: Callable[[], Any] | None = None,
    laike_enqueuer: Callable[..., Any] | None = None,
    laike_service_factory: Callable[[], LaikeSyncService] | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    database = Database(resolved_settings.database_url)
    resolved_registry = registry or MigrationRegistry()
    resolved_php_proxy = php_proxy or (
        PhpBaselineProxy(
            resolved_settings.php_baseline_url,
            resolved_settings.php_baseline_timeout_seconds,
        )
        if resolved_settings.php_baseline_url
        else None
    )
    resolved_laike_client = laike_client or HmacLaikeClient(
        resolved_settings.laike_webhook_secret
    )
    resolved_session_factory = laike_session_factory or database.session

    def enqueue_laike_webhook(event_id: str, payload: dict[str, Any]) -> Any:
        from app.worker.laike_tasks import process_laike_webhook

        return process_laike_webhook.delay(event_id)

    resolved_laike_enqueuer = laike_enqueuer or enqueue_laike_webhook
    resolved_laike_service_factory = laike_service_factory or (
        lambda: LaikeSyncService(
            session_factory=resolved_session_factory,
            client=resolved_laike_client,
            settings=resolved_settings,
            enqueuer=resolved_laike_enqueuer,
        )
    )

    app = FastAPI(title="抖音订单管理系统 Python API")
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.migration_registry = resolved_registry
    app.state.php_baseline_proxy = resolved_php_proxy
    app.state.laike_client = resolved_laike_client
    app.state.laike_session_factory = resolved_session_factory
    app.state.laike_enqueuer = resolved_laike_enqueuer
    app.state.laike_service_factory = resolved_laike_service_factory
    app.include_router(create_health_router(database))
    app.include_router(create_laike_webhook_router())

    @app.get(
        "/internal/migration/status",
        dependencies=[],
    )
    async def migration_status(request: Request):
        require_loopback(request)
        return {
            "migrated_route_count": len(resolved_registry.routes()),
            "fallback_enabled": resolved_php_proxy is not None,
            "manifest_path": "contracts/api-manifest.json",
        }

    @app.api_route(
        "/apiv1/{controller}/{action}",
        methods=["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"],
    )
    async def migration_dispatch(
        request: Request,
        controller: str,
        action: str,
    ):
        handler = resolved_registry.resolve(controller, action, request.method)
        if handler is not None:
            result = handler(request)
            if inspect.isawaitable(result):
                result = await result
            return result
        if resolved_php_proxy is not None:
            return await resolved_php_proxy.forward(request, controller, action)
        return JSONResponse(
            status_code=404,
            content={"detail": "API route is not migrated"},
        )

    return app


app = create_app()
