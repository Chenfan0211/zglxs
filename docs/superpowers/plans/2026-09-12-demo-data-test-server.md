# Demo Data Test Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe, repeatable Laike demo data seeding and deploy the current Python migration service to the test server.

**Architecture:** Demo data is inserted only into Python-owned Laike sync tables through SQLAlchemy upserts. Deployment packages the repository, installs dependencies in a release directory, runs Alembic migrations, seeds demo rows, and restarts the test services.

**Tech Stack:** Python 3.12, SQLAlchemy, Alembic, FastAPI, Systemd, Nginx, SSH.

**Spec:** User request in this conversation: add fake data and update test server `192.168.28.188`.

## Global Constraints

- Do not decrypt, modify, or depend on encrypted PHP files.
- Do not store server passwords, tokens, HAR files, real phone numbers, real addresses, or provider credentials in Git.
- Do not truncate, drop, or reset databases.
- Keep `contracts/api-manifest.json.migrated_routes` empty until real PHP/Python contract parity exists.
- Demo seed data must be idempotent and scoped to `DEMO-*` identifiers.

---

### Task 1: Demo Seed Script

**Files:**
- Create: `tools/seed_laike_demo_data.py`
- Create: `tests/test_seed_laike_demo_data.py`

**Interfaces:**
- Produces CLI: `python -m tools.seed_laike_demo_data --count 12`
- Reads database URL from `--database-url`, then `TEST_DATABASE_URL`, then `DATABASE_URL`.
- Upserts `laike_webhook_event`, `laike_order`, `laike_sync_cursor`, and `laike_sync_run`.

- [x] **Step 1: Write tests for idempotent demo data insertion.**
- [x] **Step 2: Implement the seed script with SQLAlchemy upserts and no destructive operations.**
- [x] **Step 3: Run focused tests and full regression.**

### Task 2: Test Server Deployment

**Files:**
- No source code changes beyond Task 1.

**Interfaces:**
- Remote release path: `/srv/douyin-order-python/releases/<timestamp>`.
- Current symlink: `/srv/douyin-order-python/current`.
- Environment file: `/srv/douyin-order-python/shared/env/api.env`.

- [x] **Step 1: Connect to the test server and inspect Python, systemd, nginx, and current app layout.**
- [x] **Step 2: Upload the release package without secrets or local caches.**
- [x] **Step 3: Install dependencies, run Alembic migrations, and seed demo data.**
- [x] **Step 4: Restart services and run deployment checks.**

### Verification Checklist

- [x] `python -m pytest tests/test_seed_laike_demo_data.py -q` passes.
- [x] `python -m pytest -q` passes.
- [x] `python -m compileall -q app alembic tools` passes.
- [x] `git diff --check` passes.
- [x] Remote health endpoint responds.
- [x] Remote database contains `DEMO-LAIKE-ORDER-*` rows.
- [x] No real credentials or personal data are committed.

## Deployment Notes

- Release: `/srv/douyin-order-python/releases/20260912100301`.
- Current release: `/srv/douyin-order-python/current`.
- Demo database: `/srv/douyin-order-python/shared/data/douyin_py_test.db`.
- The old PHP service on port `18082` was not replaced.
- On this SELinux-enforcing host, the application env, data, logs, and port `18084/tcp` received persistent SELinux policy labels.
- Windows archive extraction did not preserve executable bits for shell scripts; the deployed `deploy/scripts/*.sh` files were restored to mode `0755`.
