"""
Unit tests for comparison runner service.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.comparison_runner import ComparisonRunner

@pytest.fixture
def mock_db():
    return MagicMock()

def test_run_comparison(mock_db):
    # Setup mocks
    extractor_mock = MagicMock()
    extractor_mock.fetch_historical_data.return_value = [
        {
            "id": i,
            "home_team": f"TeamA_{i}",
            "away_team": f"TeamB_{i}",
            "home_score": 110 if i % 2 == 0 else 100,
            "away_score": 100 if i % 2 == 0 else 110,
            "bets": [
                {
                    "selection_id": f"bet_{i}_1",
                    "team": f"TeamA_{i}",
                    "market": "moneyline",
                    "current_odds": 1.9,
                    "implied_prob": 0.52,
                    "devig_prob": 0.53,
                    "posterior_prob": 0.55,
                    "edge": 0.04
                },
                {
                    "selection_id": f"bet_{i}_2",
                    "team": f"TeamB_{i}",
                    "market": "moneyline",
                    "current_odds": 2.1,
                    "implied_prob": 0.48,
                    "devig_prob": 0.47,
                    "posterior_prob": 0.45,
                    "edge": -0.02
                }
            ]
        } for i in range(10) # 10 games * 2 bets = 20 bets
    ]
    
    with patch("app.services.comparison_runner.DataExtractor", return_value=extractor_mock):
        runner = ComparisonRunner(mock_db)
        results = runner.run_comparison(sport="nba", days=7)
        
        # Verify
        assert "bayesian" in results
        assert "random_forest" in results
        assert results["bayesian"]["total_bets"] == 10  # stats engine counts per-game
        assert results["random_forest"]["total_bets"] == 10
