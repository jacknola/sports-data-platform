"""
Similarity search service for finding historical game analogs.
"""
from typing import List, Dict, Any
from app.services.game_profiler import GameProfiler
from app.services.vector_store import VectorStoreService
from loguru import logger

def find_similar_games(game_data: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Module-level convenience wrapper around SimilaritySearchService.find_similar_games."""
    service = SimilaritySearchService()
    return service.find_similar_games(game_data, limit=limit)


class SimilaritySearchService:
    """
    Service for identifying historical games similar to current scenarios.
    """
    
    def __init__(self):
        self.profiler = GameProfiler()
        self.vector_store = VectorStoreService()

    def find_similar_games(self, game_data: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find historical analogs for a given game.
        """
        description = self.profiler.generate_description(game_data)
        logger.info(f"Searching for historical analogs for: {description}")
        
        results = self.vector_store.search_similar_scenarios(description, limit=limit)
        return results
