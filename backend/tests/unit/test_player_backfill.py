"""
Unit tests for NBA player historical data backfill.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.services.player_backfill import NBAPlayerBackfillService
from app.models.player_game_log import PlayerGameLog
from app.models.player import Player

def test_backfill_player_logs(db_session):
    # Setup test player
    player = Player(external_player_id="2544", name="LeBron James", sport="nba")
    db_session.add(player)
    db_session.commit()
    
    # Mock nba_api playergamelog
    mock_gamelog = MagicMock()
    mock_gamelog.get_data_frames.return_value = [
        MagicMock(iterrows=lambda: iter([
            (0, {
                "Game_ID": "9999999",
                "GAME_DATE": "OCT 24, 2023",
                "MATCHUP": "LAL @ GSW",
                "PTS": 21,
                "REB": 8,
                "AST": 5,
                "MIN": "30",
                "STL": 1,
                "BLK": 0,
                "TOV": 3,
                "FG3M": 1
            })
        ]))
    ]
    
    mock_module = MagicMock()
    mock_module.PlayerGameLog = MagicMock(return_value=mock_gamelog)
    with patch("app.services.player_backfill.playergamelog", mock_module):
        service = NBAPlayerBackfillService(db_session)
        count = service.backfill_player(player.id, "2023-24")
        
        # Verify
        assert count == 1
        log = db_session.query(PlayerGameLog).filter_by(player_id=player.id).first()
        assert log is not None
        assert log.pts == 21
        assert log.pra == 34 # 21+8+5
