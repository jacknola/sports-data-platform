"""
Player profiler service for situational player analysis.
"""
from typing import Dict, Any
from loguru import logger

class PlayerProfiler:
    """
    Service for generating qualitative descriptions of player performance scenarios.
    """
    
    def generate_description(self, log_data: Dict[str, Any]) -> str:
        """
        Generate a text description of a player's situation for a specific game.
        """
        player = log_data.get("player_name", "Player")
        opp = log_data.get("opponent", "Opponent")
        is_home = "home" if log_data.get("is_home", True) else "away"
        rest = log_data.get("rest_days", 1)
        pace = log_data.get("opp_pace", 100.0)
        
        description = (
            f"{player} playing at {is_home} vs {opp}. "
            f"Rest: {rest} days. Opponent pace: {pace:.1f}."
        )
        
        return description

    def generate_metadata(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate outcome metadata for the vector store.
        """
        return {
            "player_id": log_data.get("player_id"),
            "game_id": log_data.get("game_id"),
            "outcome_pts": log_data.get("pts", 0),
            "outcome_reb": log_data.get("reb", 0),
            "outcome_ast": log_data.get("ast", 0),
            "outcome_pra": log_data.get("pra", 0),
            "outcome_fg3m": log_data.get("fg3m", 0)
        }
