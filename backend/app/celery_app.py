"""
Celery application and beat schedule
"""
from celery import Celery
from celery.schedules import crontab
from loguru import logger

from app.config import settings


# Create Celery application (variable name must be `app` for CLI discovery)
app = Celery(
    "sports-intel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.nba",
    ],
)

# Basic configuration
app.conf.update(
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,  # 1 hour
)

# Periodic tasks
# Runs daily at 11:05 UTC (adjust in compose or here as needed)
app.conf.beat_schedule = {
    "refresh-nba-odds-daily": {
        "task": "app.tasks.nba.refresh_nba_odds",
        "schedule": crontab(hour=11, minute=5),
        "options": {"queue": "data-updates"},
    },
}

logger.info("Celery app configured with daily NBA odds refresh schedule")
