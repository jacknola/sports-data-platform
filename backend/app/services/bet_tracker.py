"""
Bet Tracker Service

Handles reading and writing bet records. Uses Supabase if available,
otherwise falls back to a local SQLite database for persistence.

Schema:
- bet_id (str, UUID)
- date (str, YYYY-MM-DD)
- game_id (str)
- sport (str)
- side (str)
- market (str)
- odds (int)
- edge (float)
- bet_size (float)
- status (str: pending, won, lost, push, void)
- clv (float)
"""

import os
import uuid
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from loguru import logger

from app.config import settings
from app.services.supabase_service import SupabaseService, TABLE_BETS
from app.database import SessionLocal
from app.models.bet import Bet
from sqlalchemy import select

LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bets.db")


class BetTracker:
    def __init__(self):
        self.supabase = SupabaseService()
        self.use_supabase = self.supabase.is_connected

        if not self.use_supabase:
            logger.info(
                f"Supabase not connected. Falling back to local SQLite: {LOCAL_DB_PATH}"
            )
            self._init_sqlite()

    def _init_sqlite(self):
        """Initialize local SQLite database if Supabase is unavailable."""
        os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id TEXT PRIMARY KEY,
                    created_at TEXT,
                    date TEXT,
                    game_id TEXT,
                    sport TEXT,
                    side TEXT,
                    market TEXT,
                    odds INTEGER,
                    line REAL,
                    edge REAL,
                    bet_size REAL,
                    status TEXT,
                    book TEXT,
                    actual_clv REAL,
                    settled_at TEXT
                )
            """)
            # Add book column to existing DBs that pre-date this field
            try:
                conn.execute("ALTER TABLE bets ADD COLUMN book TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists
            conn.commit()

    def save_bet(self, bet_data: Dict[str, Any]) -> str:
        """
        Save a pending bet.
        Returns the generated bet ID.
        """
        bet_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        # Standardize record
        record = {
            "id": bet_id,
            "created_at": now_iso,
            "date": bet_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "game_id": bet_data.get("game_id", ""),
            "sport": bet_data.get("sport", "ncaab"),
            "side": bet_data.get("side", ""),
            "market": bet_data.get("market", "spread"),
            "odds": bet_data.get("odds", -110),
            "line": bet_data.get("line", 0.0),
            "edge": bet_data.get("edge", 0.0),
            "bet_size": bet_data.get("bet_size", 0.0),
            "status": "pending",
            "book": bet_data.get("book", settings.PRIMARY_BOOK),
            "actual_clv": None,
            "settled_at": None,
        }

        # 1. Save to PostgreSQL (for model comparison)
        self._save_postgres(bet_data, record)

        # 2. Save to Supabase or SQLite
        if self.use_supabase:
            try:
                self.supabase.client.table(TABLE_BETS).insert(record).execute()
                logger.info(f"Saved bet {bet_id} to Supabase")
            except Exception as e:
                logger.error(
                    f"Failed saving bet to Supabase: {e}. Falling back to SQLite."
                )
                self._save_sqlite(record)
        else:
            self._save_sqlite(record)

        return bet_id

    def _save_postgres(self, original_data: Dict[str, Any], record: Dict[str, Any]):
        """Save to PostgreSQL bets table for Analysis services."""
        try:
            db = SessionLocal()
            # Try to map internal game_id to postgres game.id
            # In run_ncaab_analysis it's like 'NCAAB_12345'
            game_ext_id = record["game_id"]
            
            from app.models.game import Game
            stmt = select(Game).where(Game.external_game_id == game_ext_id)
            game = db.execute(stmt).scalars().first()
            
            postgres_game_id = game.id if game else None
            
            # Convert american to implied
            odds = record["odds"]
            if odds > 0:
                implied = 100 / (odds + 100)
            else:
                implied = abs(odds) / (abs(odds) + 100)

            # We create a Bet model instance
            new_bet = Bet(
                selection_id=record["id"],
                sport=record["sport"],
                game_id=postgres_game_id,
                team=record["side"],
                market=record["market"],
                current_odds=float(odds),
                implied_prob=float(implied),
                devig_prob=float(original_data.get("true_prob") or implied),
                posterior_prob=float(original_data.get("true_prob")) if original_data.get("true_prob") else None,
                edge=float(record["edge"]),
                features=original_data.get("features", {})
            )
            db.add(new_bet)
            db.commit()
            db.close()
            logger.info(f"Saved bet {record['id']} to PostgreSQL")
        except Exception as e:
            logger.error(f"PostgreSQL save failed: {e}")

    def _save_sqlite(self, record: Dict[str, Any]):
        self._init_sqlite()
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO bets
                (id, created_at, date, game_id, sport, side, market, odds, line, edge, bet_size, status, book)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["created_at"],
                    record["date"],
                    record["game_id"],
                    record["sport"],
                    record["side"],
                    record["market"],
                    record["odds"],
                    record["line"],
                    record["edge"],
                    record["bet_size"],
                    record["status"],
                    record.get("book", settings.PRIMARY_BOOK),
                ),
            )
            conn.commit()
            logger.info(f"Saved bet {record['id']} to SQLite")

    def get_pending_bets(self, sport: str = "ncaab") -> List[Dict[str, Any]]:
        """Get all unresolved bets."""
        if self.use_supabase:
            try:
                res = (
                    self.supabase.client.table(TABLE_BETS)
                    .select("*")
                    .eq("status", "pending")
                    .eq("sport", sport)
                    .execute()
                )
                return res.data or []
            except Exception as e:
                logger.error(f"Supabase fetch pending failed: {e}")
                return self._get_pending_sqlite(sport)
        else:
            return self._get_pending_sqlite(sport)

    def _get_pending_sqlite(self, sport: str) -> List[Dict]:
        self._init_sqlite()
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bets WHERE status = 'pending' AND sport = ?", (sport,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_bet_result(self, bet_id: str, status: str, clv: float = None):
        """Update a bet as won, lost, push, or void."""
        now = datetime.utcnow().isoformat()
        if self.use_supabase:
            try:
                update_data = {"status": status, "settled_at": now}
                if clv is not None:
                    update_data["actual_clv"] = clv
                self.supabase.client.table(TABLE_BETS).update(update_data).eq(
                    "id", bet_id
                ).execute()
                logger.info(f"Updated bet {bet_id} in Supabase: {status}")
            except Exception as e:
                logger.error(f"Supabase update failed: {e}")
                self._update_sqlite(bet_id, status, clv, now)
        else:
            self._update_sqlite(bet_id, status, clv, now)

    def _update_sqlite(self, bet_id: str, status: str, clv: float, now: str):
        self._init_sqlite()
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            if clv is not None:
                conn.execute(
                    "UPDATE bets SET status = ?, actual_clv = ?, settled_at = ? WHERE id = ?",
                    (status, clv, now, bet_id),
                )
            else:
                conn.execute(
                    "UPDATE bets SET status = ?, settled_at = ? WHERE id = ?",
                    (status, now, bet_id),
                )
            conn.commit()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate overall Win/Loss and Units."""
        if self.use_supabase:
            try:
                # We fetch all resolved bets to calculate stats
                res = (
                    self.supabase.client.table(TABLE_BETS)
                    .select("*")
                    .neq("status", "pending")
                    .execute()
                )
                resolved = res.data or []
            except Exception as e:
                logger.error(f"Supabase fetch metrics failed: {e}")
                resolved = self._get_resolved_sqlite()
        else:
            resolved = self._get_resolved_sqlite()

        return self._calculate_metrics(resolved)

    def _get_resolved_sqlite(self) -> List[Dict]:
        self._init_sqlite()
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bets WHERE status != 'pending'")
            return [dict(row) for row in cursor.fetchall()]

    def _calculate_metrics(self, bets: List[Dict]) -> Dict[str, Any]:
        wins = 0
        losses = 0
        pushes = 0
        units_won = 0.0
        total_staked = 0.0

        for bet in bets:
            status = bet.get("status")
            size = float(bet.get("bet_size") or 0.0)
            odds = int(bet.get("odds") or -110)

            if size <= 0:
                continue

            total_staked += size

            # Calculate payout based on American odds
            if odds < 0:
                profit = size * (100.0 / abs(odds))
            else:
                profit = size * (odds / 100.0)

            if status == "won":
                wins += 1
                units_won += profit
            elif status == "lost":
                losses += 1
                units_won -= size
            elif status == "push" or status == "void":
                pushes += 1

        total_decisions = wins + losses
        win_rate = (wins / total_decisions) if total_decisions > 0 else 0.0
        roi = (units_won / total_staked) if total_staked > 0 else 0.0

        # CLV average from settled bets that have actual_clv recorded
        clv_values = [float(b["actual_clv"]) for b in bets if b.get("actual_clv") is not None]
        avg_clv = round(sum(clv_values) / len(clv_values), 3) if clv_values else None

        return {
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": win_rate,
            "units": units_won,
            "roi": roi,
            "total_bets": len(bets),
            "avg_clv": avg_clv,
            "clv_sample_size": len(clv_values),
        }
