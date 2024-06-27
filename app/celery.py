from celery import Celery
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
    task_acks_late=True,
    task_reject_on_worker_lost=True,  # task is re-queued if worker crashes
    task_default_retry_delay=60,  # retry after 60 sec
    task_max_retries=3,  # retry up to 3 times
    task_soft_time_limit=300,  # soft time limit of 5 minutes
    task_time_limit=360,  # hard time limit of 6 minutes
    worker_max_tasks_per_child=100,  # restart worker after 100 tasks
)
