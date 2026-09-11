# Python 迁移基础骨架实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可启动、可测试、支持 Python 接管与 PHP 基线回退的 FastAPI 迁移基础骨架。

**Architecture:** 使用 `MigrationRegistry` 保存显式 Python 接口，使用兼容入口统一分发；未登记接口只有在配置 `PHP_BASELINE_URL` 时才由 `PhpBaselineProxy` 转发。数据库和外部服务都采用延迟初始化与可替换实现，使本地测试不依赖真实基础设施。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、pydantic-settings、SQLAlchemy 2、PyMySQL、Alembic、Celery/Redis、pytest、httpx、SQLite（仅测试）。

**Spec:** `docs/superpowers/specs/2026-09-11-python-migration-foundation-design.md`

## Global Constraints

- 不连接或修改生产数据库。
- 不复制或提交 `wwwroot.zip` 中的 `.env`、Token、证书、日志和上传文件。
- 第一阶段不实现真实业务接口，不登记没有行为契约的 PHP 控制器动作。
- PHP 基线回退默认关闭，只允许由固定的 `PHP_BASELINE_URL` 配置。
- `/internal/health/live` 和 `/internal/health/ready` 只允许本机访问。
- 所有新增生产代码必须先有一个会失败的行为测试，再实现最小代码。

---

### Task 1: 工程元数据与安全默认值

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Test: `tests/test_project_metadata.py`

**Interfaces:**
- Produces install command `python -m pip install -e ".[test]"`.
- Produces settings keys `APP_ENV`, `DATABASE_URL`, `PHP_BASELINE_URL`, `PHP_BASELINE_TIMEOUT_SECONDS`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_project_metadata_has_safe_defaults_and_test_extra():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert 'python = ">=3.12,<3.13"' in pyproject
    assert "[project.optional-dependencies]" in pyproject
    assert 'DATABASE_URL=""' in env_example
    assert 'PHP_BASELINE_URL=""' in env_example
    assert ".env" in gitignore
    assert "runtime/" in gitignore
    assert "uploads/" in gitignore
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_project_metadata.py -q`

Expected: FAIL because the project metadata files do not exist.

- [ ] **Step 3: Write minimal implementation**

`pyproject.toml` must declare:

```toml
[project]
name = "douyin-order-python"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "alembic>=1.13,<2",
  "celery[redis]>=5.4,<6",
  "fastapi>=0.115,<1",
  "httpx>=0.27,<1",
  "pydantic>=2.9,<3",
  "pydantic-settings>=2.6,<3",
  "PyMySQL>=1.1,<2",
  "SQLAlchemy>=2.0,<3",
  "uvicorn[standard]>=0.30,<1",
]

[project.optional-dependencies]
test = ["pytest>=8,<9", "pytest-asyncio>=0.24,<1"]
```

`.env.example` must contain blank values only:

```dotenv
APP_ENV=development
DATABASE_URL=""
PHP_BASELINE_URL=""
PHP_BASELINE_TIMEOUT_SECONDS=10
```

`.gitignore` must ignore `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `runtime/`, `uploads/`, and `*.log`.

`README.md` must document the install/test/run commands and explicitly state that the real `.env` and production credentials are never committed.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_project_metadata.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml .gitignore .env.example README.md tests/test_project_metadata.py
git commit -m "chore: bootstrap python migration project"
```

### Task 2: 配置、数据库和健康检查

**Files:**
- Create: `app/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/settings.py`
- Create: `app/db/__init__.py`
- Create: `app/db/session.py`
- Create: `app/api/__init__.py`
- Create: `app/api/health.py`
- Create: `app/main.py`
- Test: `tests/test_health.py`

**Interfaces:**
- `Settings.from_env()` returns a Pydantic settings object with `database_url: str | None`, `php_baseline_url: str | None`, and `php_baseline_timeout_seconds: float`.
- `Database.check()` returns `True` after executing `SELECT 1`, and raises a controlled `RuntimeError` when no URL is configured.
- `create_app(settings: Settings | None = None, ...) -> FastAPI` returns the application.

- [ ] **Step 1: Write the failing test**

```python
import httpx
import pytest

from app.core.settings import Settings
from app.main import create_app


async def request(app, path: str, client=("127.0.0.1", 123)):
    transport = httpx.ASGITransport(app=app, client=client)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as http_client:
        return await http_client.get(path)


