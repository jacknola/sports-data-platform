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
    CURRENT_SEASON: str = "2025-26"

    # Database
    DATABASE_URL: str = "sqlite:///./test.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant (Vector Database)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_GAMES: str = "game_scenarios"
    QDRANT_COLLECTION_PLAYERS: str = "player_performances"
    QDRANT_COLLECTION_NBA_PROPS: str = "nba_historical_props"
    QDRANT_COLLECTION_HISTORICAL_PROPS: str = "historical_props"
    QDRANT_COLLECTION_NBA_PATTERNS: str = "nba_player_patterns"
    QDRANT_COLLECTION_HISTORICAL_GAMES: str = "historical_games"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # API Keys
    SPORTSRADAR_API_KEY: Optional[str] = None
    ODDS_API_KEY: Optional[str] = None
    ODDSAPI_API_KEY: Optional[str] = None
    THE_ODDS_API_KEY: Optional[str] = None
    ODDS_API_KEY_FALLBACK: Optional[str] = None
    SPORTS_GAME_ODDS_API_KEY: Optional[str] = None
    ODDS_API_IO_KEY: Optional[str] = None

    # Twitter
    TWITTER_BEARER_TOKEN: Optional[str] = None
    TWITTER_CONSUMER_KEY: Optional[str] = None
    TWITTER_CONSUMER_SECRET: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_TOKEN_SECRET: Optional[str] = None

    # Hugging Face
    HUGGINGFACE_API_KEY: Optional[str] = None
    HUGGINGFACE_MODEL: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"

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

    # Betting
    BETTING_BANKROLL: float = 1000.0
    KELLY_FRACTION_QUARTER: float = 0.25
    KELLY_FRACTION_HALF: float = 0.5
    MAX_BET_PERCENTAGE: float = 0.05
    EDGE_THRESHOLD_LOW: float = 0.03
    EDGE_THRESHOLD_MEDIUM: float = 0.05
    EDGE_THRESHOLD_HIGH: float = 0.07
    EDGE_THRESHOLD_MAX: float = 0.10
    ENABLE_SHARP_SIGNALS: bool = False

    # Primary retail sportsbook (the book you actually place bets at)
    # Odds fetches, CLV tracking, and bet records will reference this book.
    PRIMARY_BOOK: str = "fanduel"

    # How often (in minutes) to auto-refresh odds from the primary book.
    # Matches the Celery beat schedule: crontab(minute=0, hour="*/4") = 240 min.
    ODDS_REFRESH_INTERVAL_MINUTES: int = 240

    # Sharp Signals Data Quality
    SHARP_SIGNALS_MODE: str = "development"  # "production" or "development"
    SHARP_SIGNALS_ALLOW_MOCK: bool = True  # Allow mock data in dev, False in production
    SHARP_SIGNALS_MIN_DATA_QUALITY: str = "inferred"  # "live", "inferred", "mock", "unavailable"
    SHARP_SIGNALS_LOG_QUALITY_METRICS: bool = True
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
