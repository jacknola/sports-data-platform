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
            "id": 1,
            "home_team": "LAL",
            "away_team": "GSW",
            "home_score": 110,
            "away_score": 105,
            "bets": [
                {
                    "selection_id": "bet_1",
                    "team": "LAL",
                    "market": "moneyline",
                    "current_odds": 1.9,
                    "implied_prob": 0.52,
                    "devig_prob": 0.53,
                    "posterior_prob": 0.55,
                    "edge": 0.04
                },
                {
                    "selection_id": "bet_2",
                    "team": "GSW",
                    "market": "moneyline",
                    "current_odds": 2.1,
                    "implied_prob": 0.48,
                    "devig_prob": 0.47,
                    "posterior_prob": 0.45,
                    "edge": -0.02
                }
            ]
        }
    ]
    
    with patch("app.services.comparison_runner.DataExtractor", return_value=extractor_mock):
        runner = ComparisonRunner(mock_db)
        results = runner.run_comparison(sport="nba", days=7)
        
        # Verify
        assert "bayesian" in results
        assert "random_forest" in results
        assert results["bayesian"]["total_bets"] == 2
        assert results["random_forest"]["total_bets"] == 2