@pytest.mark.asyncio
async def test_live_health_is_available_without_database():
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url=None,
            php_baseline_timeout_seconds=1,
        )
    )

    from app.api.health import require_loopback

    app.dependency_overrides[require_loopback] = lambda: None
    response = await request(app, "/internal/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_health_reports_unconfigured_database():
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url=None,
            php_baseline_timeout_seconds=1,
        )
    )

    from app.api.health import require_loopback

    app.dependency_overrides[require_loopback] = lambda: None
    response = await request(app, "/internal/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "database is not configured"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health.py -q`

Expected: FAIL because `app.main` and the health endpoints do not exist.

- [ ] **Step 3: Write minimal implementation**

`Settings` must use `pydantic-settings` aliases so environment variables map to the fields:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    php_baseline_url: str | None = Field(default=None, validation_alias="PHP_BASELINE_URL")
    php_baseline_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="PHP_BASELINE_TIMEOUT_SECONDS",
        gt=0,
    )
```

Normalize blank URLs to `None`. `Database` must create its SQLAlchemy engine only when `database_url` is non-empty:

```python
class Database:
    def __init__(self, database_url: str | None):
        self._database_url = database_url
        self._engine = None

    def check(self) -> bool:
        if not self._database_url:
            raise RuntimeError("database is not configured")
        if self._engine is None:
            self._engine = create_engine(self._database_url, pool_pre_ping=True)
        with self._engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
```

The two health endpoints must use a dependency that rejects non-loopback clients with status 403. For the tests, use a dependency override or the request host accepted by the implementation; do not remove the production loopback check.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app tests/test_health.py
git commit -m "feat: add local health checks and lazy database"
```

### Task 3: 显式迁移路由和 PHP 基线代理

**Files:**
- Create: `app/api/migration.py`
- Create: `app/integrations/__init__.py`
- Create: `app/integrations/php_baseline.py`
- Modify: `app/main.py`
- Test: `tests/test_migration_routing.py`

**Interfaces:**
- `MigrationRegistry.register(controller, action, methods, handler)` registers a Python handler.
- `MigrationRegistry.resolve(controller, action, method)` returns a handler or `None`.
- `PhpBaselineProxy.forward(request, controller, action) -> Response` forwards to the configured fixed base URL.
- `create_app(..., registry: MigrationRegistry | None = None, php_proxy: PhpBaselineProxy | None = None) -> FastAPI`.

- [ ] **Step 1: Write the failing test**

```python
from fastapi import Response
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app
from app.api.migration import MigrationRegistry


class FakePhpProxy:
    async def forward(self, request, controller, action):
        return Response(
            content=b'{"source":"php","controller":"Demo","action":"list"}',
            media_type="application/json",
            status_code=201,
        )


async def python_probe(request):
    return {"source": "python"}


def test_registered_route_is_handled_by_python():
    registry = MigrationRegistry()
    registry.register("Demo", "probe", ["GET"], python_probe)
    app = create_app(
        Settings(app_env="test", database_url=None, php_baseline_url=None),
        registry=registry,
    )

    response = TestClient(app).get("/apiv1/Demo/probe")

    assert response.status_code == 200
    assert response.json() == {"source": "python"}


def test_unregistered_route_falls_back_to_php_proxy():
    app = create_app(
        Settings(
            app_env="test",
            database_url=None,
            php_baseline_url="http://127.0.0.1:18085",
            php_baseline_timeout_seconds=1,
        ),
        php_proxy=FakePhpProxy(),
    )

    response = TestClient(app).get("/apiv1/Demo/list")

    assert response.status_code == 201
    assert response.json()["source"] == "php"


def test_unregistered_route_without_php_baseline_returns_not_migrated():
    app = create_app(
        Settings(app_env="test", database_url=None, php_baseline_url=None)
    )

    response = TestClient(app).get("/apiv1/Demo/list")

    assert response.status_code == 404
    assert response.json()["detail"] == "API route is not migrated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migration_routing.py -q`

Expected: FAIL because the registry, proxy and `/apiv1/{controller}/{action}` dispatcher do not exist.

- [ ] **Step 3: Write minimal implementation**

Use a case-sensitive tuple key `(controller, action, method.upper())`. The dispatcher must:

1. Resolve a registered handler and await it.
2. Call the injected `PhpBaselineProxy` only when no handler exists and `settings.php_baseline_url` is not `None`.
3. Return `404` with exactly `API route is not migrated` otherwise.

The real proxy must build its destination as:

```python
target = f"{base_url.rstrip('/')}/apiv1/{controller}/{action}"
```

It must pass query params, request body, cookies, and safe headers to `httpx.AsyncClient(timeout=timeout)`, then return a FastAPI `Response` containing the upstream bytes, status code, and `content-type`. Catch `httpx.HTTPError` and raise `HTTPException(status_code=502, detail="PHP baseline unavailable")`.

