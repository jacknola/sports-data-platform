"""
Unit tests for app/services/bet_tracker.py

Focus:
- _calculate_metrics — pure function, no DB needed
- SQLite layer (save, retrieve, update) via a temp DB path
"""
import os
import sqlite3
import uuid
import pytest
from unittest.mock import patch, MagicMock

import app.services.bet_tracker as bet_tracker_module
from app.services.bet_tracker import BetTracker


# ---------------------------------------------------------------------------
# Fixture: redirect SQLite DB to a temp file per test
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Patch LOCAL_DB_PATH to an isolated temp file so tests don't pollute each other."""
    db_file = str(tmp_path / "test_bets.db")
    monkeypatch.setattr(bet_tracker_module, "LOCAL_DB_PATH", db_file)
    return db_file


@pytest.fixture
def tracker(tmp_db):
    """BetTracker wired to temp SQLite (no Supabase)."""
    with patch("app.services.bet_tracker.SupabaseService") as mock_supabase_cls:
        mock_supabase = MagicMock()
        mock_supabase.is_connected = False
        mock_supabase_cls.return_value = mock_supabase
        with patch("app.services.bet_tracker.SessionLocal") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            t = BetTracker()
    return t


# ---------------------------------------------------------------------------
# _calculate_metrics  (pure function — no DB)
# ---------------------------------------------------------------------------

class TestCalculateMetrics:
    def setup_method(self):
        """We only need the method, not the full tracker."""
        with patch("app.services.bet_tracker.SupabaseService") as msc:
            msc.return_value.is_connected = False
            with patch("app.services.bet_tracker.SessionLocal"):
                with patch.object(BetTracker, "_init_sqlite"):
                    self.tracker = BetTracker.__new__(BetTracker)
                    self.tracker.use_supabase = False

    def _calc(self, bets):
        return self.tracker._calculate_metrics(bets)

    def test_empty_bets_all_zeros(self):
        result = self._calc([])
        assert result["wins"] == 0
        assert result["losses"] == 0
        assert result["pushes"] == 0
        assert result["win_rate"] == 0.0
        assert result["roi"] == 0.0
        assert result["units"] == 0.0

    def test_single_win_at_minus_110(self):
        bets = [{"status": "won", "bet_size": 110.0, "odds": -110}]
        result = self._calc(bets)
        assert result["wins"] == 1
        assert result["losses"] == 0
        # profit = 110 * (100/110) = 100.0
        assert result["units"] == pytest.approx(100.0, abs=0.01)
        assert result["win_rate"] == pytest.approx(1.0)

    def test_single_loss(self):
        bets = [{"status": "lost", "bet_size": 100.0, "odds": -110}]
        result = self._calc(bets)
        assert result["wins"] == 0
        assert result["losses"] == 1
        # stake lost
        assert result["units"] == pytest.approx(-100.0)

    def test_push_not_counted_as_win_or_loss(self):
        bets = [{"status": "push", "bet_size": 100.0, "odds": -110}]
        result = self._calc(bets)
        assert result["pushes"] == 1
        assert result["wins"] == 0
        assert result["losses"] == 0

    def test_void_counted_as_push(self):
        bets = [{"status": "void", "bet_size": 100.0, "odds": -110}]
        result = self._calc(bets)
        assert result["pushes"] == 1

    def test_win_with_positive_odds(self):
        # +150 win on $100 -> profit = $150
        bets = [{"status": "won", "bet_size": 100.0, "odds": 150}]
        result = self._calc(bets)
        assert result["units"] == pytest.approx(150.0)

    def test_win_rate_calculation(self):
        bets = [
            {"status": "won", "bet_size": 100.0, "odds": -110},
            {"status": "won", "bet_size": 100.0, "odds": -110},
            {"status": "lost", "bet_size": 100.0, "odds": -110},
            {"status": "lost", "bet_size": 100.0, "odds": -110},
        ]
        result = self._calc(bets)
        assert result["win_rate"] == pytest.approx(0.50)

    def test_roi_positive_when_profitable(self):
        bets = [
            {"status": "won", "bet_size": 100.0, "odds": -110},
            {"status": "won", "bet_size": 100.0, "odds": -110},
        ]
        result = self._calc(bets)
        assert result["roi"] > 0

    def test_roi_negative_when_losing(self):
        bets = [
            {"status": "lost", "bet_size": 100.0, "odds": -110},
            {"status": "lost", "bet_size": 100.0, "odds": -110},
        ]
        result = self._calc(bets)
        assert result["roi"] < 0

    def test_bets_with_zero_size_ignored(self):
        bets = [
            {"status": "won", "bet_size": 0.0, "odds": -110},
            {"status": "won", "bet_size": 100.0, "odds": -110},
        ]
        result = self._calc(bets)
        # Only the $100 bet should count toward staked / wins
        assert result["wins"] == 1

    def test_total_bets_includes_all_statuses(self):
        bets = [
            {"status": "won", "bet_size": 100.0, "odds": -110},
            {"status": "lost", "bet_size": 100.0, "odds": -110},
            {"status": "push", "bet_size": 100.0, "odds": -110},
        ]
        result = self._calc(bets)
        assert result["total_bets"] == 3


