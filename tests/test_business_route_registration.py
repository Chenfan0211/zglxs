from app.api.migration import MigrationRegistry
from app.core.settings import Settings
from app.domain.routes import register_business_routes
from app.main import create_app


def test_business_route_registration_is_empty_without_verified_handlers():
    registry = MigrationRegistry()

    register_business_routes(registry, Settings(app_env="test"))

    assert registry.routes() == []


def test_create_app_invokes_business_route_registration(monkeypatch):
    calls = []

    def register(registry, settings):
        calls.append((registry, settings))

    monkeypatch.setattr("app.main.register_business_routes", register)
    settings = Settings(app_env="test", database_url=None)
    registry = MigrationRegistry()

    create_app(settings=settings, registry=registry)

    assert calls == [(registry, settings)]
