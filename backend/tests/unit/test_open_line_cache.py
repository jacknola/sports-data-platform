"""
Unit tests for app/services/open_line_cache.py

All tests redirect the SQLite path to a temp file via monkeypatch so they
don't touch the real data/ directory and remain fully isolated.
"""
import time
import pytest

import app.services.open_line_cache as olc_module
from app.services.open_line_cache import (
    get_or_set_open_line,
    get_open_line,
    purge_all,
)


# ---------------------------------------------------------------------------
# Fixture: isolated temp DB
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB path + dir to a fresh temp location for every test."""
    db_file = str(tmp_path / "open_lines_test.db")
    monkeypatch.setattr(olc_module, "_DB_PATH", db_file)
    monkeypatch.setattr(olc_module, "_DB_DIR", str(tmp_path))
    yield db_file


# ---------------------------------------------------------------------------
# get_or_set_open_line – first call (new entry)
# ---------------------------------------------------------------------------

class TestGetOrSetOpenLineFirstCall:
    def test_is_new_on_first_call(self):
        result = get_or_set_open_line("game_001", "spread", -3.5)
        assert result["is_new"] is True

    def test_line_move_is_zero_on_first_call(self):
        result = get_or_set_open_line("game_001", "spread", -3.5)
        assert result["line_move"] == pytest.approx(0.0)

    def test_open_line_matches_current_on_first_call(self):
        result = get_or_set_open_line("game_001", "spread", -3.5)
        assert result["open_line"] == pytest.approx(-3.5)

    def test_open_odds_stored(self):
        result = get_or_set_open_line("game_001", "spread", -3.5,
                                      current_odds=-110.0)
        assert result["open_odds"] == pytest.approx(-110.0)

    def test_open_odds_away_stored(self):
        result = get_or_set_open_line("game_001", "spread", -3.5,
                                      current_odds=-110.0,
                                      current_odds_away=-110.0)
        assert result["open_odds_away"] == pytest.approx(-110.0)

    def test_different_games_stored_independently(self):
        get_or_set_open_line("game_A", "spread", -4.0)
        get_or_set_open_line("game_B", "spread", 6.5)
        r_a = get_or_set_open_line("game_A", "spread", -5.0)
        r_b = get_or_set_open_line("game_B", "spread", 7.0)
        assert r_a["open_line"] == pytest.approx(-4.0)
        assert r_b["open_line"] == pytest.approx(6.5)

    def test_different_markets_for_same_game_stored_independently(self):
        get_or_set_open_line("game_001", "spread", -3.5)
        get_or_set_open_line("game_001", "total", 152.5)
        r_spread = get_or_set_open_line("game_001", "spread", -4.0)
        r_total = get_or_set_open_line("game_001", "total", 153.0)
        assert r_spread["open_line"] == pytest.approx(-3.5)
        assert r_total["open_line"] == pytest.approx(152.5)


# ---------------------------------------------------------------------------
# get_or_set_open_line – subsequent calls (cache hit)
# ---------------------------------------------------------------------------

class TestGetOrSetOpenLineSubsequentCalls:
    def test_is_not_new_on_second_call(self):
        get_or_set_open_line("game_002", "spread", -3.5)
        result = get_or_set_open_line("game_002", "spread", -4.0)
        assert result["is_new"] is False

    def test_open_line_remains_first_value(self):
        get_or_set_open_line("game_002", "spread", -3.5)
        result = get_or_set_open_line("game_002", "spread", -4.0)
        assert result["open_line"] == pytest.approx(-3.5)

    def test_line_move_reflects_change(self):
        get_or_set_open_line("game_002", "spread", -3.5)
        result = get_or_set_open_line("game_002", "spread", -4.0)
        # current (-4.0) - open (-3.5) = -0.5
        assert result["line_move"] == pytest.approx(-0.5)

    def test_positive_line_move(self):
        get_or_set_open_line("game_003", "spread", -4.0)
        result = get_or_set_open_line("game_003", "spread", -3.5)
        assert result["line_move"] == pytest.approx(0.5)

    def test_no_line_move(self):
        get_or_set_open_line("game_004", "total", 152.5)
        result = get_or_set_open_line("game_004", "total", 152.5)
        assert result["line_move"] == pytest.approx(0.0)

    def test_multiple_subsequent_calls_keep_original(self):
        get_or_set_open_line("game_005", "spread", -3.5)
        get_or_set_open_line("game_005", "spread", -4.0)
        result = get_or_set_open_line("game_005", "spread", -4.5)
        # Open line should still be the very first value
        assert result["open_line"] == pytest.approx(-3.5)
        assert result["line_move"] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# get_open_line (read-only)
# ---------------------------------------------------------------------------

class TestGetOpenLine:
    def test_returns_none_when_not_cached(self):
        result = get_open_line("uncached_game", "spread")
        assert result is None

    def test_returns_dict_when_cached(self):
        get_or_set_open_line("game_006", "spread", -3.5)
        result = get_open_line("game_006", "spread")
        assert result is not None
        assert result["open_line"] == pytest.approx(-3.5)

    def test_does_not_overwrite_existing_entry(self):
        get_or_set_open_line("game_006", "spread", -3.5)
        # Read-only lookup — should not change stored value
        get_open_line("game_006", "spread")
        later = get_or_set_open_line("game_006", "spread", -4.0)
        assert later["open_line"] == pytest.approx(-3.5)


# ---------------------------------------------------------------------------
# purge_all
# ---------------------------------------------------------------------------

class TestPurgeAll:
    def test_purge_removes_all_rows(self):
        get_or_set_open_line("game_007", "spread", -3.5)
        get_or_set_open_line("game_008", "total", 152.5)
        count = purge_all()
        assert count == 2
        assert get_open_line("game_007", "spread") is None
        assert get_open_line("game_008", "total") is None

    def test_purge_empty_db_returns_zero(self):
        count = purge_all()
        assert count == 0


# ---------------------------------------------------------------------------
# Stale-line expiry
# ---------------------------------------------------------------------------

class TestStaleLineExpiry:
    def test_stale_lines_not_returned(self, monkeypatch):
        # Store an entry with a timestamp far in the past (48 h ago)
        get_or_set_open_line("game_009", "spread", -3.5)

        # Manually set first_seen to 48 h ago so it expires
        import sqlite3
        db_path = olc_module._DB_PATH
        stale_ts = time.time() - (48 * 3600)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE open_lines SET first_seen = ? WHERE market_key = ?",
                (stale_ts, "game_009:spread"),
            )
            conn.commit()

        # The next call should NOT find the stale row (purge runs inside the function)
        result = get_or_set_open_line("game_009", "spread", -4.5)
        # After purge it's treated as new
        assert result["is_new"] is True
        assert result["open_line"] == pytest.approx(-4.5)
