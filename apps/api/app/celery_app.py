from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()
celery = Celery("ncr", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery.conf.timezone = settings.timezone
celery.conf.task_track_started = True

# Reports run at 08:00 and 16:00 Tehran time; the half-hourly catch-up covers a worker that was
# down at the exact minute (generation is idempotent per slot and day).
schedule = {
    "report-morning": {
        "task": "reports.generate",
        "schedule": crontab(hour=8, minute=0),
        "args": ("morning",),
    },
    "report-afternoon": {
        "task": "reports.generate",
        "schedule": crontab(hour=16, minute=0),
        "args": ("afternoon",),
    },
    "report-catch-up": {"task": "reports.catch_up", "schedule": crontab(minute="*/30")},
}
if settings.ingest_enabled:
    schedule["ingest-all-sources"] = {
        "task": "ingest.run_all",
        "schedule": float(settings.ingest_interval_seconds),
    }
celery.conf.beat_schedule = schedule
