"""Configuration data module"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # App
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./test.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # API Keys
    SPORTSRADAR_API_KEY: Optional[str] = None
    ODDSAPI_API_KEY: Optional[str] = None
    THE_ODDS_API_KEY: Optional[str] = None

    # Twitter
    TWITTER_BEARER_TOKEN: Optional[str] = None
    TWITTER_CONSUMER_KEY: Optional[str] = None
    TWITTER_CONSUMER_SECRET: Optional[str] = None

    # Hugging Face
    HUGGINGFACE_API_KEY: Optional[str] = None
    HUGGINGFACE_MODEL: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"

    # BallDontLie (NBA player stats)
    BALLDONTLIE_API_KEY: Optional[str] = None
    BALL_DONT_LIE_API_KEY: Optional[str] = None

    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None

    # Notion
    NOTION_API_KEY: Optional[str] = None
    NOTION_DATABASE_ID: Optional[str] = None

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None

    # Gemini (Google AI)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_PROJECT_ID: Optional[str] = None

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_TIMEZONE: str = "America/New_York"
    TELEGRAM_CRON_MORNING: str = "0 9 * * *"
    TELEGRAM_CRON_AFTERNOON: str = "0 14 * * *"
    TELEGRAM_CRON_EVENING: str = "0 19 * * *"

    # Slack
    SLACK_WEBHOOK_URL: Optional[str] = None

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_PATH: Optional[str] = None
    GOOGLE_SPREADSHEET_ID: Optional[str] = None

    # Security
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        case_sensitive = True


settings = Settings()
