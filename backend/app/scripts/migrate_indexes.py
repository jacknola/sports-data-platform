"""
migrate_indexes.py — idempotent index migration for existing databases.

Run once after deploying the model changes:
    cd backend && python -m app.scripts.migrate_indexes

All statements use CREATE INDEX IF NOT EXISTS so they are safe to re-run.
The expires_at column is added to api_cache via ALTER TABLE with error handling.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger
from sqlalchemy import text
from app.database import engine


DDL = [
    # ── api_cache: add expires_at column (no-op if exists) ───────────────────
    """
    DO $$ BEGIN
      ALTER TABLE api_cache ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;
    EXCEPTION WHEN duplicate_column THEN NULL;
    END $$;
    """,
    # Back-fill expires_at from timestamp + 1 hour for existing rows
    """
    UPDATE api_cache
       SET expires_at = timestamp + INTERVAL '1 hour'
     WHERE expires_at IS NULL;
    """,

    # ── indexes ───────────────────────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS ix_apicache_key_expires ON api_cache (key, expires_at);",
    "CREATE INDEX IF NOT EXISTS ix_games_sport_date     ON games (sport, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_bets_sport_market    ON bets (sport, market);",
    "CREATE INDEX IF NOT EXISTS ix_bets_game_market     ON bets (game_id, market);",
    "CREATE INDEX IF NOT EXISTS ix_pgl_player_date      ON player_game_logs (player_id, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_hgl_season_date      ON historical_game_lines (season, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_hgl_teams_season     ON historical_game_lines (home_team, away_team, season);",
    "CREATE INDEX IF NOT EXISTS ix_hpp_player_prop_date ON historical_player_props (player_name, prop_type, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_hpp_season_prop_book ON historical_player_props (season, prop_type, sportsbook);",
]

# SQLite versions (no DO $$ syntax, no IF NOT EXISTS on older versions)
DDL_SQLITE = [
    "ALTER TABLE api_cache ADD COLUMN expires_at TEXT;",  # SQLite uses TEXT for datetime
    "UPDATE api_cache SET expires_at = datetime(timestamp, '+1 hour') WHERE expires_at IS NULL;",
    "CREATE INDEX IF NOT EXISTS ix_apicache_key_expires ON api_cache (key, expires_at);",
    "CREATE INDEX IF NOT EXISTS ix_games_sport_date     ON games (sport, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_bets_sport_market    ON bets (sport, market);",
    "CREATE INDEX IF NOT EXISTS ix_bets_game_market     ON bets (game_id, market);",
    "CREATE INDEX IF NOT EXISTS ix_pgl_player_date      ON player_game_logs (player_id, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_hgl_season_date      ON historical_game_lines (season, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_hgl_teams_season     ON historical_game_lines (home_team, away_team, season);",
    "CREATE INDEX IF NOT EXISTS ix_hpp_player_prop_date ON historical_player_props (player_name, prop_type, game_date);",
    "CREATE INDEX IF NOT EXISTS ix_hpp_season_prop_book ON historical_player_props (season, prop_type, sportsbook);",
]


def run():
    is_sqlite = str(engine.url).startswith("sqlite")
    statements = DDL_SQLITE if is_sqlite else DDL

    with engine.begin() as conn:
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                conn.execute(text(stmt))
                short = stmt.split("\n")[0][:72]
                logger.info(f"OK  {short}")
            except Exception as e:
                msg = str(e).lower()
                # "duplicate column", "already exists" are expected — skip silently
                if any(x in msg for x in ("duplicate", "already exist", "duplicate_column")):
                    short = stmt.split("\n")[0][:72]
                    logger.debug(f"SKIP (already applied): {short}")
                else:
                    logger.error(f"FAILED: {stmt[:80]}\n  {e}")

    logger.info("Index migration complete.")


if __name__ == "__main__":
    run()
