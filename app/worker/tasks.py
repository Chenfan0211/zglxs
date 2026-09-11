from app.worker.laike_tasks import (
    celery_app,
    process_laike_webhook,
    reconcile_laike_account,
    retry_failed_laike_events,
)


@celery_app.task
def health_task() -> str:
    return "ok"
