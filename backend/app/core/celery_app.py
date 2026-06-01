from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=60 * 60 * 24,
    worker_prefetch_multiplier=1,
    imports=["app.worker.tasks"],
)