Do not accept a complete target URL from request data, and do not log authorization or cookie values.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migration_routing.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app tests/test_migration_routing.py
git commit -m "feat: add explicit migration routing and php fallback"
```

### Task 4: 外部服务协议和 Mock

**Files:**
- Create: `app/integrations/providers.py`
- Test: `tests/test_provider_mocks.py`

**Interfaces:**
- `DouyinLaikeProvider`, `SmsProvider`, `CloudCallProvider`, and `WebhookProvider` are runtime-checkable protocols with an async `send(payload: Mapping[str, Any]) -> ProviderResult`.
- `ProviderResult` has `ok: bool`, `code: str`, and `request_id: str`.
- `MockProvider(name, fail=False).send(payload)` returns a deterministic success result or `ProviderResult(ok=False, code="mock_failure", request_id=...)`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.integrations.providers import (
    CloudCallProvider,
    DouyinLaikeProvider,
    MockProvider,
    ProviderResult,
    SmsProvider,
    WebhookProvider,
)


@pytest.mark.parametrize(
    "provider_protocol",
    [DouyinLaikeProvider, SmsProvider, CloudCallProvider, WebhookProvider],
)
@pytest.mark.asyncio
async def test_mock_provider_returns_deterministic_result(provider_protocol):
    provider = MockProvider("sms")
    assert isinstance(provider, provider_protocol)

    result = await provider.send({"event": "DEMO_order_created"})

    assert result == ProviderResult(ok=True, code="mock_ok", request_id="mock-sms-001")


@pytest.mark.asyncio
async def test_mock_provider_can_simulate_failure():
    result = await MockProvider("webhook", fail=True).send({"event": "DEMO"})

    assert result == ProviderResult(
        ok=False,
        code="mock_failure",
        request_id="mock-webhook-001",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_provider_mocks.py -q`

Expected: FAIL because the provider protocols and MockProvider do not exist.

- [ ] **Step 3: Write minimal implementation**

Define one shared protocol shape and four protocol aliases:

```python
@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    code: str
    request_id: str


@runtime_checkable
class SmsProvider(Protocol):
    async def send(self, payload: Mapping[str, Any]) -> ProviderResult: ...
```

`MockProvider.send()` must ignore personal fields, return the fixed request id `mock-{name}-001`, and never perform network I/O. Implement the remaining three protocols with the same shape.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_provider_mocks.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/integrations/providers.py tests/test_provider_mocks.py pyproject.toml
git commit -m "feat: add deterministic external provider mocks"
```

### Task 5: 契约清单与全量验证

**Files:**
- Create: `contracts/api-manifest.json`
- Create: `contracts/README.md`
- Modify: `README.md`
- Test: `tests/test_contract_manifest.py`

**Interfaces:**
- `contracts/api-manifest.json` records `version`, `fallback_enabled_by_default`, `migrated_routes`, and `discovered_routes`.
- The initial manifest has empty route arrays and states that no real business endpoint is migrated.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path


def test_initial_contract_manifest_is_explicitly_empty():
    manifest = json.loads(
        (Path(__file__).parents[1] / "contracts/api-manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["version"] == 1
    assert manifest["fallback_enabled_by_default"] is False
    assert manifest["migrated_routes"] == []
    assert manifest["discovered_routes"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contract_manifest.py -q`

Expected: FAIL because the contract manifest does not exist.

- [ ] **Step 3: Write minimal implementation**

Use this exact initial JSON shape:

```json
{
  "version": 1,
  "fallback_enabled_by_default": false,
  "migrated_routes": [],
  "discovered_routes": [],
  "notes": [
    "真实业务接口必须先完成 PHP/Python 契约对比后才能加入 migrated_routes。",
    "PHP 基线回退由 PHP_BASELINE_URL 显式开启。"
  ]
}
```

`contracts/README.md` must explain the fields and require every later migrated endpoint to record method, controller, action, request shape, response shape, error behavior, and database side effects.

- [ ] **Step 4: Run the full verification suite**

Run: `python -m pytest -q`

Expected: PASS with zero failures and no unhandled warnings.

- [ ] **Step 5: Run import and startup verification**

Run: `python -c "from app.main import app; print(app.title)"`

Expected: prints `抖音订单管理系统 Python API`.

Run: `python -m uvicorn app.main:app --host 127.0.0.1 --port 18083` and request `GET http://127.0.0.1:18083/internal/health/live` from a second terminal.

Expected: HTTP 200 and `{"status":"ok"}`. Stop the process after the check.

- [ ] **Step 6: Commit**

```powershell
git add contracts README.md tests/test_contract_manifest.py
git commit -m "docs: add initial api contract manifest"
```
