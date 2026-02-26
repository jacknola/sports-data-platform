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
        "app.tasks.betting",
    ],
)

# Basic configuration
app.conf.update(
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,  # 1 hour
)

# Periodic tasks
app.conf.beat_schedule = {
    "refresh-nba-odds-daily": {
        "task": "app.tasks.nba.refresh_nba_odds",
        "schedule": crontab(hour=11, minute=5),
        "options": {"queue": "data-updates"},
    },
    "place-bets-daily": {
        "task": "app.tasks.betting.place_bets_daily",
        "schedule": crontab(hour=14, minute=0), # Run at 2 PM UTC daily
        "options": {"queue": "betting"},
    },
    "settle-bets-daily": {
        "task": "app.tasks.betting.settle_bets_daily",
        "schedule": crontab(hour=10, minute=0), # Run at 10 AM UTC daily
        "options": {"queue": "betting"},
    },
    "export-sheets-daily": {
        "task": "app.tasks.betting.export_to_sheets_daily",
        "schedule": crontab(hour=15, minute=0), # Run at 3 PM UTC daily
        "options": {"queue": "reports"},
    },
}

logger.info("Celery app configured with daily NBA odds refresh schedule")
