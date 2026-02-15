from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Force tasks to be acknowledged only after they succeed or fail
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks in the app/tasks directory
celery_app.autodiscover_tasks(["app.tasks"])
