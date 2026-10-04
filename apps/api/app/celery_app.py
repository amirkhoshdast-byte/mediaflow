from celery import Celery

from app.config import get_settings

settings = get_settings()
celery = Celery("ncr", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery.conf.timezone = settings.timezone
celery.conf.task_track_started = True
