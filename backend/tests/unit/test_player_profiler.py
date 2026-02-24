"""
Unit tests for PlayerProfiler.
"""
import pytest
from app.services.player_profiler import PlayerProfiler

def test_generate_player_description():
    log_data = {
        "player_name": "LeBron James",
        "opponent": "GSW",
        "is_home": True,
        "rest_days": 1,
        "opp_pace": 102.5,
        "pts": 25,
        "pra": 40
    }
    
    profiler = PlayerProfiler()
    description = profiler.generate_description(log_data)
    
    assert "LeBron James" in description
    assert "home" in description.lower()
    assert "GSW" in description
    assert "102.5" in description
    
    metadata = profiler.generate_metadata(log_data)
    assert metadata["outcome_pts"] == 25
    assert metadata["outcome_pra"] == 40
