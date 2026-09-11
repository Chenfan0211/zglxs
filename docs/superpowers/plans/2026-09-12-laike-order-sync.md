# 来客订单自动同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不解密 PHP、不猜真实来客接口的前提下，补齐可测试的来客 Webhook、订单轮询补偿、幂等存储、Celery 任务和黑盒契约采集基础设施。

**Architecture:** 来客适配层只依赖显式注入的 endpoint、签名头和字段映射；同步服务通过 SQLAlchemy 自有表保存原始事件、标准化订单、游标和批次，Webhook 接收与 Worker 处理分离。旧 `/apiv1` 路径继续由 `MigrationRegistry` 或 PHP 回退处理，只有在外部契约采集完成后才能显式注册真实 legacy action。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Pydantic Settings、Celery、httpx、pytest、SQLite/MySQL-compatible schema。

**Spec:** 用户提供的“来客订单自动同步补全方案”（本对话中的实施方案）。

## Global Constraints

- 不解密、不绕过授权、不修改加密 PHP 文件。
- 没有真实 HAR、PHP 基线、脱敏数据库快照时，不猜来客 Webhook 路径、签名算法、订单唯一 ID 或业务字段含义。
- 默认 `LAIKE_SYNC_MODE=observe`，`LAIKE_WEBHOOK_ENABLED=false`，`LAIKE_RECONCILE_ENABLED=false`，`LAIKE_WRITE_ENABLED=false`。
- 原始来客请求体完整保留在 Python 自有同步表，手机号、地址、Token、签名等敏感字段不得写普通日志、fixtures 或 Git。
- Python 只写独立同步表/测试库；不与 PHP 共用业务写库，不把未知接口加入 `migrated_routes`。
- 所有新增行为遵循 TDD：先写一个会失败的行为测试，再写最小实现，再运行回归测试。

---

### Task 1: 配置开关与脱敏契约采集工具

**Files:**
- Modify: `app/core/settings.py`
- Modify: `.env.example`
- Modify: `deploy/env/api.env.example`
- Create: `tools/laike_capture.py`
- Create: `tests/test_laike_config_and_capture.py`
- Modify: `contracts/api-manifest.json`
- Create: `contracts/fixtures/laike/accounts.jsonl`
- Create: `contracts/fixtures/laike/products.jsonl`
- Create: `contracts/fixtures/laike/sync-orders.jsonl`
- Create: `contracts/fixtures/laike/webhooks.jsonl`
- Create: `contracts/fixtures/laike/errors.jsonl`
- Create: `contracts/fixtures/laike/normalization.json`

**Interfaces:**
- `Settings` exposes `test_database_url`, `laike_base_url`, `laike_orders_path`, `laike_app_id`, `laike_app_secret`, `laike_access_token`, `laike_webhook_secret`, `laike_webhook_signature_header`, `laike_webhook_event_id_header`, `laike_sync_mode`, `laike_webhook_enabled`, `laike_reconcile_enabled`, `laike_write_enabled`, `laike_max_retries`, and `laike_overlap_seconds`.
- `sanitize_payload(value) -> value` recursively replaces sensitive keys with `[REDACTED]`.
- `append_jsonl(path, record) -> None` writes one sanitized JSON object per line and creates the parent directory.
- Manifest version becomes `2`; route template includes request headers, field identifiers, pagination, sync effects and dynamic normalization fields while `migrated_routes` remains empty.

- [ ] **Step 1: Write failing tests for settings, mode validation, redaction and JSONL output.**
- [ ] **Step 2: Run `python -m pytest tests/test_laike_config_and_capture.py -q`; confirm failure is caused by missing interfaces.**
- [ ] **Step 3: Implement settings aliases, secure defaults, redaction and fixture writer.**
- [ ] **Step 4: Run the focused test and then `python -m pytest -q`; both must pass.**
- [ ] **Step 5: Commit with `feat: add laike sync configuration and capture tooling`.**

### Task 2: 来客协议、HMAC 验证、HTTP 客户端和字段归一化

**Files:**
- Create: `app/laike/__init__.py`
- Create: `app/laike/contracts.py`
- Create: `app/laike/client.py`
- Create: `app/laike/normalizer.py`
- Create: `app/laike/webhook.py`
- Create: `tests/test_laike_protocols.py`

**Interfaces:**
- `LaikePage(items: list[Mapping[str, Any]], next_cursor: str | None, raw: Mapping[str, Any])`.
- `WebhookVerification(valid: bool, event_id: str | None, source: str, reason: str | None = None)`.
- `LaikeClient` has the exact async `fetch_orders(account_id, cursor, start_time, end_time)` and `verify_webhook(headers, raw_body)` methods from the user plan.
- `HttpLaikeClient` receives all URL/header/signature choices by constructor; an empty orders path raises a configuration error rather than inventing a path.
- `WebhookVerifier` verifies the injected signature header over the raw body, supports a configurable digest prefix and `hmac.compare_digest`, and never logs secrets.
- `OrderFieldMapping` and `OrderNormalizer` only extract explicitly configured paths; absent order ID, subject ID or product ID raises `NormalizationError`; raw payload and original/normalized time values are retained.

