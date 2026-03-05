"""
Supabase Integration Service

Provides a unified interface to the Supabase backend for:
- Persisting bet analysis results
- Storing sharp money signals
- Tracking CLV records
- Storing game slate data
- Reading/writing portfolio performance metrics

Supabase project: https://jlqhvweftcknjcnvrzve.supabase.co
"""

import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("supabase package not installed. Run: pip install supabase==2.4.0")


# ---------------------------------------------------------------------------
# Table schema constants (match your Supabase SQL schema)
# ---------------------------------------------------------------------------

TABLE_BETS = "bets"
TABLE_GAMES = "games"
TABLE_SHARP_SIGNALS = "sharp_signals"
TABLE_CLV_RECORDS = "clv_records"
TABLE_PORTFOLIO_SNAPSHOTS = "portfolio_snapshots"
TABLE_SLATE_ANALYSIS = "slate_analysis"


class SupabaseService:
    """
    Handles all read/write operations to the Supabase backend.

    Usage:
        service = SupabaseService()
        service.save_slate_analysis(analysis_results)
        records = service.get_recent_bets(limit=50)
    """

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
    ):
        self.url = url or os.getenv("SUPABASE_URL", "")
        self.key = key or os.getenv("SUPABASE_ANON_KEY", "")
        self._client: Optional[Any] = None

        if not self.url or not self.key:
            logger.warning(
                "Supabase URL or key not configured. "
                "Set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file."
            )
        elif not SUPABASE_AVAILABLE:
            logger.warning("Install supabase package: pip install supabase==2.4.0")
        else:
            try:
                self._client = create_client(self.url, self.key)
                logger.info(f"Supabase client connected: {self.url}")
            except Exception as e:
                logger.error(f"Failed to create Supabase client: {e}")

    @property
    def client(self) -> Optional[Any]:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    # ------------------------------------------------------------------
    # Bet Storage
    # ------------------------------------------------------------------

    def save_bet(self, bet: Dict) -> Optional[Dict]:
        """
        Save a single bet recommendation to Supabase.

        Expected fields:
            game_id, side, market, true_prob, decimal_odds, edge,
            kelly_fraction, bet_size, sport, conference, sharp_signals,
            signal_confidence, notes
        """
        if not self.is_connected:
            return None

        record = {
            **bet,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending",  # pending | won | lost | void
        }

        try:
            result = self._client.table(TABLE_BETS).insert(record).execute()
            logger.info(f"Bet saved to Supabase: {bet.get('game_id')} {bet.get('side')}")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save bet to Supabase: {e}")
            return None

    def save_bets_batch(self, bets: List[Dict]) -> int:
        """Save multiple bets in a single Supabase insert. Returns count saved."""
        if not self.is_connected or not bets:
            return 0

        records = [
            {**b, "created_at": datetime.utcnow().isoformat(), "status": "pending"}
            for b in bets
        ]

        try:
            result = self._client.table(TABLE_BETS).insert(records).execute()
            count = len(result.data) if result.data else 0
            logger.info(f"Batch saved {count} bets to Supabase")
            return count
        except Exception as e:
            logger.error(f"Failed to batch save bets: {e}")
            return 0

    def get_recent_bets(self, limit: int = 50, sport: Optional[str] = None) -> List[Dict]:
        """Retrieve recent bet records, optionally filtered by sport."""
        if not self.is_connected:
            return []

        try:
            query = (
                self._client.table(TABLE_BETS)
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
            )
            if sport:
                query = query.eq("sport", sport)

            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to retrieve bets: {e}")
            return []

    def update_bet_result(self, bet_id: str, result: str, actual_clv: float) -> bool:
        """
        Update a bet record with the outcome and CLV after game completion.

        Args:
            bet_id: Supabase row ID
            result: 'won', 'lost', or 'void'
            actual_clv: Closing Line Value as percentage (e.g., 1.5 for +1.5%)
        """
        if not self.is_connected:
            return False

        try:
            self._client.table(TABLE_BETS).update({
                "status": result,
                "actual_clv": actual_clv,
                "settled_at": datetime.utcnow().isoformat()
            }).eq("id", bet_id).execute()
            logger.info(f"Bet {bet_id} updated: {result}, CLV={actual_clv:+.2f}%")
            return True
        except Exception as e:
            logger.error(f"Failed to update bet result: {e}")
            return False

    # ------------------------------------------------------------------
    # Sharp Signal Storage
    # ------------------------------------------------------------------

    def save_sharp_signal(self, signal: Dict) -> Optional[Dict]:
        """
        Persist a detected sharp money signal.

        Expected fields:
            game_id, market, signal_type, sharp_side, confidence,
            ticket_pct, money_pct, open_line, current_line, details
        """
        if not self.is_connected:
            return None

        record = {
            **signal,
            "detected_at": datetime.utcnow().isoformat()
        }

        try:
            result = self._client.table(TABLE_SHARP_SIGNALS).insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save sharp signal: {e}")
            return None

    # ------------------------------------------------------------------
    # CLV Tracking
    # ------------------------------------------------------------------

    def save_clv_record(self, clv: Dict) -> Optional[Dict]:
        """
        Store a CLV measurement for performance tracking.

        Expected fields:
            game_id, market, side, bet_odds, closing_odds, clv_pct,
            implied_at_bet, implied_closing, bet_timestamp
        """
        if not self.is_connected:
            return None

        record = {
            **clv,
            "recorded_at": datetime.utcnow().isoformat()
        }

        try:
            result = self._client.table(TABLE_CLV_RECORDS).insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save CLV record: {e}")
            return None

    def get_clv_summary(self, days: int = 30) -> Dict:
        """Return CLV performance summary for the past N days."""
        if not self.is_connected:
            return {}

        from datetime import timedelta
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        try:
            result = (
                self._client.table(TABLE_CLV_RECORDS)
                .select("clv_pct")
                .gte("recorded_at", since)
                .execute()
            )
            clvs = [r["clv_pct"] for r in (result.data or []) if r.get("clv_pct") is not None]

            if not clvs:
                return {"count": 0, "avg_clv": 0.0, "pct_positive": 0.0}

            import numpy as np
            return {
                "count": len(clvs),
                "avg_clv": round(float(np.mean(clvs)), 3),
                "median_clv": round(float(np.median(clvs)), 3),
                "pct_positive": round(sum(1 for c in clvs if c > 0) / len(clvs), 3),
                "cumulative_clv": round(sum(clvs), 3),
                "days": days
            }
        except Exception as e:
            logger.error(f"Failed to get CLV summary: {e}")
            return {}

    # ------------------------------------------------------------------
    # Slate Analysis Storage
    # ------------------------------------------------------------------

    def save_slate_analysis(self, analysis: Dict) -> Optional[Dict]:
        """
        Store the full output of a slate analysis run.

        Args:
            analysis: Dict from run_ncaab_analysis or similar runner,
                      containing bets, portfolio_summary, game_analyses
        """
        if not self.is_connected:
            return None

        record = {
            "sport": analysis.get("sport", "ncaab"),
            "date": analysis.get("date", datetime.utcnow().date().isoformat()),
            "games_analyzed": analysis.get("games_analyzed", 0),
            "bets_placed": analysis.get("bets_placed", 0),
            "total_exposure_pct": analysis.get("total_exposure_pct", 0.0),
            "expected_growth_rate": analysis.get("expected_growth_rate", 0.0),
            "kelly_scale": analysis.get("kelly_scale", 0.5),
            "payload": analysis,
            "created_at": datetime.utcnow().isoformat()
        }

        try:
            result = self._client.table(TABLE_SLATE_ANALYSIS).insert(record).execute()
            logger.info(f"Slate analysis saved to Supabase: {record['date']} {record['sport']}")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save slate analysis: {e}")
            return None

    def get_slate_history(
        self, sport: str = "ncaab", limit: int = 30
    ) -> List[Dict]:
        """Retrieve historical slate analysis records."""
        if not self.is_connected:
            return []

        try:
            result = (
                self._client.table(TABLE_SLATE_ANALYSIS)
                .select("*")
                .eq("sport", sport)
                .order("date", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to retrieve slate history: {e}")
            return []

    # ------------------------------------------------------------------
    # Portfolio Performance
    # ------------------------------------------------------------------

    def save_portfolio_snapshot(
        self, bankroll: float, total_bets: int, win_rate: float,
        roi: float, avg_clv: float, sport: str = "ncaab"
    ) -> Optional[Dict]:
        """Snapshot current portfolio performance metrics."""
        if not self.is_connected:
            return None

        record = {
            "sport": sport,
            "bankroll": bankroll,
            "total_bets": total_bets,
            "win_rate": win_rate,
            "roi": roi,
            "avg_clv": avg_clv,
            "snapshot_at": datetime.utcnow().isoformat()
        }

        try:
            result = self._client.table(TABLE_PORTFOLIO_SNAPSHOTS).insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save portfolio snapshot: {e}")
            return None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def health_check(self) -> Dict:
        """Verify Supabase connectivity."""
        if not self.is_connected:
            return {
                "status": "disconnected",
                "url": self.url,
                "error": "Client not initialized"
            }

        try:
            # Simple query to verify connection
            self._client.table(TABLE_BETS).select("id").limit(1).execute()
            return {
                "status": "connected",
                "url": self.url
            }
        except Exception as e:
            return {
                "status": "error",
                "url": self.url,
                "error": str(e)
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service_instance: Optional[SupabaseService] = None


def get_supabase_service() -> SupabaseService:
    """Return the module-level SupabaseService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SupabaseService()
    return _service_instance
