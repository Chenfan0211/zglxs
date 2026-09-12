import inspect
from collections.abc import Callable
from typing import Any

from celery import Celery
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import create_health_router, require_loopback
from app.api.migration import MigrationRegistry
from app.api.demo_auth import create_demo_auth_router
from app.api.demo_dashboard import create_demo_dashboard_router
from app.core.settings import Settings
from app.db.session import Database
from app.integrations.php_baseline import PhpBaselineProxy
from app.laike.client import HmacLaikeClient, LaikeClient
from app.laike.normalizer import normalize_order
from app.laike.service import LaikeSyncService
from app.laike.webhook import WebhookVerifier, create_laike_webhook_router
from app.worker.celery_app import create_celery_app


def create_app(
    settings: Settings | None = None,
    registry: MigrationRegistry | None = None,
    php_proxy: PhpBaselineProxy | None = None,
    laike_client: LaikeClient | None = None,
    laike_session_factory: Callable[[], Any] | None = None,
    laike_enqueuer: Callable[..., Any] | None = None,
    laike_task_app: Celery | None = None,
    laike_enqueuer_factory: Callable[[Celery], Callable[..., Any]] | None = None,
    laike_service_factory: Callable[[], LaikeSyncService] | None = None,
    laike_normalizer: Callable[..., Any] | None = None,
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
    resolved_webhook_verifier = WebhookVerifier(
        resolved_settings.laike_webhook_secret,
        signature_header=resolved_settings.laike_webhook_signature_header,
        event_id_header=resolved_settings.laike_webhook_event_id_header,
    )
    resolved_laike_client = laike_client or HmacLaikeClient(
        resolved_settings.laike_webhook_secret,
        verifier=resolved_webhook_verifier,
    )
    resolved_session_factory = laike_session_factory or database.session
    resolved_laike_task_app = laike_task_app or create_celery_app(
        settings=resolved_settings
    )

    def enqueue_laike_webhook(event_id: str, payload: dict[str, Any]) -> Any:
        return resolved_laike_task_app.send_task(
            "process_laike_webhook",
            args=(event_id,),
        )

    resolved_laike_enqueuer = (
        laike_enqueuer
        or (
            laike_enqueuer_factory(resolved_laike_task_app)
            if laike_enqueuer_factory is not None
            else enqueue_laike_webhook
        )
    )
    resolved_laike_service_factory = laike_service_factory or (
        lambda: LaikeSyncService(
            session_factory=resolved_session_factory,
            client=resolved_laike_client,
            settings=resolved_settings,
            enqueuer=resolved_laike_enqueuer,
            normalizer=(
                laike_normalizer
                if laike_normalizer is not None
                else normalize_order
            ),
        )
    )

    app = FastAPI(title="抖音订单管理系统 Python API")
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.migration_registry = resolved_registry
    app.state.php_baseline_proxy = resolved_php_proxy
    app.state.laike_client = resolved_laike_client
    app.state.laike_session_factory = resolved_session_factory
    app.state.laike_task_app = resolved_laike_task_app
    app.state.laike_enqueuer = resolved_laike_enqueuer
    app.state.laike_service_factory = resolved_laike_service_factory
    app.include_router(create_health_router(database))
    app.include_router(create_laike_webhook_router())
    app.include_router(create_demo_auth_router(resolved_settings))
    app.include_router(create_demo_dashboard_router(resolved_settings))

    @app.exception_handler(StarletteHTTPException)
    async def legacy_http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "请求失败"
        if request.url.path.startswith("/apiv1/") and detail == "Not Found":
            detail = "API route is not migrated"
        messages = {
            "API route is not migrated": "接口尚未迁移",
            "PHP baseline unavailable": "PHP baseline unavailable",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": 0,
                "msg": messages.get(detail, detail),
                "data": None,
                "detail": detail,
            },
            headers=exc.headers,
        )

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
        "/apiv1/{controller}/{action:path}",
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
            content={
                "code": 0,
                "msg": "接口尚未迁移",
                "data": None,
                "detail": "API route is not migrated",
            },
        )

    return app


app = create_app()
