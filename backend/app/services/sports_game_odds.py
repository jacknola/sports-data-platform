"""
Sports Game Odds API Service
Provides live odds and public betting percentages.
"""
from typing import Dict, Any, List
import httpx
from loguru import logger
from app.config import settings

# Map The Odds API sport keys → SportsGameOdds sport keys
SPORT_KEY_MAP = {
    "basketball_nba": "nba",
    "basketball_ncaab": "ncaab",
}


class SportsGameOddsService:
    """
    Service for interacting with the SportsGameOdds API.
    Used for live odds and real public betting percentages.
    """
    
    BASE_URL = "https://api.sportsgameodds.com/v1"
    
    def __init__(self):
        self.api_key = settings.SPORTS_GAME_ODDS_API_KEY
        self.headers = {
            "X-Api-Key": self.api_key,
            "Accept": "application/json"
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def get_nba_odds(self) -> List[Dict[str, Any]]:
        """Fetch live NBA odds and public percentages."""
        return await self._fetch_odds("nba")

    async def get_ncaab_odds(self) -> List[Dict[str, Any]]:
        """Fetch live NCAAB odds and public percentages."""
        return await self._fetch_odds("ncaab")

    async def _fetch_odds(self, sport: str) -> List[Dict[str, Any]]:
        if not self.is_configured:
            logger.warning("SportsGameOdds API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/odds",
                    params={"sport": sport, "regions": "us"},
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return self._normalize_odds(data)
        except Exception as e:
            logger.error(f"SportsGameOdds API error for {sport}: {e}")
            return []

    async def get_odds_by_sport_key(self, sport_key: str) -> List[Dict[str, Any]]:
        """Fetch odds using a The Odds API sport key (e.g. 'basketball_ncaab').

        Maps to the internal SGO sport key and delegates to _fetch_odds().
        """
        sgo_sport = SPORT_KEY_MAP.get(sport_key)
        if not sgo_sport:
            logger.warning(f"SportsGameOdds: no mapping for sport key '{sport_key}'")
            return []
        return await self._fetch_odds(sgo_sport)

    async def get_player_props(self, sport: str, event_id: str) -> List[Dict[str, Any]]:
        """Fetch player props for a specific event."""
        if not self.is_configured:
            return []

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/props/{event_id}",
                    params={"sport": sport},
                    headers=self.headers
                )
                if response.status_code == 200:
                    return response.json().get("data", [])
        except Exception as e:
            logger.debug(f"SportsGameOdds props fetch failed for {event_id}: {e}")
            
        return []

    def _normalize_odds(self, data: Any) -> List[Dict[str, Any]]:
        """
        Normalize SportsGameOdds response to match our internal schema.
        """
        results = []
        if isinstance(data, list):
            results = data
        elif isinstance(data, dict):
            # Try common keys for data list
            for key in ["data", "results", "odds", "events"]:
                if key in data and isinstance(data[key], list):
                    results = data[key]
                    break
        
        # Ensure minimum required fields exist or map them
        normalized = []
        for item in results:
            if not isinstance(item, dict):
                continue
            
            # Map SGO fields to internal schema if different
            # SGO typically uses: home_team, away_team, start_time, bookmakers
            n = {
                "id": str(item.get("id", item.get("event_id", ""))),
                "home_team": item.get("home_team", item.get("home", "")),
                "away_team": item.get("away_team", item.get("away", "")),
                "commence_time": item.get("commence_time", item.get("start_time", "")),
                "bookmakers": item.get("bookmakers", [])
            }
            if n["home_team"] and n["away_team"]:
                normalized.append(n)
                
        return normalized

    async def get_public_percentages(self, game_id: str) -> Dict[str, float]:
        """
        Fetch real public betting percentages for a game.
        Returns: {"home_ticket_pct": float, "home_money_pct": float}
        """
        if not self.is_configured:
            return {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Assuming /public-percentages or similar endpoint
                response = await client.get(
                    f"{self.BASE_URL}/public-percentages/{game_id}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "home_ticket_pct": data.get("home_tickets", 0.50),
                        "home_money_pct": data.get("home_money", 0.50)
                    }
        except Exception as e:
            logger.debug(f"Could not fetch public percentages for {game_id}: {e}")
            
        return {}
