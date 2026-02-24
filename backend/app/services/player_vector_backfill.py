"""
Bulk vectorization service for player performances.
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.player_game_log import PlayerGameLog
from app.models.player import Player
from app.services.player_profiler import PlayerProfiler
from app.services.vector_store import VectorStoreService
from app.config import settings
from loguru import logger

class PlayerVectorBackfillService:
    """
    Service for vectorizing historical player logs into Qdrant.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.profiler = PlayerProfiler()
        self.vector_store = VectorStoreService()

    def backfill_all_logs(self) -> int:
        """
        Vectorize all player game logs in PostgreSQL into Qdrant.
        """
        # Fetch all logs with player info
        stmt = select(PlayerGameLog, Player.name).join(Player).where(PlayerGameLog.player_id == Player.id)
        results = self.db.execute(stmt).all()
        
        count = 0
        for log, player_name in results:
            log_data = {
                "player_id": log.player_id,
                "player_name": player_name,
                "opponent": "Opponent", # Ideally fetch team abbrev
                "is_home": True,
                "rest_days": 1,
                "opp_pace": 100.0,
                "pts": log.pts,
                "pra": log.pra,
                "reb": log.reb,
                "ast": log.ast,
                "fg3m": log.fg3m,
                "game_id": log.game_id
            }
            
            description = self.profiler.generate_description(log_data)
            metadata = self.profiler.generate_metadata(log_data)
            
            self.vector_store.upsert_game_scenario(
                game_id=log.external_log_id,
                description=description,
                metadata=metadata,
                collection=settings.QDRANT_COLLECTION_PLAYERS
            )
            count += 1
            
        logger.info(f"Successfully vectorized {count} player performances")
        return count
