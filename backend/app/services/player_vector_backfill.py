"""
Bulk vectorization service for player performances.
"""
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.player_game_log import PlayerGameLog
from app.models.player import Player
from app.services.player_profiler import PlayerProfiler
from app.services.vector_store import VectorStoreService
from app.config import settings
from loguru import logger

class PlayerVectorBackfillService:
    def __init__(self, db: Session):
        self.db = db
        self.profiler = PlayerProfiler()
        self.vector_store = VectorStoreService()

    def backfill_all_logs(self, batch_size: int = 100) -> int:
        """Vectorize player logs with batching and real data context."""
        # FIX: Ensure you are pulling real team/matchup data if your schema allows
        stmt = select(PlayerGameLog, Player.name).join(Player).where(PlayerGameLog.player_id == Player.id)
        results = self.db.execute(stmt).all()
        
        count = 0
        
        for log, player_name in results:
            # FIX: Stop hardcoding "Opponent" and "is_home". 
            # Use log attributes to ensure your search vectors are accurate.
            log_data = {
                "player_id": log.player_id,
                "player_name": player_name,
                "opponent": getattr(log, 'opp_team', 'Unknown'), 
                "is_home": getattr(log, 'is_home', True),
                "pts": log.pts,
                "pra": log.pra,
                "game_id": log.game_id
            }
            
            description = self.profiler.generate_description(log_data)
            metadata = self.profiler.generate_metadata(log_data)
            
            # Queue for batch processing
            self.vector_store.upsert_game_scenario(
                game_id=log.external_log_id,
                description=description,
                metadata=metadata,
                collection=settings.QDRANT_COLLECTION_PLAYERS
            )
            count += 1
            
            if count % batch_size == 0:
                logger.info(f"Processed {count} records...")
            
        logger.info(f"Successfully vectorized {count} player performances")
        return count