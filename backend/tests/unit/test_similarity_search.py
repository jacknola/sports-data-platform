"""
Unit tests for SimilaritySearchService.
"""
from unittest.mock import MagicMock, patch
from app.services.similarity_search import SimilaritySearchService

def test_find_similar_games():
    # Setup mocks
    profiler_mock = MagicMock()
    profiler_mock.generate_description.return_value = "Mocked game description"
    
    vector_mock = MagicMock()
    vector_mock.search_similar_scenarios.return_value = [
        {"game_id": "HIST_1", "description": "Similar hist game", "outcome": "win"}
    ]
    
    with patch("app.services.similarity_search.GameProfiler", return_value=profiler_mock), \
         patch("app.services.similarity_search.VectorStoreService", return_value=vector_mock):
        
        service = SimilaritySearchService()
        results = service.find_similar_games({"any": "data"})
        
        # Verify
        assert len(results) == 1
        assert results[0]["game_id"] == "HIST_1"
        profiler_mock.generate_description.assert_called_once()
        vector_mock.search_similar_scenarios.assert_called_with("Mocked game description", limit=5)
