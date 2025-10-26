"""
Sports API service for fetching odds and game data
"""
from typing import Dict, Any, List
import httpx
from loguru import logger

from app.config import settings


class SportsAPIService:
    """Service for interacting with sports APIs"""
    
    def __init__(self):
        self.odds_api_key = settings.ODDSAPI_API_KEY
        self.sportsradar_key = settings.SPORTSRADAR_API_KEY
        self.base_url = "https://api.the-odds-api.com/v4"
    
    async def get_odds(self, sport: str) -> List[Dict[str, Any]]:
        """
        Fetch current odds for a sport
        
        Args:
            sport: Sport identifier (nfl, nba, mlb, etc.)
            
        Returns:
            List of odds markets
        """
        if not self.odds_api_key:
            logger.warning("Odds API key not configured")
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/sports/{sport}/odds",
                    params={
                        'regions': 'us',
                        'markets': 'h2h,spreads,totals',
                        'apiKey': self.odds_api_key
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Fetched odds for {sport}: {len(data)} games")
                return data
                
        except Exception as e:
            logger.error(f"Failed to fetch odds for {sport}: {e}")
            return []
    
    async def get_game_info(self, sport: str, game_id: str) -> Dict[str, Any]:
        """Fetch detailed game information"""
        logger.info(f"Fetching game info for {sport} game {game_id}")
        # Placeholder
        return {}

