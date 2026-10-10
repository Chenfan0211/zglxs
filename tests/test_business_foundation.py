from __future__ import annotations

from collections.abc import Mapping

import httpx
import pytest
from fastapi import Depends, FastAPI, Request
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.auth import (
    AuthContext,
    RequestAuth,
    require_permission,
)
from app.api.responses import ApiEnvelope, failure, success
from app.core.settings import Settings
from app.db.repository import SqlAlchemyRepository
from app.db.session import UnitOfWork
from app.worker.celery_app import create_celery_app


class FakeValidator:
    def __init__(self, context: AuthContext | None):
        self.context = context
        self.tokens: list[str] = []

    async def validate(self, token: str) -> AuthContext | None:
        self.tokens.append(token)
        return self.context


def make_request(
    headers: Mapping[str, str] | None = None,
    cookies: Mapping[str, str] | None = None,
) -> Request:
    headers = headers or {}
    cookies = cookies or {}
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [
            (key.lower().encode(), value.encode())
            for key, value in headers.items()
        ]
        + [
            (b"cookie", "; ".join(f"{key}={value}" for key, value in cookies.items()).encode())
        ]
        if cookies
        else [],
        "client": ("127.0.0.1", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_settings_include_worker_and_runtime_defaults():
    settings = Settings(app_env="test", database_url=None)

    assert settings.app_name == "douyin-order-python"
    assert settings.log_level == "INFO"
    assert settings.environment == "development"
    assert settings.redis_url is None


def test_success_and_failure_have_stable_json_envelopes():
    assert ApiEnvelope(code=1, msg="success", data={"id": "DEMO"}).model_dump() == {
        "code": 1,
        "msg": "success",
        "data": {"id": "DEMO"},
    }
    assert success({"id": "DEMO"}).body == b'{"code":1,"msg":"success","data":{"id":"DEMO"}}'
    assert failure("invalid request").body == (
        b'{"code":0,"msg":"invalid request","data":null}'
    )


@pytest.mark.asyncio
async def test_request_auth_accepts_bearer_token_before_cookie():
    context = AuthContext(
        user_id=7,
        role_ids=frozenset({"staff"}),
        permissions=frozenset({"order:read"}),
        department_ids=frozenset({3}),
    )
    validator = FakeValidator(context)
    auth = RequestAuth(validator)

    result = await auth(
        make_request(
            headers={"authorization": "Bearer bearer-token"},
            cookies={"access_token": "cookie-token"},
        )
    )

    assert result == context
    assert validator.tokens == ["bearer-token"]


@pytest.mark.asyncio
async def test_request_auth_uses_cookie_and_rejects_missing_or_invalid_tokens():
    context = AuthContext(
        user_id=7,
        role_ids=frozenset(),
        permissions=frozenset(),
        department_ids=frozenset(),
    )
    validator = FakeValidator(context)
    auth = RequestAuth(validator)

    assert await auth(make_request(cookies={"access_token": "cookie-token"})) == context
    assert validator.tokens == ["cookie-token"]

    with pytest.raises(Exception) as missing:
        await RequestAuth(FakeValidator(None))(make_request())
    assert missing.value.status_code == 401
    assert missing.value.detail == "authentication required"

    with pytest.raises(Exception) as invalid:
        await RequestAuth(FakeValidator(None))(
            make_request(headers={"authorization": "Bearer bad"})
        )
    assert invalid.value.status_code == 401
    assert invalid.value.detail == "authentication required"


@pytest.mark.asyncio
async def test_require_permission_rejects_missing_permission():
    dependency = require_permission("order:write")
    allowed = AuthContext(1, frozenset(), frozenset({"order:write"}), frozenset())
    denied = AuthContext(1, frozenset(), frozenset({"order:read"}), frozenset())

    assert await dependency(allowed) == allowed
    with pytest.raises(Exception) as error:
        await dependency(denied)
    assert error.value.status_code == 403
    assert error.value.detail == "permission denied"


@pytest.mark.asyncio
async def test_require_permission_can_use_injected_request_auth_dependency():
    context = AuthContext(
        user_id=7,
        role_ids=frozenset(),
        permissions=frozenset({"order:read"}),
        department_ids=frozenset(),
    )
    auth = RequestAuth(FakeValidator(context))
    app = FastAPI()

    @app.get("/orders", dependencies=[Depends(require_permission("order:read", auth))])
    async def orders():
        return {"ok": True}

    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/orders", headers={"authorization": "Bearer DEMO"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_unit_of_work_commits_and_rolls_back():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    table = Table(
        "demo",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
    )
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with UnitOfWork(factory) as unit:
        unit.session.execute(table.insert().values(id=1, name="committed"))

    with pytest.raises(ValueError):
        with UnitOfWork(factory) as unit:
            unit.session.execute(table.insert().values(id=2, name="rolled-back"))
            raise ValueError("abort")

    with factory() as session:
        rows = session.execute(select(table)).mappings().all()
    assert [dict(row) for row in rows] == [{"id": 1, "name": "committed"}]


def test_repository_lists_filters_and_inserts_with_sqlalchemy_expressions():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    table = Table(
        "demo",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
    )
    metadata.create_all(engine)
    with Session(engine) as session:
        repository = SqlAlchemyRepository(session, table)
        repository.insert({"id": 1, "name": "DEMO"})
        assert repository.get_by_id(1)["name"] == "DEMO"
        assert repository.list({"name": "DEMO"})[0]["id"] == 1


def test_repository_rejects_unknown_filter_columns():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    table = Table(
        "demo",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
    )
    metadata.create_all(engine)

    with Session(engine) as session:
        repository = SqlAlchemyRepository(session, table)
        with pytest.raises(ValueError, match="unknown filter column: missing"):
            repository.list({"missing": "DEMO"})


def test_celery_app_configures_broker_without_connecting():
    celery = create_celery_app("redis://127.0.0.1:6379/15")

    assert celery.conf.broker_url == "redis://127.0.0.1:6379/15"
    assert celery.conf.task_always_eager is False
    assert celery.connection_for_read is not None


def test_celery_app_reads_redis_url_from_formal_settings_when_omitted(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/16")

    celery = create_celery_app()

    assert celery.conf.broker_url == "redis://127.0.0.1:6379/16"
    assert celery.conf.result_backend == "redis://127.0.0.1:6379/16"