# ---------------------------------------------------------------------------
# SQLite layer
# ---------------------------------------------------------------------------

class TestBetTrackerSQLite:
    def _conn(self, db_path):
        return sqlite3.connect(db_path)

    def test_save_bet_creates_record(self, tracker, tmp_db):
        bet_data = {
            "game_id": "NCAAB_001",
            "sport": "ncaab",
            "side": "Duke -3.5",
            "market": "spread",
            "odds": -110,
            "edge": 0.03,
            "bet_size": 55.0,
        }
        with patch.object(tracker, "_save_postgres"):
            bet_id = tracker.save_bet(bet_data)

        assert bet_id is not None
        # Verify in SQLite
        with self._conn(tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM bets WHERE id = ?", (bet_id,)
            ).fetchone()
        assert row is not None

    def test_saved_bet_has_pending_status(self, tracker, tmp_db):
        with patch.object(tracker, "_save_postgres"):
            bet_id = tracker.save_bet({"sport": "ncaab", "side": "A", "odds": -110})

        with self._conn(tmp_db) as conn:
            row = conn.execute(
                "SELECT status FROM bets WHERE id = ?", (bet_id,)
            ).fetchone()
        assert row[0] == "pending"

    def test_get_pending_bets_returns_only_pending(self, tracker, tmp_db):
        with patch.object(tracker, "_save_postgres"):
            bet_id = tracker.save_bet({"sport": "ncaab", "side": "B", "odds": -110})

        pending = tracker.get_pending_bets(sport="ncaab")
        ids = [b["id"] for b in pending]
        assert bet_id in ids

    def test_update_bet_result_changes_status(self, tracker, tmp_db):
        with patch.object(tracker, "_save_postgres"):
            bet_id = tracker.save_bet({"sport": "ncaab", "side": "C", "odds": -110})

        tracker.update_bet_result(bet_id, "won", clv=0.02)

        with self._conn(tmp_db) as conn:
            row = conn.execute(
                "SELECT status, actual_clv FROM bets WHERE id = ?", (bet_id,)
            ).fetchone()
        assert row[0] == "won"
        assert row[1] == pytest.approx(0.02)

    def test_get_pending_excludes_settled_bets(self, tracker, tmp_db):
        with patch.object(tracker, "_save_postgres"):
            bet_id = tracker.save_bet({"sport": "ncaab", "side": "D", "odds": -110})
        tracker.update_bet_result(bet_id, "lost")

        pending = tracker.get_pending_bets(sport="ncaab")
        ids = [b["id"] for b in pending]
        assert bet_id not in ids

    def test_save_bet_returns_uuid_string(self, tracker):
        with patch.object(tracker, "_save_postgres"):
            bet_id = tracker.save_bet({"sport": "ncaab", "side": "E", "odds": -110})
        # Should parse as UUID
        parsed = uuid.UUID(bet_id)
        assert str(parsed) == bet_id
