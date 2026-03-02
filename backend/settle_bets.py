#!/usr/bin/env python3
"""
settle_bets.py - Settle pending bets against actual game results.

Matches pending bets in SQLite against final scores in PostgreSQL,
then marks each bet won/lost/push based on market type.

Usage:
    python backend/settle_bets.py              # Settle all pending bets
    python backend/settle_bets.py --dry-run    # Preview without saving
    python backend/settle_bets.py --days 7     # Also fetch fresh scores from Odds API
"""

import sys
import os
import sqlite3
import asyncio
import argparse
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from sqlalchemy import create_engine, text
from app.config import settings
from app.services.bet_tracker import BetTracker, LOCAL_DB_PATH

# Map sport keys to Odds API format for fresh score fetching
SPORT_SCORE_KEYS = {
    "ncaab": "basketball_ncaab",
    "nba": "basketball_nba",
}


def _load_pending_bets() -> List[Dict]:
    """Load all pending bets from the SQLite tracker."""
    if not os.path.exists(LOCAL_DB_PATH):
        logger.warning(f"No bets DB found at {LOCAL_DB_PATH}")
        return []
    with sqlite3.connect(LOCAL_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM bets WHERE status = 'pending'"
        ).fetchall()
    return [dict(r) for r in rows]


def _load_game_scores() -> Dict[str, Dict]:
    """Load all games with final scores from PostgreSQL, keyed by external_game_id."""
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT external_game_id, home_team, away_team, home_score, away_score "
                    "FROM games WHERE home_score IS NOT NULL AND away_score IS NOT NULL"
                )
            ).fetchall()
        return {row[0]: dict(row._mapping) for row in rows}
    except Exception as e:
        logger.error(f"Failed to load game scores from PostgreSQL: {e}")
        return {}


async def _fetch_fresh_scores(days: int = 3) -> Dict[str, Dict]:
    """Fetch recent completed scores from Odds API and upsert into PostgreSQL."""
    from app.services.sports_api import SportsAPI

    api = SportsAPI()
    fresh: Dict[str, Dict] = {}

    for sport_key, odds_key in SPORT_SCORE_KEYS.items():
        scores = await api.get_scores(odds_key, days_from=days)
        for game in scores:
            if not game.get("completed"):
                continue
            home = next(
                (t for t in game.get("scores", []) if t.get("name") == game.get("home_team")),
                None,
            )
            away = next(
                (t for t in game.get("scores", []) if t.get("name") != game.get("home_team")),
                None,
            )
            if not (home and away):
                # Try direct score fields
                home_score = game.get("home_score")
                away_score = game.get("away_score")
            else:
                home_score = int(home.get("score", 0) or 0)
                away_score = int(away.get("score", 0) or 0)

            if home_score is None or away_score is None:
                continue

            ext_id = f"{sport_key.upper()}_{game.get('id', '')}"
            fresh[ext_id] = {
                "external_game_id": ext_id,
                "home_team": game.get("home_team", ""),
                "away_team": game.get("away_team", ""),
                "home_score": home_score,
                "away_score": away_score,
            }
            # Upsert into PostgreSQL
            try:
                engine = create_engine(settings.DATABASE_URL)
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE games SET home_score = :hs, away_score = :as "
                            "WHERE external_game_id = :eid"
                        ),
                        {"hs": home_score, "as": away_score, "eid": ext_id},
                    )
            except Exception as e:
                logger.debug(f"Upsert score failed for {ext_id}: {e}")

    logger.info(f"Fetched {len(fresh)} completed games from Odds API")
    return fresh


def _settle_spread(side: str, line: float, game: Dict) -> Optional[str]:
    """
    Settle a spread bet.
    line: spread value from the bet side's perspective (e.g., -12 means this team is -12 fav)
    Returns: 'won', 'lost', 'push', or None if can't determine
    """
    home_score = game["home_score"]
    away_score = game["away_score"]
    home_team = (game.get("home_team") or "").lower()
    away_team = (game.get("away_team") or "").lower()
    side_lower = side.lower()

    # Fuzzy team matching
    if side_lower in home_team or home_team in side_lower:
        is_home = True
    elif side_lower in away_team or away_team in side_lower:
        is_home = False
    else:
        logger.debug(f"Can't match '{side}' to home='{game['home_team']}' away='{game['away_team']}'")
        return None

    # adjusted_score = side_score + line (cover if adjusted > opponent)
    if is_home:
        adjusted = home_score + line
        opponent = away_score
    else:
        adjusted = away_score + line
        opponent = home_score

    if adjusted > opponent:
        return "won"
    elif adjusted < opponent:
        return "lost"
    else:
        return "push"


