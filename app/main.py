import inspect

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.health import create_health_router
from app.api.migration import MigrationRegistry
from app.core.settings import Settings
from app.db.session import Database
from app.integrations.php_baseline import PhpBaselineProxy


def create_app(
    settings: Settings | None = None,
    registry: MigrationRegistry | None = None,
    php_proxy: PhpBaselineProxy | None = None,
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

    app = FastAPI(title="抖音订单管理系统 Python API")
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.migration_registry = resolved_registry
    app.state.php_baseline_proxy = resolved_php_proxy
    app.include_router(create_health_router(database))

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
