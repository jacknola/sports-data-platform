"""
Application configuration
"""
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
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
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
    
    # Notion
    NOTION_API_KEY: Optional[str] = None
    NOTION_DATABASE_ID: Optional[str] = None
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

