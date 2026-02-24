"""
Data extraction utility for historical game and bet data.
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from app.models.game import Game
from app.models.bet import Bet
from loguru import logger

class DataExtractor:
    """
    Service for extracting historical data for analysis.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def fetch_historical_data(self, sport: str = "nba", days: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch historical games and their associated bets.
        
        Args:
            sport: The sport to filter by.
            days: Number of days of historical data to fetch.
            
        Returns:
            A list of game dictionaries with nested bet data.
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        logger.info(f"Fetching historical {sport} data for the last {days} days (since {start_date})")
        
        # Query games with their bets
        games = (
            self.db.query(Game)
            .filter(Game.sport == sport)
            .filter(Game.game_date >= start_date)
            .filter(Game.home_score.isnot(None))  # Only completed games
            .filter(Game.away_score.isnot(None))
            .options(joinedload(Game.bets))
            .all()
        )
        
        result = []
        for game in games:
            game_data = {
                "id": game.id,
                "external_game_id": game.external_game_id,
                "sport": game.sport,
                "home_team": game.home_team,
                "away_team": game.away_team,
                "game_date": game.game_date,
                "home_score": game.home_score,
                "away_score": game.away_score,
                "bets": []
            }
            
            for bet in game.bets:
                bet_data = {
                    "id": bet.id,
                    "selection_id": bet.selection_id,
                    "team": bet.team,
                    "market": bet.market,
                    "current_odds": bet.current_odds,
                    "implied_prob": bet.implied_prob,
                    "devig_prob": bet.devig_prob,
                    "posterior_prob": bet.posterior_prob,
                    "edge": bet.edge,
                    "features": bet.features
                }
                game_data["bets"].append(bet_data)
            
            result.append(game_data)
            
        logger.info(f"Successfully fetched {len(result)} games")
        return result
