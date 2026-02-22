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
                        "regions": "us",
                        "markets": "h2h,spreads,totals",
                        "apiKey": self.odds_api_key,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                logger.info(f"Fetched odds for {sport}: {len(data)} games")
                return data

        except Exception as e:
            logger.error(f"Failed to fetch odds for {sport}: {e}")
            return []

    async def get_scores(self, sport: str, days_from: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch completed game scores for a sport over the last N days.

        Args:
            sport: Sport identifier (e.g. 'basketball_ncaab')
            days_from: Number of days to look back

        Returns:
            List of completed game score objects
        """
        if not self.odds_api_key:
            logger.warning("Odds API key not configured")
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/sports/{sport}/scores",
                    params={
                        "daysFrom": days_from,
                        "apiKey": self.odds_api_key,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                # Filter only for games that are marked as completed
                completed = [g for g in data if g.get("completed")]
                logger.info(
                    f"Fetched scores for {sport}: {len(completed)} completed games in last {days_from} days"
                )
                return completed

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error fetching scores for {sport}: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch scores for {sport}: {e}")
            return []
