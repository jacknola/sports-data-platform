import argparse
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from app.services.elo_service import EloService
from app.services.ml.data_fetcher import HistoricalDataFetcher


def backfill_elo(sport: str, start_year: int, end_year: int) -> int:
    elo = EloService(sport=sport)
    fetcher = HistoricalDataFetcher()

    games_df = fetcher.fetch_nba_games_paired(start_year=start_year, end_year=end_year)
    if games_df.empty:
        logger.warning("No historical games fetched for Elo backfill")
        return 0

    games: List[Dict] = []
    for _, row in games_df.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]
        home_score = row["home_score"]
        away_score = row["away_score"]
        if not home_team or not away_team:
            continue
        if home_score is None or away_score is None:
            continue
        games.append(
            {
                "home_team": str(home_team),
                "away_team": str(away_team),
                "home_score": int(home_score),
                "away_score": int(away_score),
            }
        )

    elo.backfill_season(games)
    elo.save()
    logger.info(f"Backfilled Elo games: {len(games)}")
    logger.info(f"Top teams: {elo.get_top_teams(10)}")
    return len(games)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Elo ratings")
    parser.add_argument("--sport", default="nba", choices=["nba", "ncaab"])
    parser.add_argument("--seasons", default="2018-2025", help="format YYYY-YYYY")
    args = parser.parse_args()

    try:
        start_year, end_year = map(int, args.seasons.split("-"))
    except Exception:
        start_year, end_year = 2018, 2025

    count = backfill_elo(args.sport, start_year, end_year)
    logger.info(f"Elo backfill complete ({count} games)")


if __name__ == "__main__":
    main()
