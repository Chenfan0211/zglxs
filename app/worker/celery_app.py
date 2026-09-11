from __future__ import annotations

from celery import Celery


def create_celery_app(redis_url: str | None = None) -> Celery:
    broker = redis_url or "memory://"
    backend = redis_url or "cache+memory://"
    return Celery(
        "douyin-order-python",
        broker=broker,
        backend=backend,
        set_as_current=False,
    )