- [ ] **Step 1: Write failing tests for page parsing, missing endpoint configuration, signature success/failure/missing, and explicit field mapping.**
- [ ] **Step 2: Run `python -m pytest tests/test_laike_protocols.py -q`; confirm expected RED failures.**
- [ ] **Step 3: Implement the protocol dataclasses, injected httpx client, verifier and normalizer.**
- [ ] **Step 4: Run the focused test and full suite.**
- [ ] **Step 5: Commit with `feat: add laike protocol and normalization layer`.**

### Task 3: SQLAlchemy 同步表、Repository 和幂等 Service

**Files:**
- Create: `app/db/models/laike.py`
- Modify: `app/db/models/__init__.py`
- Create: `app/laike/repositories.py`
- Create: `app/laike/service.py`
- Create: `tests/test_laike_service.py`

**Interfaces:**
- Tables are named `laike_webhook_event`, `laike_order`, `laike_sync_cursor`, and `laike_sync_run`.
- `LaikeSyncService(session_factory, client, normalizer, enqueue_webhook=None, settings=None)` exposes async `receive_webhook(headers, raw_body)`, `process_webhook(event_id)`, `reconcile_account(account_id, start_time=None, end_time=None)`, and `retry_failed_events()`.
- Webhook receipt writes an event before enqueueing; duplicate event IDs are idempotent; invalid JSON/signature is recorded and not enqueued.
- Order upsert uses the stable normalized order ID as a unique key; duplicate order delivery updates the row.
- Reconciliation processes each order in an independent transaction, advances the cursor only after successful page processing, writes a sync run, and records per-order failures without aborting other orders.
- `SyncResult` includes status, event ID, fetched, succeeded, duplicate, failed and reason fields needed by API and task layers.

- [ ] **Step 1: Write failing SQLite tests for event idempotency, order upsert, invalid input, per-order failure isolation, cursor behavior and rollback.**
- [ ] **Step 2: Run `python -m pytest tests/test_laike_service.py -q`; confirm RED.**
- [ ] **Step 3: Implement declarative models, repositories and transaction-scoped service logic.**
- [ ] **Step 4: Run focused tests and full suite.**
- [ ] **Step 5: Commit with `feat: add laike sync persistence and service`.**

### Task 4: Celery 任务、内部 Webhook 入口和兼容路由注册钩子

**Files:**
- Modify: `app/worker/celery_app.py`
- Modify: `app/worker/tasks.py`
- Create: `app/laike/routes.py`
- Modify: `app/main.py`
- Create: `tests/test_laike_api_and_tasks.py`

**Interfaces:**
- Tasks are named `process_laike_webhook(event_id)`, `reconcile_laike_account(account_id)`, and `retry_failed_laike_events()`; transient exceptions use Celery retry/backoff configuration.
- `create_laike_task_service(service)` injects a service for tests and worker bootstrap; absent service fails clearly without network access.
- `POST /internal/laike/webhook` is loopback-only and only enabled when a service is configured; it returns the existing JSON envelope and never processes orders inline.
- `register_captured_legacy_route(registry, controller, action, method, handler)` is an explicit hook; `main.py` does not invent or register unknown `collect` actions.
- Runtime configuration disables webhook/reconcile/write by default; `shadow` can write only the Python sync tables.

- [ ] **Step 1: Write failing tests for internal-only receipt, disabled mode, enqueue behavior and task delegation/retry metadata.**
- [ ] **Step 2: Run `python -m pytest tests/test_laike_api_and_tasks.py -q`; confirm RED.**
- [ ] **Step 3: Implement task wiring, internal route and explicit legacy registration helper.**
- [ ] **Step 4: Run focused tests and full suite.**
- [ ] **Step 5: Commit with `feat: wire laike webhook and celery tasks`.**

### Task 5: 契约回放比较、部署配置、文档和最终回归

**Files:**
- Modify: `tools/contract_tools.py`
- Modify: `tools/compare_contracts.py`
- Create: `tests/test_laike_contract_comparison.py`
- Modify: `README.md`
- Modify: `docs/migration-status.md`
- Modify: `contracts/README.md`
- Modify: `deploy/systemd/douyin-order-worker.service`
- Modify: `deploy/systemd/douyin-order-scheduler.service`
- Modify: `deploy/scripts/check-deploy.sh`

**Interfaces:**
- Contract comparison normalizes and compares status code, response headers/body and database effects while preserving the existing CLI.
- Deployment templates expose the three mode switches and worker/scheduler task names without embedding secrets.
- Documentation states that real Webhook path, signature algorithm, order ID and database mapping remain blocked until PHP/HAR/test credentials are supplied.

- [ ] **Step 1: Write failing tests for header/body/database comparison and deployment/docs declarations.**
- [ ] **Step 2: Run `python -m pytest tests/test_laike_contract_comparison.py -q`; confirm RED.**
- [ ] **Step 3: Implement comparison and documentation/deployment updates.**
- [ ] **Step 4: Run `python -m pytest -q` and inspect `git diff --check`.**
- [ ] **Step 5: Commit with `docs: document laike parity rollout and verification`.**

## Verification Checklist

- [ ] `python -m pytest -q` passes with zero failures.
- [ ] `git diff --check` passes.
- [ ] No fixture or log contains a real phone, address, token, secret or signature.
- [ ] `contracts/api-manifest.json` still has an empty `migrated_routes`.
- [ ] No real external request is made during tests.
- [ ] Final report explicitly separates implemented local infrastructure from blocked external prerequisites.
