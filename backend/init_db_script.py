"""
Database initialization script.
Creates all tables defined in the SQLAlchemy models.
"""
import asyncio
import sys
import os

# Add the current directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db
from loguru import logger

async def main():
    try:
        logger.info("Starting database schema creation...")
        await init_db()
        logger.info("✅ All tables created successfully!")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
