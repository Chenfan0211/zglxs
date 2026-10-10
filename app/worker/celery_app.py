from __future__ import annotations

from celery import Celery

from app.core.settings import Settings


def create_celery_app(
    redis_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> Celery:
    resolved_settings = settings or Settings.from_env()
    if redis_url is None:
        redis_url = resolved_settings.redis_url
    broker = redis_url or "memory://"
    backend = redis_url or "cache+memory://"
    app = Celery(
        "douyin-order-python",
        broker=broker,
        backend=backend,
        set_as_current=False,
    )
    beat_schedule = {
        "retry-failed-laike-events": {
            "task": "retry_failed_laike_events",
            "schedule": 60.0,
        },
    }
    if resolved_settings.laike_account_id:
        beat_schedule["reconcile-laike-account"] = {
            "task": "reconcile_laike_account",
            "schedule": float(resolved_settings.laike_poll_interval_seconds),
            "args": (resolved_settings.laike_account_id,),
        }
    app.conf.update(
        beat_schedule=beat_schedule,
        enable_utc=True,
        timezone="UTC",
    )
    return app
