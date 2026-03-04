"""
Unit tests for SportsAPIService SGO fallback and exhaustion-flag logic.

These tests are fully isolated — no network, no DB, no real API keys.
"""
import time
import types
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Module-level stubs so we can import sports_api without real dependencies
# ---------------------------------------------------------------------------

_STUBBED_MODULES = []  # track modules we inserted for cleanup


def _stub_modules():
    """Inject lightweight stubs for heavy dependencies."""
    stubs = {}

    # pydantic_settings
    ps = types.ModuleType("pydantic_settings")
    ps.BaseSettings = object
    stubs["pydantic_settings"] = ps

    # app.config
    cfg = types.ModuleType("app.config")
    settings = MagicMock()
    settings.ODDS_API_KEY = None
    settings.ODDS_API_KEY_FALLBACK = None
    settings.ODDSAPI_API_KEY = None
    settings.THE_ODDS_API_KEY = None
    settings.SPORTSRADAR_API_KEY = None
    settings.DATABASE_URL = "sqlite+aiosqlite:///./test.db"
    cfg.settings = settings
    stubs["app.config"] = cfg

    # app.database — not used in the unit being tested, but imported transitively
    db = types.ModuleType("app.database")
    db.SessionLocal = MagicMock()
    db.init_db = AsyncMock()
    db.get_db = MagicMock()
    stubs["app.database"] = db

    for name, mod in stubs.items():
        if name not in sys.modules:
            _STUBBED_MODULES.append(name)
            sys.modules[name] = mod

    return stubs


_stub_modules()


def teardown_module(module):
    """Remove stubs we inserted so they don't leak to other test modules."""
    for name in _STUBBED_MODULES:
        sys.modules.pop(name, None)


# Now import after stubs are in place
import app.services.sports_api as sports_api_module
from app.services.sports_api import SportsAPIService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_GAMES = [
    {"id": "g1", "home_team": "LAL", "away_team": "GSW", "commence_time": "2099-01-01T20:00:00Z"},
]


def _reset_module_state():
    """Reset the module-level exhaustion flag between tests."""
    sports_api_module._odds_api_exhausted = False
    sports_api_module._odds_api_exhausted_at = 0.0
    # Clear in-memory cache for the test sport key
    sports_api_module._cache._store.clear()


# ---------------------------------------------------------------------------
# _try_sportsgameodds_fallback
# ---------------------------------------------------------------------------

class TestTrySGOFallback:
    @pytest.mark.asyncio
    async def test_returns_empty_when_not_configured(self):
        """If SportsGameOddsService is not configured (no key), fallback returns []."""
        svc = SportsAPIService()

        mock_sgo = MagicMock()
        mock_sgo.is_configured = False

        with patch("app.services.sports_game_odds.SportsGameOddsService", return_value=mock_sgo):
            result = await svc._try_sportsgameodds_fallback("basketball_nba")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_data_when_configured(self):
        """When SGO is configured and returns data, fallback returns that data."""
        svc = SportsAPIService()

        mock_sgo = MagicMock()
        mock_sgo.is_configured = True
        mock_sgo.get_odds_by_sport_key = AsyncMock(return_value=FAKE_GAMES)

        with patch("app.services.sports_game_odds.SportsGameOddsService", return_value=mock_sgo):
            result = await svc._try_sportsgameodds_fallback("basketball_nba")

        assert result == FAKE_GAMES

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        """Network / API errors inside SGO fallback should return [], not raise."""
        svc = SportsAPIService()

        mock_sgo = MagicMock()
        mock_sgo.is_configured = True
        mock_sgo.get_odds_by_sport_key = AsyncMock(side_effect=RuntimeError("network error"))

        with patch("app.services.sports_game_odds.SportsGameOddsService", return_value=mock_sgo):
            result = await svc._try_sportsgameodds_fallback("basketball_nba")

        assert result == []


# ---------------------------------------------------------------------------
# Exhaustion flag logic in get_odds
# ---------------------------------------------------------------------------

