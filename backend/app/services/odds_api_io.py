"""
Odds-API.io Service
Integrated as a fallback provider for bulk odds (Moneyline, Spreads, Totals).
Provider: https://odds-api.io/
"""

from typing import List, Dict, Any
import httpx
from loguru import logger

class OddsApiIoService:
    BASE_URL = "https://api.odds-api.io/v3"
    
    # Map our internal sport keys to their league slugs
    LEAGUE_MAP = {
        "basketball_nba": "usa-nba",
        "basketball_ncaab": "usa-ncaa-regular-season"
    }
    
    # Map their market names to our internal keys
    MARKET_MAP = {
        "ML": "h2h",
        "Spread": "spreads",
        "Totals": "totals"
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_odds(self, sport: str) -> List[Dict[str, Any]]:
        """Fetch odds for a sport using the value-bets bulk workaround."""
        league_slug = self.LEAGUE_MAP.get(sport)
        if not league_slug:
            logger.warning(f"OddsApiIo: No league mapping for {sport}")
            return []

        logger.info(f"OddsApiIo: Fetching odds for {league_slug}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Fetch upcoming events to get team names and dates
                events_resp = await client.get(
                    f"{self.BASE_URL}/events",
                    params={
                        "apiKey": self.api_key,
                        "sport": "basketball",
                        "league": league_slug
                    }
                )
                events_resp.raise_for_status()
                events_list = events_resp.json()
                
                # Build lookup table: eventId -> event_meta
                event_lookup = {}
                for e in events_list:
                    event_lookup[e["id"]] = {
                        "home_team": e["home"],
                        "away_team": e["away"],
                        "commence_time": e["date"]
                    }

                # 2. Fetch value-bets for DraftKings (acts as bulk odds fetcher)
                # We fetch DraftKings as the primary 'retail' book
                odds_resp = await client.get(
                    f"{self.BASE_URL}/value-bets",
                    params={
                        "apiKey": self.api_key,
                        "league": league_slug,
                        "bookmaker": "DraftKings"
                    }
                )
                odds_resp.raise_for_status()
                value_bets = odds_resp.json()

                # Group by eventId
                game_odds: Dict[int, Dict[str, Any]] = {}
                
                for bet in value_bets:
                    event_id = bet["eventId"]
                    if event_id not in event_lookup:
                        continue
                        
                    if event_id not in game_odds:
                        meta = event_lookup[event_id]
                        game_odds[event_id] = {
                            "id": f"OIO_{event_id}",
                            "sport_key": sport,
                            "home_team": meta["home_team"],
                            "away_team": meta["away_team"],
                            "commence_time": meta["commence_time"],
                            "bookmakers": []
                        }
                    
                    # Create a mock bookmaker entry for DraftKings
                    # We'll also include the 'fair' odds as a 'sharp' book placeholder
                    market_name = bet["market"]["name"]
                    internal_market = self.MARKET_MAP.get(market_name)
                    if not internal_market:
                        continue
                        
                    # 1. Add DraftKings (Retail)
                    dk_book = next((b for b in game_odds[event_id]["bookmakers"] if b["key"] == "draftkings"), None)
                    if not dk_book:
                        dk_book = {"key": "draftkings", "title": "DraftKings", "markets": []}
                        game_odds[event_id]["bookmakers"].append(dk_book)
                    
                    # 2. Add 'Sharp' (using the 'market' fair odds from the API)
                    sharp_book = next((b for b in game_odds[event_id]["bookmakers"] if b["key"] == "sharp_composite"), None)
                    if not sharp_book:
                        sharp_book = {"key": "sharp_composite", "title": "Sharp Composite", "markets": []}
                        game_odds[event_id]["bookmakers"].append(sharp_book)

                    # Build outcome format
                    dk_outcomes = []
                    sharp_outcomes = []
                    
                    market_data = bet["market"]
                    bk_odds = bet["bookmakerOdds"]
                    
                    if internal_market == "h2h":
                        dk_outcomes = [
                            {"name": event_lookup[event_id]["home_team"], "price": self._dec_to_am(bk_odds.get("home"))},
                            {"name": event_lookup[event_id]["away_team"], "price": self._dec_to_am(bk_odds.get("away"))}
                        ]
                        sharp_outcomes = [
                            {"name": event_lookup[event_id]["home_team"], "price": self._dec_to_am(market_data.get("home"))},
                            {"name": event_lookup[event_id]["away_team"], "price": self._dec_to_am(market_data.get("away"))}
                        ]
                    elif internal_market == "spreads":
                        hdp = float(market_data.get("hdp", 0))
                        dk_outcomes = [
                            {"name": event_lookup[event_id]["home_team"], "price": self._dec_to_am(bk_odds.get("home")), "point": hdp},
                            {"name": event_lookup[event_id]["away_team"], "price": self._dec_to_am(bk_odds.get("away")), "point": -hdp}
                        ]
                        sharp_outcomes = [
                            {"name": event_lookup[event_id]["home_team"], "price": self._dec_to_am(market_data.get("home")), "point": hdp},
                            {"name": event_lookup[event_id]["away_team"], "price": self._dec_to_am(market_data.get("away")), "point": -hdp}
                        ]
                    elif internal_market == "totals":
                        hdp = float(market_data.get("hdp", 0))
                        dk_outcomes = [
                            {"name": "Over", "price": self._dec_to_am(bk_odds.get("over")), "point": hdp},
                            {"name": "Under", "price": self._dec_to_am(bk_odds.get("under")), "point": hdp}
                        ]
                        sharp_outcomes = [
                            {"name": "Over", "price": self._dec_to_am(market_data.get("over")), "point": hdp},
                            {"name": "Under", "price": self._dec_to_am(market_data.get("under")), "point": hdp}
                        ]

                    dk_book["markets"].append({"key": internal_market, "outcomes": dk_outcomes})
                    sharp_book["markets"].append({"key": internal_market, "outcomes": sharp_outcomes})

                result = list(game_odds.values())
                logger.info(f"OddsApiIo: Successfully processed {len(result)} games for {sport}")
                return result

        except Exception as e:
            logger.error(f"OddsApiIo error: {e}")
            return []

    def _dec_to_am(self, dec: Any) -> int:
        """Convert decimal odds string to American integer."""
        if not dec: return -110
        try:
            d = float(dec)
            if d >= 2.0:
                return int(round((d - 1) * 100))
            else:
                return int(round(-100 / (d - 1)))
        except Exception:
            return -110
