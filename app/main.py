from fastapi import FastAPI

from app.api.health import create_health_router
from app.core.settings import Settings
from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    database = Database(resolved_settings.database_url)

    app = FastAPI(title="抖音订单管理系统 Python API")
    app.state.settings = resolved_settings
    app.state.database = database
    app.include_router(create_health_router(database))
    return app


app = create_app()
