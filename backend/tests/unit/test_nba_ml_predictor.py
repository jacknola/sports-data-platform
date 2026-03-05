
import pytest
from app.services.nba_ml_predictor import NBAMLPredictor

@pytest.mark.asyncio
async def test_predict_game_output_types():
    """
    Test that the output of predict_game has the correct data types.
    This test is designed to fail if numpy types are returned instead of standard Python floats.
    """
    predictor = NBAMLPredictor()

    # Mock features
    features = {
        "home_off_rating": 115.0,
        "home_def_rating": 110.0,
        "away_off_rating": 112.0,
        "away_def_rating": 114.0,
        "home_win_pct": 0.6,
        "away_win_pct": 0.4,
        "home_pace": 100.0,
        "away_pace": 100.0,
        "odds": {"home": -150, "away": 130}
    }

    prediction = await predictor.predict_game("Home Team", "Away Team", features)

    # Check moneyline prediction types
    ml_pred = prediction.get("moneyline_prediction", {})
    assert isinstance(ml_pred.get("home_win_prob"), float), "home_win_prob should be a float"
    assert isinstance(ml_pred.get("away_win_prob"), float), "away_win_prob should be a float"
    assert isinstance(ml_pred.get("confidence"), float), "confidence should be a float"

    # Check for core prediction keys (spread/total/book added by predict_today_games, not predict_game)
    assert "expected_value" in prediction, "expected_value key should be in prediction"
    assert "kelly_criterion" in prediction, "kelly_criterion key should be in prediction"
    assert "method" in prediction, "method key should be in prediction"

@pytest.mark.asyncio
async def test_graceful_degradation_without_odds():
    """
    Test that predict_today_games returns predictions even when odds_data is empty.
    """
    predictor = NBAMLPredictor()

    # Mock SportsAPIService to return no odds
    class MockDiscoveryResult:
        def __init__(self, data):
            self.data = data
            self.source = "mock"

    class MockSportsAPIService:
        async def get_odds(self, sport):
            return []
        async def discover_games(self, sport):
            return MockDiscoveryResult([{"home_team": "Team A", "away_team": "Team B"}])

    predictor.sports_api = MockSportsAPIService()

    predictions = await predictor.predict_today_games()

    assert len(predictions) > 0, "Should return predictions even without odds"
    assert "moneyline_prediction" in predictions[0], "Prediction should have moneyline data"

    # Check that default odds were used
    ev = predictions[0].get("expected_value", {})
    assert ev.get("home_odds") == -110
    assert ev.get("away_odds") == -110

    # Check that spread/total metadata was attached
    assert "spread" in predictions[0], "spread key should be in prediction"
    assert "total" in predictions[0], "total key should be in prediction"
