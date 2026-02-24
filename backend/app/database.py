"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from loguru import logger

from app.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database"""
    import os
    logger.info("Initializing database...")
    # Import all models to register them with SQLAlchemy Base
    from app.models import bet, game, team, player, api_cache, parlay, player_game_log
    
    # Create tables
    if os.getenv("ENVIRONMENT") != "test":
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized")
    else:
        logger.info("Database initialization skipped (test environment)")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

