"""
Game profiler service for situational analysis.
"""
from typing import Dict, Any

class GameProfiler:
    """
    Service for generating qualitative descriptions of game scenarios.
    """
    
    def generate_description(self, game_data: Dict[str, Any]) -> str:
        """
        Generate a text description of a game scenario based on stats and moves.
        """
        home = game_data.get("home_team", "Home")
        away = game_data.get("away_team", "Away")
        spread = game_data.get("spread", 0.0)
        open_spread = game_data.get("open_spread", 0.0)
        h_tickets = game_data.get("home_ticket_pct", 0.5)
        h_money = game_data.get("home_money_pct", 0.5)
        
        # 1. Determine favorite
        fav = home if spread < 0 else away
        
        # 2. Determine line move
        move = spread - open_spread
        move_desc = "steady line"
        if move < -1.0: move_desc = f"line moving toward {home}"
        elif move > 1.0: move_desc = f"line moving toward {away}"
        
        # 3. Detect RLM
        rlm_desc = ""
        if h_tickets > 0.65 and h_money < 0.50 and move > 0.5:
            rlm_desc = f"Reverse Line Movement against heavily bet {home}."
        elif (1-h_tickets) > 0.65 and (1-h_money) < 0.50 and move < -0.5:
            rlm_desc = f"Reverse Line Movement against heavily bet {away}."
            
        # 4. Public splits
        public_desc = "balanced action"
        if h_tickets > 0.70: public_desc = f"public heavy on {home}"
        elif h_tickets < 0.30: public_desc = f"public heavy on {away}"
        
        description = (
            f"A {game_data.get('sport', 'sports')} matchup between {away} and {home}. "
            f"{fav} is the favorite. {move_desc} with {public_desc}. {rlm_desc}"
        ).strip()
        
        return description
