from app.worker.celery_app import create_celery_app


celery_app = create_celery_app()


@celery_app.task
def health_task() -> str:
    return "ok"
