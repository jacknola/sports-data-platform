"""
Unit tests for GameProfiler.
"""
import pytest
from app.services.game_profiler import GameProfiler

def test_generate_profile_description():
    game_data = {
        "home_team": "LAL",
        "away_team": "GSW",
        "spread": -1.5,
        "open_spread": -3.5,
        "home_ticket_pct": 0.75,
        "home_money_pct": 0.45,
        "sport": "nba"
    }
    
    profiler = GameProfiler()
    description = profiler.generate_description(game_data)
    
    # Verify description contains key situational markers
    assert "LAL" in description
    assert "favorite" in description.lower()
    assert "reverse line movement" in description.lower()
    assert "public heavy" in description.lower()
