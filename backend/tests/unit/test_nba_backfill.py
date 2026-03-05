"""
Unit tests for NBA historical data backfill.
"""
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.services.nba_backfill import NBABackfillService
from app.models.game import Game

def test_backfill_nba_data(db_session):
    # Setup mocks for nba_api
    mock_game_finder = MagicMock()
    # Mock return data for leaguegamefinder
    mock_game_finder.get_data_frames.return_value = [
        MagicMock(to_dict=lambda orient: [
            {
                "GAME_ID": "0022300001",
                "GAME_DATE": "2023-10-24",
                "MATCHUP": "LAL @ GSW",
                "PTS": 107,
                "TEAM_ABBREVIATION": "LAL"
            },
            {
                "GAME_ID": "0022300001",
                "GAME_DATE": "2023-10-24",
                "MATCHUP": "GSW vs LAL",
                "PTS": 108,
                "TEAM_ABBREVIATION": "GSW"
            }
        ])
    ]
    
    mock_module = MagicMock()
    mock_module.LeagueGameFinder = MagicMock(return_value=mock_game_finder)
    with patch("app.services.nba_backfill.leaguegamefinder", mock_module):
        service = NBABackfillService(db_session)
        count = service.backfill_season("2023-24")
        
        # Verify
        assert count == 1
        game = db_session.query(Game).filter_by(external_game_id="NBA_0022300001").first()
        assert game is not None
        assert game.home_team == "GSW"
        assert game.away_team == "LAL"
        assert game.home_score == 108
        assert game.away_score == 107
