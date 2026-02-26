"""
Backfill PlayerGameLog.scenario with real matchup context features.

Populates the five scenario features that sync_qdrant.py and train_prop_model.py
cannot compute from game log data alone:

    opp_pace          — opponent team's possessions per 48 min (season avg)
    opp_def_rtg       — opponent team's defensive rating (season avg)
    def_vs_position   — not yet populated (requires position-level DvP data)
    implied_team_total — not yet populated (requires historical odds)
    spread             — not yet populated (requires historical odds)

Without this script those three fields default to league averages (100.0 / 112.0
/ 0.0) — which is still consistent between training and inference, but provides
no actual matchup signal. Running this script upgrades those two fields to real
team stats for every game log in the database.

Data source: nba_api LeagueDashTeamStats (current-season stats).
Limitation: uses current-season stats for all historical games in the same season.
            For multi-season archives retrain after each season's stats are final.

Usage:
    cd backend
    python backfill_scenario.py              # fill only NULL / incomplete scenarios
    python backfill_scenario.py --force      # overwrite all scenario records
    python backfill_scenario.py --dry-run    # print counts, skip DB writes
    python backfill_scenario.py --batch 500  # commit in batches of N (default 200)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("logs", exist_ok=True)
logger.add("logs/backfill_scenario.log", rotation="7 days", level="INFO")

from app.config import settings  # noqa: E402
from app.models.player_game_log import PlayerGameLog  # noqa: E402
from app.models.game import Game  # noqa: E402
from app.models.team import Team  # noqa: E402
from app.services.nba_dvp_analyzer import (  # noqa: E402
    NBADvPAnalyzer,
    TEAM_ABBREV_MAP,
    TEAM_NAME_TO_ABBREV,
)


# ── Team stat helpers ──────────────────────────────────────────────────────────

def _load_team_stats(analyzer: NBADvPAnalyzer) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Return (pace_by_abbrev, def_rtg_by_abbrev) dicts keyed by 3-letter
    team abbreviation (e.g. "BOS", "LAL").

    Fetches from nba_api; falls back to built-in estimates if unavailable.
    """
    pace = analyzer.fetch_team_pace()           # abbrev -> float
    advanced = analyzer.fetch_team_advanced_stats()  # abbrev -> {DEF_RATING, ...}
    def_rtg = {abbrev: v["DEF_RATING"] for abbrev, v in advanced.items() if v.get("DEF_RATING")}

    logger.info(f"Loaded pace for {len(pace)} teams, def_rtg for {len(def_rtg)} teams")
    return pace, def_rtg


def _normalize_abbrev(raw: Optional[str]) -> Optional[str]:
    """
    Accept either a 2-3 letter abbreviation or a full team name and return
    the canonical 2-3 letter abbreviation used in TEAM_ABBREV_MAP.

    Returns None if the team cannot be resolved.
    """
    if not raw:
        return None
    raw = raw.strip()

    # Already a known abbreviation?
    if raw in TEAM_ABBREV_MAP:
        return raw

    # Try the reverse map (full name -> abbrev)
    if raw in TEAM_NAME_TO_ABBREV:
        return TEAM_NAME_TO_ABBREV[raw]

    # Case-insensitive abbreviation match
    upper = raw.upper()
    if upper in TEAM_ABBREV_MAP:
        return upper

    # Partial full-name match (e.g. "Golden State" -> "GS")
    for full, abbrev in TEAM_NAME_TO_ABBREV.items():
        if raw.lower() in full.lower() or full.lower() in raw.lower():
            return abbrev

    return None


# ── Main backfill logic ────────────────────────────────────────────────────────

