"""
Unit tests for VectorStoreService.
"""
import pytest
from app.services.vector_store import VectorStoreService

def test_upsert_and_search():
    service = VectorStoreService()
    
    game_id = "TEST_GAME_1"
    description = "Home underdog on back-to-back vs sharp money move"
    metadata = {"outcome": "covered", "spread_move": -1.5}
    
    # Execute
    service.upsert_game_scenario(game_id, description, metadata)
    
    # Search
    results = service.search_similar_scenarios("underdog vs sharp money", limit=1)
    
    # Verify
    assert len(results) > 0
    assert results[0]["game_id"] == game_id
    assert results[0]["outcome"] == "covered"
