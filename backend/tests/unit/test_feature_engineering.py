"""
Unit tests for feature engineering utility.
"""
import pytest
import pandas as pd
from app.services.feature_engineering import FeatureEngineer

def test_prepare_features():
    # Setup: Mock data from DataExtractor
    data = [
        {
            "id": 1,
            "home_team": "LAL",
            "away_team": "GSW",
            "home_score": 110,
            "away_score": 105,
            "bets": [
                {
                    "team": "LAL",
                    "market": "moneyline",
                    "current_odds": 1.9,
                    "implied_prob": 0.52,
                    "devig_prob": 0.53,
                    "posterior_prob": 0.55,
                    "edge": 0.04
                }
            ]
        }
    ]
    
    engineer = FeatureEngineer()
    
    # Execute
    X, y = engineer.prepare_features(data)
    
    # Verify
    assert isinstance(X, pd.DataFrame)
    assert len(X) == 1
    assert "implied_prob" in X.columns
    assert "is_home" in X.columns
    assert y[0] == 1  # LAL won
