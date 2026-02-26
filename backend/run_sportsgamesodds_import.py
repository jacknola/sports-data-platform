"""
SportsGameOdds API Historical Props Import

Imports player props from sportsgameodds.com API.
Note: Free tier provides CURRENT odds only - historical data requires paid tier.

Usage:
    python3 run_sportsgamesodds_import.py --start-date 2024-01-01 --end-date 2024-12-31
    python3 run_sportsgamesodds_import.py --dry-run
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings
from app.models.historical_player_prop import HistoricalPlayerProp


class SportsGameOddsClient:
    """Handle props from SportsGameOdds API v2."""

    BASE_URL = "https://api.sportsgameodds.com/v2"

    def __init__(self):
        self.api_key = settings.SPORTS_GAME_ODDS_API_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_events(
        self, league: str = "NBA", date: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch events (games) with odds for a given date."""
        if not self.is_configured:
            logger.warning("SportsGameOdds API key not configured")
            return []

        params = {
            "apiKey": self.api_key,
            "league": league,
            "limit": limit,
            "oddsAvailable": "true",
        }

        if date:
            params["date"] = date

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.BASE_URL}/events", params=params)

                if response.status_code == 200:
                    data = response.json()
                    return data if isinstance(data, list) else data.get("data", [])
                elif response.status_code == 429:
                    logger.warning("Rate limited, waiting 60s...")
                    await asyncio.sleep(60)
                    return []
                elif response.status_code == 401:
                    logger.error("Invalid API key")
                    return []
                else:
                    logger.error(
                        f"API error {response.status_code}: {response.text[:200]}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Request error: {e}")
            return []

    def extract_props_from_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract player props from an event's odds."""
        props = []

        # Navigate to player props in the response structure
        # Based on API docs: events contain markets, which contain outcomes
        markets = event.get("markets", [])

        for market in markets:
            market_name = market.get("name", "")

            # Player props typically have names like "Player Points", "Player Rebounds", etc.
            if "Player " not in market_name:
                continue

            outcomes = market.get("outcomes", [])
            if len(outcomes) < 2:
                continue

            # Extract prop type from market name (e.g., "Player Points" -> "points")
            prop_type = market_name.replace("Player ", "").lower()

            # Get game info
            home_team = event.get("homeTeam", {}).get("name", "")
            away_team = event.get("awayTeam", {}).get("name", "")
            game_date = event.get("startDate", "")

            for outcome in outcomes:
                # Props have over/under outcomes
                side = outcome.get("side", "").lower()  # "over" or "under"
                if side not in ["over", "under"]:
                    continue

                player = outcome.get("participant", {}).get("name", "")
                if not player:
                    continue

                # Find the line (the line is usually in the other outcome)
                line = None
                odds = outcome.get("odds", 0)

                # Find the paired outcome to get the line
                for other in outcomes:
                    if other.get("side", "").lower() != side:
                        line = other.get("line") or other.get("point")
                        break

                if line is None:
                    line = outcome.get("line") or outcome.get("point")

                prop = {
                    "player_name": player,
                    "team": "",  # Need to determine from player team
                    "opponent": home_team if away_team == player else away_team,
                    "game_date": game_date,
                    "prop_type": prop_type,
                    "stat_type": side,
                    "line": line,
                    "over_odds": odds if side == "over" else None,
                    "under_odds": odds if side == "under" else None,
                    "sportsbook": outcome.get("bookmaker", {}).get(
                        "name", "SportsGameOdds"
                    ),
                    "external_prop_id": f"{event.get('id')}_{player}_{prop_type}_{side}",
                    "raw_data": outcome,
                }
                props.append(prop)

        return props

    async def fetch_props_for_date_range(
        self, start_date: str, end_date: str, sportsbook: str = "draftkings"
    ) -> List[Dict[str, Any]]:
        """Fetch props for a date range."""
        all_props = []

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            logger.info(f"Fetching props for {date_str}...")

            events = await self.fetch_events(date=date_str)

            for event in events:
                props = self.extract_props_from_event(event)
                all_props.extend(props)

            current += timedelta(days=1)
            await asyncio.sleep(1)  # Rate limiting

        logger.info(f"Total props fetched: {len(all_props)}")
        return all_props


def transform_prop_to_model(
    prop: Dict[str, Any], sportsbook: str, source: str = "sportsgamesodds"
) -> Dict[str, Any]:
    """Transform SportsGameOdds prop data to HistoricalPlayerProp model."""

    player = prop.get("player", {})
    game = prop.get("game", {})

    return {
        "player_name": player.get("name", ""),
        "player_id": player.get("id"),
        "team": player.get("team", ""),
        "opponent": game.get("opponent", ""),
        "game_date": datetime.fromisoformat(
            game.get("date", datetime.now().isoformat()).replace("Z", "+00:00")
        ),
        "season": game.get("season"),
        "prop_type": prop.get("type", ""),  # points, rebounds, assists, etc.
        "stat_type": prop.get("bet_type", "over"),  # over/under
        "line": prop.get("line", 0.0),
        "over_odds": prop.get("over_odds"),
        "under_odds": prop.get("under_odds"),
        "over_price": prop.get("over_price"),
        "under_price": prop.get("under_price"),
        "actual": prop.get("result", {}).get("actual"),
        "result": prop.get("result", {}).get("outcome"),
        "sportsbook": sportsbook,
        "source": source,
        "external_prop_id": str(prop.get("id", "")),
        "raw_data": prop,
    }


def save_props_to_db(props: List[Dict[str, Any]], db: Session) -> int:
    """Save transformed props to database. Returns count of new records."""
    saved = 0
    for prop_data in props:
        existing = (
            db.query(HistoricalPlayerProp)
            .filter(
                HistoricalPlayerProp.external_prop_id == prop_data["external_prop_id"]
            )
            .first()
        )

        if not existing:
            record = HistoricalPlayerProp(**prop_data)
            db.add(record)
            saved += 1

    db.commit()
    return saved


async def run_import(
    start_date: str,
    end_date: str,
    sportsbook: str = "draftkings",
    dry_run: bool = False,
):
    """Main import function."""
    logger.info(f"Starting SportsGameOdds import: {start_date} to {end_date}")

    service = SportsGameOddsHistorical()

    if not service.is_configured:
        logger.error("SportsGameOdds API key not configured")
        return 0

    props = await service.fetch_historical_props(
        sport="nba", start_date=start_date, end_date=end_date, sportsbook=sportsbook
    )

    logger.info(f"Fetched {len(props)} props from API")

    if not props:
        logger.warning("No props fetched. Check API tier for historical data access.")
        return 0

    transformed = [transform_prop_to_model(p, sportsbook) for p in props]

    if dry_run:
        logger.info(f"Dry run: {len(transformed)} props ready to import")
        return len(transformed)

    db = SessionLocal()
    try:
        saved = save_props_to_db(transformed, db)
        logger.info(f"Import complete. New records: {saved}")
        return saved
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="SportsGameOdds historical player props import"
    )
    parser.add_argument(
        "--start-date", type=str, required=True, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", type=str, required=True, help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--sportsbook",
        type=str,
        default="draftkings",
        help="Sportsbook (default: draftkings)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    asyncio.run(
        run_import(args.start_date, args.end_date, args.sportsbook, args.dry_run)
    )


if __name__ == "__main__":
    main()
