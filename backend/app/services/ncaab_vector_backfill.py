"""
NCAAB Vector Backfill Service.
Generates embeddings for historical NCAAB games and upserts them to Qdrant.
"""
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.game import Game
from app.services.vector_store import VectorStoreService
from app.config import settings
from loguru import logger

class NCAABVectorBackfillService:
    """
    Service for vectorizing historical NCAAB games into Qdrant.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.vector_store = VectorStoreService()

    def backfill_vectors(self) -> int:
        """
        Vectorize all NCAAB games in the SQL database.
        """
        logger.info("Starting NCAAB vector backfill...")
        
        # Fetch all NCAAB games
        stmt = select(Game).where(Game.sport == "ncaab")
        games = self.db.execute(stmt).scalars().all()
        
        if not games:
            logger.warning("No NCAAB games found in database to vectorize.")
            return 0
            
        count = 0
        for game in games:
            # Skip if no score
            if game.home_score is None or game.away_score is None:
                continue
                
            # Create a descriptive scenario string for RAG
            # e.g. "NCAAB: Duke (84) vs UNC (79) on 2024-03-09. Status: STATUS_FINAL. Neutral: False."
            # Note: Game model metadata column is not yet migrated, defaulting to generic context.
            neutral_str = "Home/Away"
            
            description = (
                f"NCAAB Game: {game.away_team} ({game.away_score}) @ {game.home_team} ({game.home_score}). "
                f"Date: {game.game_date.strftime('%Y-%m-%d')}. "
                f"Context: {neutral_str}."
            )
            
            # Metadata for filtering
            metadata = {
                "sport": "ncaab",
                "home_team": game.home_team,
                "away_team": game.away_team,
                "date": game.game_date.strftime('%Y-%m-%d'),
                "home_score": game.home_score,
                "away_score": game.away_score
            }
            
            # Upsert to Qdrant
            try:
                self.vector_store.upsert_game_scenario(
                    game_id=game.external_game_id,
                    description=description,
                    metadata=metadata,
                    collection=settings.QDRANT_COLLECTION_GAMES
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to vectorize game {game.external_game_id}: {e}")
                
        logger.info(f"Successfully vectorized {count} NCAAB games into Qdrant.")
        return count
