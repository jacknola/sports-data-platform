"""
Unit tests for VectorStoreService.
"""
from unittest.mock import MagicMock
from app.services.vector_store import VectorStoreService


def test_upsert_and_search():
    service = VectorStoreService()

    game_id = "TEST_GAME_1"
    description = "Home underdog on back-to-back vs sharp money move"
    metadata = {"outcome": "covered", "spread_move": -1.5}

    # Configure mock client so query_points returns a realistic hit.
    # qdrant_client is a MagicMock stub in the test environment, so the
    # real Qdrant server is not used — we wire the expected return value.
    mock_hit = MagicMock()
    mock_hit.payload = {"game_id": game_id, **metadata}
    mock_result = MagicMock()
    mock_result.points = [mock_hit]
    service.client.query_points.return_value = mock_result

    # Execute
    service.upsert_game_scenario(game_id, description, metadata)

    # Search
    results = service.search_similar_scenarios("underdog vs sharp money", limit=1)

    # Verify
    assert len(results) > 0
    assert results[0]["game_id"] == game_id
    assert results[0]["outcome"] == "covered"