def backfill(*, force: bool, dry_run: bool, batch_size: int) -> None:
    engine = create_engine(str(settings.DATABASE_URL))

    # Fetch team stats once for the whole run
    analyzer = NBADvPAnalyzer()
    pace_map, def_rtg_map = _load_team_stats(analyzer)

    with Session(engine) as db:
        # Build query — optionally skip logs that already have both fields
        q = (
           db.query(PlayerGameLog)
            .join(Game, PlayerGameLog.game_id == Game.id)
            .join(Team, PlayerGameLog.opponent_id == Team.id)
            .filter(Game.sport.in_(["nba", "basketball_nba"]))
        )

        if not force:
            # Only process rows where scenario is NULL or missing opp_pace
            # Using Postgres-native JSON extraction to bypass SQLAlchemy quirks
            q = q.filter(
                PlayerGameLog.scenario.is_(None) |
                text("scenario->>'opp_pace' IS NULL")
            )

        total = q.count()
        logger.info(f"{'Backfilling' if not dry_run else 'Would backfill'} {total} game logs")
        print(f"{'Dry-run: would update' if dry_run else 'Updating'} {total} PlayerGameLog records")

        if dry_run or total == 0:
            return

        updated = 0
        skipped = 0

        logs = q.all()
        for log in logs:
            game: Game = log.game
            opp_team: Team = log.opponent

            # Resolve opponent abbreviation from either the Team record name
            # or by comparing game.home_team / game.away_team to player's team
            opp_raw = opp_team.name if opp_team else None
            # Extract string values from SQLAlchemy columns
            opp_raw = opp_team.name if opp_team and hasattr(opp_team, "name") else None
            if isinstance(opp_raw, str):
                pass
            elif opp_raw is not None:
                opp_raw = str(opp_raw)
            if opp_raw is None and game:
                # Infer opponent from game home/away fields
                player_team: Team = log.team
                player_team_name = None
                if player_team and hasattr(player_team, "name"):
                    player_team_name = player_team.name
                    if not isinstance(player_team_name, str) and player_team_name is not None:
                        player_team_name = str(player_team_name)
                player_abbrev = _normalize_abbrev(player_team_name)
                if player_abbrev:
                    home_team_val = game.home_team
                    away_team_val = game.away_team
                    if not isinstance(home_team_val, str) and home_team_val is not None:
                        home_team_val = str(home_team_val)
                    if not isinstance(away_team_val, str) and away_team_val is not None:
                        away_team_val = str(away_team_val)
                    home_abbrev = _normalize_abbrev(home_team_val)
                    away_abbrev = _normalize_abbrev(away_team_val)
                    if home_abbrev == player_abbrev:
                        opp_raw = away_team_val
                    elif away_abbrev == player_abbrev:
                        opp_raw = home_team_val

            if not isinstance(opp_raw, str) and opp_raw is not None:
                opp_raw = str(opp_raw)
            opp_abbrev = _normalize_abbrev(opp_raw)

            pace = pace_map.get(opp_abbrev) if opp_abbrev else None
            drtg = def_rtg_map.get(opp_abbrev) if opp_abbrev else None

            if pace is None or drtg is None:
                skipped += 1
                if skipped <= 5:
                    logger.warning(
                        f"Cannot resolve team stats for opp='{opp_raw}' "
                        f"(abbrev={opp_abbrev}) — log_id={log.id}"
                    )
                continue

            # Determine is_home
            is_home = 0
            if game:
                player_team = log.team
                player_team_name = None
                if player_team and hasattr(player_team, "name"):
                    player_team_name = player_team.name
                    if not isinstance(player_team_name, str) and player_team_name is not None:
                        player_team_name = str(player_team_name)
                player_abbrev = _normalize_abbrev(player_team_name)
                home_team_val = game.home_team
                if not isinstance(home_team_val, str) and home_team_val is not None:
                    home_team_val = str(home_team_val)
                home_abbrev = _normalize_abbrev(home_team_val)
                if player_abbrev and player_abbrev == home_abbrev:
                    is_home = 1

            # Merge into existing scenario (preserve any manually set fields)
            import json

            scenario = log.scenario
            if scenario is None:
                scenario = {}
            elif not isinstance(scenario, dict):
                try:
                    scenario = json.loads(str(scenario))
                except Exception:
                    scenario = {}
            scenario[b"opp_pace"] = str(round(float(pace), 2)).encode()
            scenario[b"opp_def_rtg"] = str(round(float(drtg), 2)).encode()
            scenario[b"is_home"] = str(is_home).encode()
            scenario[b"_backfilled_at"] = datetime.now(timezone.utc).isoformat().encode()
            setattr(log, "scenario", scenario)

            updated += 1

            if updated % batch_size == 0:
                db.commit()
                logger.info(f"  Committed {updated}/{total}")
                print(f"  {updated}/{total} updated…")

        # Final commit
        if updated % batch_size != 0:
            db.commit()

        logger.info(
            f"Done — updated={updated}, skipped={skipped} "
            f"(skipped means opponent team could not be resolved)"
        )
        print(f"\nDone. Updated {updated} records, skipped {skipped} (unresolvable team).")
        if skipped:
            print("  Check logs/backfill_scenario.log for skipped team names.")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill scenario features into PlayerGameLog")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite all scenario records, not just NULL/incomplete ones",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print count of records to update, skip DB writes",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=200,
        help="Commit to DB every N records (default: 200)",
    )
    args = parser.parse_args()

    backfill(force=args.force, dry_run=args.dry_run, batch_size=args.batch)