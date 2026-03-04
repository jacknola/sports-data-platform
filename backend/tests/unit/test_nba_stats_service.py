"""
Unit tests for NBAStatsService (app/services/nba_stats_service.py).

All external HTTP calls are mocked with httpx.Response stubs so tests run
without a live API key or network access.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Service under test
# ---------------------------------------------------------------------------

from app.services.nba_stats_service import NBAStatsService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    """NBAStatsService with a dummy odds_api_key."""
    svc = NBAStatsService.__new__(NBAStatsService)
    from app.services.nba_stats_service import TTLCache
    svc._cache = TTLCache()
    svc.odds_api_key = "test_api_key"
    svc._current_season = 2025
    return svc


def _make_espn_response(team_abbr: str = "LAL", player_name: str = "LeBron James") -> dict:
    """Build a minimal ESPN injuries API response."""
    return {
        "injuries": [
            {
                "injuries": [
                    {
                        "status": "Out",
                        "shortComment": "knee soreness",
                        "details": {"type": "Knee", "returnDate": "2026-03-15"},
                        "athlete": {
                            "displayName": player_name,
                            "team": {"abbreviation": team_abbr},
                            "position": {"abbreviation": "F"},
                        },
                    }
                ]
            }
        ]
    }


# ---------------------------------------------------------------------------
# get_injury_report — ESPN public API (no key required)
# ---------------------------------------------------------------------------


class TestGetInjuryReport:

    @pytest.mark.asyncio
    async def test_returns_injury_list_on_success(self, service):
        """Successful ESPN response is parsed into the standard injury dict format."""
        espn_data = _make_espn_response("BOS", "Jayson Tatum")
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            resp_mock = MagicMock()
            resp_mock.raise_for_status.return_value = None
            resp_mock.json.return_value = espn_data
            mock_client.get = AsyncMock(return_value=resp_mock)

            result = await service.get_injury_report()

        assert len(result) == 1
        entry = result[0]
        assert entry["player_name"] == "Jayson Tatum"
        assert entry["team"] == "BOS"
        assert entry["status"] == "Out"
        assert entry["description"] == "knee soreness"
        assert entry["injury_type"] == "Knee"
        assert entry["return_date"] == "2026-03-15"
        assert entry["position"] == "F"

    @pytest.mark.asyncio
    async def test_team_abbreviation_filter(self, service):
        """Only entries for the requested team abbreviation are returned."""
        espn_data = {
            "injuries": [
                {
                    "injuries": [
                        {
                            "status": "Out",
                            "shortComment": "knee",
                            "details": {"type": "Knee"},
                            "athlete": {
                                "displayName": "LeBron James",
                                "team": {"abbreviation": "LAL"},
                                "position": {"abbreviation": "F"},
                            },
                        }
                    ]
                },
                {
                    "injuries": [
                        {
                            "status": "Questionable",
                            "shortComment": "ankle",
                            "details": {"type": "Ankle"},
                            "athlete": {
                                "displayName": "Jayson Tatum",
                                "team": {"abbreviation": "BOS"},
                                "position": {"abbreviation": "F"},
                            },
                        }
                    ]
                },
            ]
        }
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            resp_mock = MagicMock()
            resp_mock.raise_for_status.return_value = None
            resp_mock.json.return_value = espn_data
            mock_client.get = AsyncMock(return_value=resp_mock)

            result = await service.get_injury_report(team_abbreviation="LAL")

        assert len(result) == 1
        assert result[0]["player_name"] == "LeBron James"

    @pytest.mark.asyncio
    async def test_team_abbreviation_filter_case_insensitive(self, service):
        """Team abbreviation filter is case-insensitive."""
        espn_data = _make_espn_response("LAL", "LeBron James")
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            resp_mock = MagicMock()
            resp_mock.raise_for_status.return_value = None
            resp_mock.json.return_value = espn_data
            mock_client.get = AsyncMock(return_value=resp_mock)

            result = await service.get_injury_report(team_abbreviation="lal")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_list(self, service):
        """Any HTTP error returns [] gracefully without raising."""
        import httpx

        for status_code in (404, 401, 429, 500):
            mock_response = MagicMock()
            mock_response.status_code = status_code
            http_error = httpx.HTTPStatusError(
                f"{status_code}", request=MagicMock(), response=mock_response
            )
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                resp_mock = MagicMock()
                resp_mock.raise_for_status.side_effect = http_error
                mock_client.get = AsyncMock(return_value=resp_mock)

                result = await service.get_injury_report()

            assert result == [], f"Expected [] for HTTP {status_code}"

    @pytest.mark.asyncio
    async def test_http_error_does_not_log_error(self, service, caplog):
        """HTTP errors must NOT log at ERROR level."""
        import httpx
        import logging

        mock_response = MagicMock()
        mock_response.status_code = 503
        http_error = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_response
        )
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            resp_mock = MagicMock()
            resp_mock.raise_for_status.side_effect = http_error
            mock_client.get = AsyncMock(return_value=resp_mock)

            with caplog.at_level(logging.ERROR):
                await service.get_injury_report()

        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_logs == []

    @pytest.mark.asyncio
    async def test_cache_hit_skips_http(self, service):
        """Cached result is returned immediately without an HTTP call."""
        cached = [
            {
                "player_name": "Cached Player",
                "team": "LAL",
                "status": "Out",
                "description": "",
                "injury_type": "",
                "return_date": None,
                "position": "",
            }
        ]
        service._cache.set("injuries:all", cached)

        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await service.get_injury_report()

        mock_client_cls.assert_not_called()
        assert result == cached

    @pytest.mark.asyncio
    async def test_no_api_key_still_fetches_espn(self, service):
        """ESPN requires no API key — injury fetch works even if odds_api_key is None."""
        service.odds_api_key = None
        espn_data = _make_espn_response("MIA", "Jimmy Butler")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            resp_mock = MagicMock()
            resp_mock.raise_for_status.return_value = None
            resp_mock.json.return_value = espn_data
            mock_client.get = AsyncMock(return_value=resp_mock)

            result = await service.get_injury_report()

        mock_client.get.assert_called_once()
        assert len(result) == 1
        assert result[0]["player_name"] == "Jimmy Butler"


# ---------------------------------------------------------------------------
# TTLCache behaviour
# ---------------------------------------------------------------------------


class TestTTLCache:
    def test_set_and_get(self):
        from app.services.nba_stats_service import TTLCache
        cache = TTLCache()
        cache.set("key", "value", ttl=60)
        assert cache.get("key") == "value"

    def test_expired_entry_returns_none(self):
        from app.services.nba_stats_service import TTLCache
        import time
        cache = TTLCache()
        cache.set("key", "value", ttl=0)
        time.sleep(0.01)
        assert cache.get("key") is None

    def test_invalidate_removes_key(self):
        from app.services.nba_stats_service import TTLCache
        cache = TTLCache()
        cache.set("key", "value", ttl=60)
        cache.invalidate("key")
        assert cache.get("key") is None


# ---------------------------------------------------------------------------
# Settings — BallDontLie API keys must be accessible
# ---------------------------------------------------------------------------


class TestSettingsBallDontLieKeys:
    def test_balldontlie_api_key_is_optional(self):
        """BALLDONTLIE_API_KEY should be an Optional[str] in settings."""
        from app.config import settings
        assert hasattr(settings, "BALLDONTLIE_API_KEY")
        assert settings.BALLDONTLIE_API_KEY is None or isinstance(
            settings.BALLDONTLIE_API_KEY, str
        )

    def test_ball_dont_lie_api_key_alias_is_optional(self):
        """BALL_DONT_LIE_API_KEY alias should also be accessible."""
        from app.config import settings
        assert hasattr(settings, "BALL_DONT_LIE_API_KEY")
        assert settings.BALL_DONT_LIE_API_KEY is None or isinstance(
            settings.BALL_DONT_LIE_API_KEY, str
        )
