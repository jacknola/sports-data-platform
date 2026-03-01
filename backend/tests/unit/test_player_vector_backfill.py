"""
Unit tests for player vector backfill service.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.player_vector_backfill import PlayerVectorBackfillService
from app.models.player_game_log import PlayerGameLog
from app.models.player import Player

def test_backfill_all_player_vectors(db_session):
    # Setup test data
    player = Player(external_player_id="9999", name="Test Player", sport="nba")
    db_session.add(player)
    
    log = PlayerGameLog(
        player_id=player.id,
        external_log_id="NBA_LOG_VECTOR_TEST",
        pts=25,
        pra=40
    )
    db_session.add(log)
    
    # Mock VectorStore
    vector_mock = MagicMock()
    
    with patch("app.services.player_vector_backfill.VectorStoreService", return_value=vector_mock):
        service = PlayerVectorBackfillService(db_session)
        count = service.backfill_all_logs()
        
        assert count >= 1
        vector_mock.upsert_game_scenario.assert_called()
        # Verify collection name
        args, kwargs = vector_mock.upsert_game_scenario.call_args
        assert kwargs["collection"] == "player_performances"
