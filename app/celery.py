from celery import Celery
from datetime import timedelta

from .config import get_settings


settings = get_settings()

celery_app = Celery(
    "app",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    result_expires=timedelta(days=7),  # keep results for 7 days
    result_persistent=True,
)
