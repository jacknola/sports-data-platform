"""
Unit tests for data extraction utility.
"""
from datetime import datetime, timedelta, timezone
from app.models.game import Game
from app.models.bet import Bet
from app.services.data_extraction import DataExtractor

def test_fetch_historical_data(db_session):
    # Setup: Create some test data
    game1 = Game(
        external_game_id="game_1",
        sport="nba",
        home_team="LAL",
        away_team="GSW",
        game_date=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
        home_score=110,
        away_score=105
    )
    db_session.add(game1)
    db_session.flush()
    
    bet1 = Bet(
        selection_id="bet_1",
        sport="nba",
        game_id=game1.id,
        team="LAL",
        market="moneyline",
        current_odds=1.9,
        implied_prob=0.52,
        devig_prob=0.53,
        posterior_prob=0.55,
        edge=0.04
    )
    db_session.add(bet1)
    
    # Initialize extractor with test session
    extractor = DataExtractor(db_session)
    
    # Execute
    data = extractor.fetch_historical_data(sport="nba", days=7)
    
    # Verify
    assert len(data) == 1
    assert data[0]["external_game_id"] == "game_1"
    assert data[0]["home_score"] == 110
    assert len(data[0]["bets"]) == 1
    assert data[0]["bets"][0]["selection_id"] == "bet_1"
    assert data[0]["bets"][0]["edge"] == 0.04
