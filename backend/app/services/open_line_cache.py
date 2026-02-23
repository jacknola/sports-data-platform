"""
Open Line Cache

Persists the first-seen (opening) line/odds for each market so that
subsequent snapshots can compute *actual* line movement, rather than
comparing current to current.

Without this, open_line == current_line everywhere, which makes RLM,
STEAM, and FREEZE signal detection impossible (line_move = 0 always).

Storage: SQLite file at ``data/open_lines.db``.  Rows expire after 24h
(lines older than that are stale/yesterday's).
"""

import os
import sqlite3
import time
from typing import Dict, Optional, Tuple
from loguru import logger


_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_DB_PATH = os.path.join(_DB_DIR, "open_lines.db")

# Lines older than this many seconds are considered stale
_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours


def _get_connection() -> sqlite3.Connection:
    """Return a SQLite connection, creating the DB + table if needed."""
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS open_lines (
            market_key   TEXT PRIMARY KEY,
            line         REAL NOT NULL,
            odds         REAL,
            odds_away    REAL,
            first_seen   REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _purge_stale(conn: sqlite3.Connection) -> None:
    """Delete rows older than _EXPIRY_SECONDS."""
    cutoff = time.time() - _EXPIRY_SECONDS
    conn.execute("DELETE FROM open_lines WHERE first_seen < ?", (cutoff,))
    conn.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_or_set_open_line(
    game_id: str,
    market: str,
    current_line: float,
    current_odds: Optional[float] = None,
    current_odds_away: Optional[float] = None,
) -> Dict[str, float]:
    """Return the opening line/odds for a market, caching the first seen.

    On the *first* call for a given game_id+market, stores the current
    values as the opening values.  On subsequent calls, returns the
    stored opening values — giving a real open→current delta.

    Args:
        game_id: Unique game identifier (e.g. ``ncaab_duke_unc_20260223``)
        market: Market type (``spread``, ``total``, ``prop:player:stat``)
        current_line: Current line value
        current_odds: Current American odds for home/over side
        current_odds_away: Current American odds for away/under side

    Returns:
        Dict with ``open_line``, ``open_odds``, ``open_odds_away``,
        ``line_move`` (current - open), ``is_new`` (bool, True if first
        time seeing this market today).
    """
    market_key = f"{game_id}:{market}"

    conn = _get_connection()
    try:
        _purge_stale(conn)

        row = conn.execute(
            "SELECT line, odds, odds_away FROM open_lines WHERE market_key = ?",
            (market_key,),
        ).fetchone()

        if row is not None:
            open_line, open_odds, open_odds_away = row
            return {
                "open_line": open_line,
                "open_odds": open_odds,
                "open_odds_away": open_odds_away,
                "line_move": round(current_line - open_line, 2),
                "is_new": False,
            }

        # First time seeing this market — store as opening
        conn.execute(
            """
            INSERT OR IGNORE INTO open_lines (market_key, line, odds, odds_away, first_seen)
            VALUES (?, ?, ?, ?, ?)
            """,
            (market_key, current_line, current_odds, current_odds_away, time.time()),
        )
        conn.commit()
        logger.debug(f"Cached opening line: {market_key} = {current_line}")

        return {
            "open_line": current_line,
            "open_odds": current_odds,
            "open_odds_away": current_odds_away,
            "line_move": 0.0,
            "is_new": True,
        }
    finally:
        conn.close()


def get_open_line(game_id: str, market: str) -> Optional[Dict[str, float]]:
    """Read-only lookup of an existing cached open line.

    Returns None if not cached yet.
    """
    market_key = f"{game_id}:{market}"
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT line, odds, odds_away FROM open_lines WHERE market_key = ?",
            (market_key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "open_line": row[0],
            "open_odds": row[1],
            "open_odds_away": row[2],
        }
    finally:
        conn.close()


def purge_all() -> int:
    """Delete all cached open lines.  Returns count deleted."""
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM open_lines")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
