from __future__ import annotations

import pytest
from celery.exceptions import MaxRetriesExceededError

from app.core.settings import Settings
from app.laike.provider_errors import LaikeProviderError
from app.worker import laike_tasks
from app.worker.celery_app import create_celery_app


def test_beat_schedules_configured_laike_account_at_poll_interval():
    app = create_celery_app(
        redis_url="memory://",
        settings=Settings(
            laike_account_id="DEMO-LAIKE-ACCOUNT-001",
            laike_poll_interval_seconds=17,
        ),
    )

    schedule = app.conf.beat_schedule["reconcile-laike-account"]

    assert schedule == {
        "task": "reconcile_laike_account",
        "schedule": 17.0,
        "args": ("DEMO-LAIKE-ACCOUNT-001",),
    }


def test_reconcile_returns_controlled_configuration_failure_without_credentials(
    monkeypatch,
):
    class Service:
        settings = Settings(
            laike_reconcile_enabled=True,
            laike_app_id=None,
            laike_app_secret=None,
        )

        async def reconcile_account(self, account_id):
            raise LaikeProviderError(
                "missing credentials",
                retryable=False,
            )

    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: Service())
    monkeypatch.setattr(
        laike_tasks.reconcile_laike_account,
        "retry",
        lambda **kwargs: pytest.fail("configuration errors must not retry"),
    )

    assert laike_tasks.reconcile_laike_account.run("DEMO-ACCOUNT") == {
        "status": "failed",
        "account_id": "DEMO-ACCOUNT",
        "reason": "laike provider request failed",
    }


def test_reconcile_retries_provider_errors_marked_retryable(monkeypatch):
    class Service:
        settings = Settings(
            laike_reconcile_enabled=True,
            laike_max_retries=3,
            laike_app_id="DEMO-APP",
            laike_app_secret="DEMO-SECRET",
        )

        async def reconcile_account(self, account_id):
            raise LaikeProviderError("temporary", code=2119003, retryable=True)

    monkeypatch.setattr(laike_tasks, "_service_factory", lambda: Service())
    calls: list[dict] = []

    def retry(**kwargs):
        calls.append(kwargs)
        raise MaxRetriesExceededError()

    monkeypatch.setattr(laike_tasks.reconcile_laike_account, "retry", retry)

    result = laike_tasks.reconcile_laike_account.run("DEMO-ACCOUNT")

    assert result == {"status": "dead_letter"}
    assert calls[0]["countdown"] == 1
