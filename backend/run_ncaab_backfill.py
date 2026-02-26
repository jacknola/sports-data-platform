import asyncio
import sys
import os
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, SessionLocal
from app.services.ncaab_backfill import NCAABBackfillService
from app.services.ncaab_vector_backfill import NCAABVectorBackfillService

async def main():
    logger.info("Starting NCAAB Backfill Pipeline")
    
    # 1. Init DB
    await init_db()
    
    db = SessionLocal()
    try:
        # Step 1: Fetch Games (ESPN)
        service = NCAABBackfillService(db)
        
        # 2023-24 Season: Nov 6, 2023 to April 8, 2024 (Championship)
        start_date = "2023-11-06"
        end_date = "2024-04-08"
        
        logger.info(f"Backfilling NCAAB season from {start_date} to {end_date}")
        
        total = await service.backfill_season(start_date, end_date)
        logger.info(f"✅ NCAAB Game Backfill Complete! Total games: {total}")
        
        # Step 2: Vectorize (Qdrant)
        logger.info("Starting Qdrant Vectorization...")
        vector_service = NCAABVectorBackfillService(db)
        vectors_count = vector_service.backfill_vectors()
        logger.info(f"✅ NCAAB Vectorization Complete! Vectors upserted: {vectors_count}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