def _settle_moneyline(side: str, game: Dict) -> Optional[str]:
    """Settle a moneyline bet."""
    home_score = game["home_score"]
    away_score = game["away_score"]
    home_team = (game.get("home_team") or "").lower()
    away_team = (game.get("away_team") or "").lower()
    side_lower = side.lower()

    if side_lower in home_team or home_team in side_lower:
        won = home_score > away_score
    elif side_lower in away_team or away_team in side_lower:
        won = away_score > home_score
    else:
        return None

    if home_score == away_score:
        return "push"
    return "won" if won else "lost"


def _settle_total(side: str, line: float, game: Dict) -> Optional[str]:
    """Settle an over/under total bet. side should be 'over' or 'under'."""
    total = game["home_score"] + game["away_score"]
    side_lower = side.lower()

    if total == line:
        return "push"
    if "over" in side_lower:
        return "won" if total > line else "lost"
    if "under" in side_lower:
        return "won" if total < line else "lost"
    return None


def _settle_bet(bet: Dict, game: Dict) -> Optional[str]:
    """Determine bet outcome. Returns status string or None if undetermined."""
    market = (bet.get("market") or "spread").lower()
    side = bet.get("side") or ""
    line = float(bet.get("line") or 0.0)

    if market == "spread":
        return _settle_spread(side, line, game)
    elif market in ("moneyline", "ml"):
        return _settle_moneyline(side, game)
    elif market in ("total", "over_under"):
        return _settle_total(side, line, game)
    elif market in ("over", "under"):
        # Some bets store 'over'/'under' as the market
        return _settle_total(market, line, game)
    else:
        # Player props: market is the stat (player_points, etc.)
        # Side is the player name — can't auto-settle without stat lines
        logger.debug(f"Auto-settlement not supported for market '{market}'")
        return None


def _print_summary(results: List[Tuple[str, str, str]]) -> None:
    """Print settlement summary to console."""
    from collections import Counter
    counts = Counter(r[1] for r in results)
    total = len(results)
    settled = sum(v for k, v in counts.items() if k != "skipped")

    print(f"\n{'='*60}")
    print(f"  BET SETTLEMENT SUMMARY")
    print(f"{'='*60}")
    print(f"  Total pending checked : {total}")
    print(f"  Settled               : {settled}")
    print(f"    ✅ Won  : {counts.get('won', 0)}")
    print(f"    ❌ Lost : {counts.get('lost', 0)}")
    print(f"    ➖ Push : {counts.get('push', 0)}")
    print(f"  ⏳ Skipped (no score)  : {counts.get('skipped', 0)}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Settle pending bets against game results")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--days", type=int, default=0,
                        help="Fetch fresh Odds API scores for last N days (0=skip)")
    args = parser.parse_args()

    logger.info("Starting bet settlement...")

    # Optionally fetch fresh scores
    if args.days > 0:
        logger.info(f"Fetching fresh scores for last {args.days} days...")
        fresh = asyncio.run(_fetch_fresh_scores(args.days))
    else:
        fresh = {}

    # Load pending bets
    pending = _load_pending_bets()
    if not pending:
        print("No pending bets to settle.")
        return

    logger.info(f"Found {len(pending)} pending bets")

    # Load game scores from DB (primary source)
    db_scores = _load_game_scores()
    # Merge fresh scores (override DB if fresh is available)
    all_scores = {**db_scores, **fresh}
    logger.info(f"Loaded {len(all_scores)} games with final scores")

    tracker = BetTracker()
    results: List[Tuple[str, str, str]] = []  # (bet_id, status, details)

    for bet in pending:
        bet_id = bet["id"]
        game_id = bet.get("game_id") or ""
        game = all_scores.get(game_id)

        if not game:
            results.append((bet_id, "skipped", f"No score for game_id={game_id}"))
            continue

        status = _settle_bet(bet, game)
        if status is None:
            results.append((bet_id, "skipped", f"Market '{bet.get('market')}' not auto-settleable"))
            continue

        detail = (
            f"{bet['side']} ({bet['market']} {bet.get('line', '')}) → "
            f"{game['home_team']} {game['home_score']} - {game['away_score']} {game['away_team']} "
            f"→ {status.upper()}"
        )
        results.append((bet_id, status, detail))
        print(f"  {detail}")

        if not args.dry_run:
            tracker.update_bet_result(bet_id, status)

    if args.dry_run:
        print("\n[DRY RUN] No changes saved.")

    _print_summary(results)

    # Show current W/L record
    if not args.dry_run:
        metrics = tracker.get_performance_metrics()
        print(f"  CURRENT RECORD: {metrics['wins']}W - {metrics['losses']}L "
              f"({metrics['win_rate']:.1%} WR) | "
              f"ROI: {metrics['roi']:.1%} | "
              f"Units: {metrics['units']:+.2f}")


if __name__ == "__main__":
    main()