class TestExhaustionFlag:
    def setup_method(self):
        _reset_module_state()

    @pytest.mark.asyncio
    async def test_get_odds_uses_sgo_when_key_missing(self):
        """If odds_api_key is None, get_odds() should bypass Odds API and try SGO."""
        svc = SportsAPIService()
        svc.odds_api_key = None  # No primary key

        mock_sgo = MagicMock()
        mock_sgo.is_configured = True
        mock_sgo.get_odds_by_sport_key = AsyncMock(return_value=FAKE_GAMES)

        with patch("app.services.sports_game_odds.SportsGameOddsService", return_value=mock_sgo), \
             patch.object(svc, "_try_odds_api_io_fallback", AsyncMock(return_value=[])):
            result = await svc.get_odds("basketball_nba")

        assert result == FAKE_GAMES

    @pytest.mark.asyncio
    async def test_get_odds_uses_sgo_when_exhausted(self):
        """When _odds_api_exhausted=True, get_odds() should skip Odds API and try SGO."""
        sports_api_module._odds_api_exhausted = True
        sports_api_module._odds_api_exhausted_at = time.time()

        svc = SportsAPIService()
        svc.odds_api_key = "fake_key"  # Would normally be tried but should be skipped

        mock_sgo = MagicMock()
        mock_sgo.is_configured = True
        mock_sgo.get_odds_by_sport_key = AsyncMock(return_value=FAKE_GAMES)

        with patch("app.services.sports_game_odds.SportsGameOddsService", return_value=mock_sgo), \
             patch.object(svc, "_try_odds_api_io_fallback", AsyncMock(return_value=[])):
            result = await svc.get_odds("basketball_nba")

        assert result == FAKE_GAMES

    @pytest.mark.asyncio
    async def test_exhaustion_flag_auto_resets_after_one_hour(self):
        """_odds_api_exhausted should reset when more than _EXHAUSTION_RESET_SECONDS have passed."""
        sports_api_module._odds_api_exhausted = True
        # Set timestamp 2 hours ago
        sports_api_module._odds_api_exhausted_at = time.time() - 7300

        svc = SportsAPIService()
        svc.odds_api_key = None  # Ensure no actual API call

        mock_sgo = MagicMock()
        mock_sgo.is_configured = False  # SGO not configured either — we just want to verify reset
        mock_sgo.get_odds_by_sport_key = AsyncMock(return_value=[])

        with patch("app.services.sports_game_odds.SportsGameOddsService", return_value=mock_sgo), \
             patch.object(svc, "_try_odds_api_io_fallback", AsyncMock(return_value=[])):
            await svc.get_odds("basketball_nba")

        # Flag should have been reset
        assert sports_api_module._odds_api_exhausted is False


# ---------------------------------------------------------------------------
# SGO sport key mapping
# ---------------------------------------------------------------------------

class TestSGOSportKeyMap:
    @pytest.mark.asyncio
    async def test_nba_key_maps_correctly(self):
        """basketball_nba should map to 'nba' in SGO."""
        from app.services.sports_game_odds import SPORT_KEY_MAP
        assert SPORT_KEY_MAP.get("basketball_nba") == "nba"

    @pytest.mark.asyncio
    async def test_ncaab_key_maps_correctly(self):
        from app.services.sports_game_odds import SPORT_KEY_MAP
        assert SPORT_KEY_MAP.get("basketball_ncaab") == "ncaab"

    @pytest.mark.asyncio
    async def test_unknown_key_returns_empty(self):
        """An unmapped sport key should return [] without raising."""
        from app.services.sports_game_odds import SportsGameOddsService

        # Patch settings so the service thinks it's configured
        with patch("app.services.sports_game_odds.settings") as mock_cfg:
            mock_cfg.SPORTS_GAME_ODDS_API_KEY = "fake_key"
            svc = SportsGameOddsService()

        result = await svc.get_odds_by_sport_key("american_football_nfl")
        assert result == []
