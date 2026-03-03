"""
Unit tests for NBAStatsService (app/services/nba_stats_service.py).

All external HTTP calls are mocked with httpx.Response stubs so tests run
without a live API key or network access.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ---------------------------------------------------------------------------
# Service under test
# ---------------------------------------------------------------------------

from app.services.nba_stats_service import NBAStatsService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    """NBAStatsService with THE_ODDS_API_KEY set to a dummy value."""
    svc = NBAStatsService.__new__(NBAStatsService)
    from app.services.nba_stats_service import TTLCache
    svc._cache = TTLCache()
    svc.odds_api_key = "test_api_key"
    svc._current_season = 2025
    return svc


@pytest.fixture
def service_no_key():
    """NBAStatsService with no API key configured."""
    svc = NBAStatsService.__new__(NBAStatsService)
    from app.services.nba_stats_service import TTLCache
    svc._cache = TTLCache()
    svc.odds_api_key = None
    svc._current_season = 2025
    return svc


# ---------------------------------------------------------------------------
# get_injury_report — HTTP 404 (known-unavailable endpoint)
# ---------------------------------------------------------------------------


class TestGetInjuryReport:

    @pytest.mark.asyncio
    async def test_no_api_key_returns_empty_list(self, service_no_key):
        """When no API key is configured, returns [] without making any HTTP call."""
        result = await service_no_key.get_injury_report()
        assert result == []

    @pytest.mark.asyncio
    async def test_no_api_key_with_team_filter_returns_empty_list(self, service_no_key):
        """Team filter doesn't change behaviour when key is missing."""
        result = await service_no_key.get_injury_report(team_abbreviation="LAL")
        assert result == []

    @pytest.mark.asyncio
    async def test_404_returns_empty_list_not_exception(self, service):
        """HTTP 404 (endpoint unavailable) should return [] gracefully."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            # Use a plain MagicMock for the response so raise_for_status is sync
            resp_mock = MagicMock()
            resp_mock.raise_for_status.side_effect = http_error
            mock_client.get = AsyncMock(return_value=resp_mock)

            result = await service.get_injury_report()

        assert result == []

    @pytest.mark.asyncio
    async def test_404_does_not_propagate_error(self, service, caplog):
        """A 404 from the injuries endpoint must NOT produce a logger.error call."""
        import httpx
        import logging

        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            resp_mock = MagicMock()
            resp_mock.raise_for_status.side_effect = http_error
            mock_client.get = AsyncMock(return_value=resp_mock)

            with caplog.at_level(logging.ERROR):
                result = await service.get_injury_report()

        # No ERROR-level log entries should be emitted for a 404
        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_logs == [], (
            f"Expected no ERROR logs for 404, but got: {[r.message for r in error_logs]}"
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_non_404_http_error_returns_empty_list(self, service):
        """Non-404 HTTP errors (e.g. 401, 500) should also return [] gracefully."""
        import httpx

        for status_code in (401, 429, 500):
            mock_response = MagicMock()
            mock_response.status_code = status_code
            http_error = httpx.HTTPStatusError(
                f"{status_code} error", request=MagicMock(), response=mock_response
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
    async def test_success_path_filters_by_team(self, service):
        """When the API succeeds, team_abbreviation filter is applied correctly."""
        import httpx

        raw_data = [
            {
                "team": "LAL",
                "injuries": [{"player": "LeBron James", "status": "Questionable", "description": "knee"}],
            },
            {
                "team": "BOS",
                "injuries": [{"player": "Jayson Tatum", "status": "Active", "description": ""}],
            },
        ]

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = raw_data
            mock_client.get.return_value = mock_resp

            result = await service.get_injury_report(team_abbreviation="LAL")

        assert len(result) == 1
        assert result[0]["player_name"] == "LeBron James"
        assert result[0]["team"] == "LAL"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_http(self, service):
        """Cached result is returned immediately without an HTTP call."""
        cached_data = [{"player_name": "Cached Player", "team": "LAL", "status": "Out", "description": ""}]
        service._cache.set("injuries:all", cached_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await service.get_injury_report()

        mock_client_cls.assert_not_called()
        assert result == cached_data


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
        """BALLDONTLIE_API_KEY should be an Optional[str] in settings (no AttributeError)."""
        from app.config import settings
        # Attribute must exist and default to None when not set
        assert hasattr(settings, "BALLDONTLIE_API_KEY")
        # Either None or a string — never missing
        assert settings.BALLDONTLIE_API_KEY is None or isinstance(settings.BALLDONTLIE_API_KEY, str)

    def test_ball_dont_lie_api_key_alias_is_optional(self):
        """BALL_DONT_LIE_API_KEY alias should also be accessible."""
        from app.config import settings
        assert hasattr(settings, "BALL_DONT_LIE_API_KEY")
        assert settings.BALL_DONT_LIE_API_KEY is None or isinstance(settings.BALL_DONT_LIE_API_KEY, str)
