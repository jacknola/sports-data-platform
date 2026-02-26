"""
Balldontlie API Historical Data Backfill

Imports historical NBA games (2007-2025) from balldontlie.io API.
Free tier: limited historical data, but game results are available.

Usage:
    python3 run_balldontlie_backfill.py --start-year 2007 --end-year 2025
    python3 run_balldontlie_backfill.py --dry-run  # Preview without saving
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
from app.models.historical_game_line import HistoricalGameLine


BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"


def get_bdl_headers() -> Dict[str, str]:
    """Return headers for balldontlie.io requests."""
    headers = {"Accept": "application/json"}
    if settings.BALLDONTLIE_API_KEY:
        headers["Authorization"] = settings.BALLDONTLIE_API_KEY
    return headers


async def fetch_games_for_date(
    client: httpx.AsyncClient, date: str
) -> List[Dict[str, Any]]:
    """Fetch all games for a given date (YYYY-MM-DD)."""
    try:
        response = await client.get(
            f"{BALLDONTLIE_BASE}/games",
            params={"dates[]": date, "per_page": 100},
            headers=get_bdl_headers(),
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        elif response.status_code == 429:
            logger.warning("Rate limited by balldontlie API")
            await asyncio.sleep(60)
            return []
        else:
            logger.error(f"API error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching games for {date}: {e}")
        return []


def transform_game_to_model(
    game: Dict[str, Any], source: str = "balldontlie"
) -> Dict[str, Any]:
    """Transform balldontlie game data to HistoricalGameLine model."""
    home = game.get("home_team", {})
    away = game.get("away_team", {})

    home_score = game.get("home_team_score")
    away_score = game.get("away_team_score")

    return {
        "game_date": datetime.fromisoformat(game["date"].replace("Z", "+00:00")),
        "season": game.get("season"),
        "home_team": home.get("full_name") if isinstance(home, dict) else str(home),
        "away_team": away.get("full_name") if isinstance(away, dict) else str(away),
        "home_score": home_score,
        "away_score": away_score,
        "total_score": (home_score + away_score) if home_score and away_score else None,
        "margin": (home_score - away_score) if home_score and away_score else None,
        "source": source,
        "external_game_id": str(game.get("id")),
        "raw_data": game,
    }


def save_games_to_db(games: List[Dict[str, Any]], db: Session) -> int:
    """Save transformed games to database. Returns count of new records."""
    saved = 0
    for game_data in games:
        existing = (
            db.query(HistoricalGameLine)
            .filter(
                HistoricalGameLine.external_game_id == game_data["external_game_id"],
                HistoricalGameLine.source == game_data["source"],
            )
            .first()
        )

        if not existing:
            record = HistoricalGameLine(**game_data)
            db.add(record)
            saved += 1

    db.commit()
    return saved


async def run_backfill(
    start_year: int = 2007, end_year: int = 2025, dry_run: bool = False
):
    """Main backfill function."""
    logger.info(f"Starting balldontlie backfill: {start_year}-{end_year}")

    db = SessionLocal()
    total_saved = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for year in range(start_year, end_year + 1):
                for month in range(10, 13):  # Oct-Dec (season start)
                    for day in range(1, 32):
                        try:
                            date = f"{year}-{month:02d}-{day:02d}"
                            games = await fetch_games_for_date(client, date)

                            if games:
                                transformed = [
                                    transform_game_to_model(g) for g in games
                                ]

                                if not dry_run:
                                    saved = save_games_to_db(transformed, db)
                                    total_saved += saved
                                    logger.info(
                                        f"{date}: {len(games)} games, {saved} new"
                                    )
                                else:
                                    logger.info(f"{date}: {len(games)} games (dry run)")

                                # Conservative rate limit for new API key
                                await asyncio.sleep(2.0)

                        except Exception as e:
                            logger.error(f"Error processing {year}-{month}: {e}")
                            continue

                # Jan-Sep (season continuation)
                for month in range(1, 10):
                    for day in range(1, 32):
                        try:
                            date = f"{year}-{month:02d}-{day:02d}"
                            games = await fetch_games_for_date(client, date)

                            if games:
                                transformed = [
                                    transform_game_to_model(g) for g in games
                                ]

                                if not dry_run:
                                    saved = save_games_to_db(transformed, db)
                                    total_saved += saved
                                    logger.info(
                                        f"{date}: {len(games)} games, {saved} new"
                                    )
                                else:
                                    logger.info(f"{date}: {len(games)} games (dry run)")

                                # Conservative rate limit for new API key
                                await asyncio.sleep(2.0)

                        except Exception as e:
                            continue

                logger.info(f"Completed year {year}")

    finally:
        db.close()

    logger.info(f"Backfill complete. Total new records: {total_saved}")
    return total_saved


def main():
    parser = argparse.ArgumentParser(
        description="Balldontlie historical NBA data backfill"
    )
    parser.add_argument(
        "--start-year", type=int, default=2007, help="Start year (e.g., 2007)"
    )
    parser.add_argument(
        "--end-year", type=int, default=2025, help="End year (e.g., 2025)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without saving to DB"
    )
    args = parser.parse_args()

    if not settings.BALLDONTLIE_API_KEY:
        logger.warning("BALLDONTLIE_API_KEY not set - API calls may be rate limited")

    asyncio.run(run_backfill(args.start_year, args.end_year, args.dry_run))


if __name__ == "__main__":
    main()
