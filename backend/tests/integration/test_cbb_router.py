"""
Integration tests for the CBB Sharp Money & Edge router (app/routers/cbb_sharp.py).

Pattern mirrors test_dvp_router.py:
  - Build a minimal FastAPI app around just the CBB router
  - Patch module-level service instances per test
  - No database or Redis required
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.cbb_sharp as cbb_router_module

# ---------------------------------------------------------------------------
# Lightweight test app
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(cbb_router_module.router, prefix="/api/v1")


@pytest.fixture(scope="module")
def client():
    with TestClient(_test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Shared mock payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_games():
    return [
        {
            "game_id": "mock_001",
            "home_team": "Duke Blue Devils",
            "away_team": "UNC Tar Heels",
            "commence_time": "2026-03-01T19:00:00Z",
            "sport": "NCAAB",
            "best_edge": 0.035,
            "bookmaker_count": 3,
            "sharp_book_count": 1,
            "markets": {
                "h2h": {
                    "market_type": "h2h",
                    "bets": [
                        {
                            "side": "UNC Tar Heels",
                            "true_prob": 0.45,
                            "fair_odds": 120.0,
                            "best_available_odds": 126,
                            "best_book": "fanduel",
                            "market_implied_prob": 0.4425,
                            "edge": 0.035,
                            "ev_per_unit": 0.042,
                            "kelly_fraction": 0.025,
                            "is_positive_ev": True,
                        }
                    ],
                    "best_edge": 0.035,
                }
            },
        }
    ]


@pytest.fixture
def mock_sharp_signals():
    return [
        {
            "game_id": "mock_001",
            "home_team": "Duke Blue Devils",
            "away_team": "UNC Tar Heels",
            "market": "h2h",
            "sharp_side": "UNC Tar Heels",
            "signal_types": ["book_divergence", "reverse_line_movement"],
            "score": 2,
            "score_label": "moderate_signal",
            "details": {"divergence": 0.045},
            "created_at": "2026-03-01T18:00:00Z",
        }
    ]


@pytest.fixture
def mock_divergences():
    return [
        {
            "game_id": "mock_001",
            "home_team": "Duke Blue Devils",
            "away_team": "UNC Tar Heels",
            "sharp_home_prob": 0.58,
            "square_home_prob": 0.53,
            "max_divergence": 0.05,
            "sharp_books_used": ["pinnacle"],
            "square_books_used": ["fanduel"],
            "interpretation": "Gap of 5.0%",
        }
    ]


def _patch_edge(return_value):
    return patch.object(
        cbb_router_module.edge_calc,
        "get_games_with_edge",
        new=AsyncMock(return_value=return_value),
    )


def _patch_sharp(return_value):
    return patch.object(
        cbb_router_module.sharp_tracker,
        "get_sharp_signals",
        new=AsyncMock(return_value=return_value),
    )


def _patch_line_movement(return_value):
    return patch.object(
        cbb_router_module.sharp_tracker,
        "get_line_movement_report",
        new=AsyncMock(return_value=return_value),
    )


def _patch_divergence(return_value):
    return patch.object(
        cbb_router_module.sharp_tracker,
        "get_book_divergence",
        new=AsyncMock(return_value=return_value),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/cbb/games
# ---------------------------------------------------------------------------

class TestGetCBBGames:
    def test_returns_200(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/games")
        assert resp.status_code == 200

    def test_body_has_games_key(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/games")
        assert "games" in resp.json()

    def test_sport_is_ncaab(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/games")
        assert resp.json()["sport"] == "NCAAB"

    def test_total_games_count(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/games")
        assert resp.json()["total_games"] == 1

    def test_min_bookmakers_filter_applied(self, client, mock_games):
        with _patch_edge(mock_games):
            # mock_games[0] has bookmaker_count=3, filter at 4 → 0 results
            resp = client.get("/api/v1/cbb/games?min_bookmakers=4")
        assert resp.json()["total_games"] == 0

    def test_error_returns_500(self, client):
        with patch.object(
            cbb_router_module.edge_calc,
            "get_games_with_edge",
            new=AsyncMock(side_effect=RuntimeError("API down")),
        ):
            resp = client.get("/api/v1/cbb/games")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/cbb/edge
# ---------------------------------------------------------------------------

class TestGetCBBEdge:
    def test_returns_200(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/edge")
        assert resp.status_code == 200

    def test_body_has_bets_key(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/edge")
        assert "bets" in resp.json()

    def test_only_positive_ev_bets_returned(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/edge?min_edge=0.0")
        for bet in resp.json()["bets"]:
            assert bet["is_positive_ev"] is True

    def test_methodology_in_response(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/edge")
        assert "methodology" in resp.json()

    def test_min_edge_filter_excludes_low_edge(self, client, mock_games):
        with _patch_edge(mock_games):
            # The mock bet has edge=0.035; filter to 0.05 should exclude it
            resp = client.get("/api/v1/cbb/edge?min_edge=0.05")
        assert resp.json()["total_positive_ev_bets"] == 0

    def test_market_filter_accepted(self, client, mock_games):
        with _patch_edge(mock_games):
            resp = client.get("/api/v1/cbb/edge?market=h2h")
        assert resp.status_code == 200

    def test_error_returns_500(self, client):
        with patch.object(
            cbb_router_module.edge_calc,
            "get_games_with_edge",
            new=AsyncMock(side_effect=Exception("timeout")),
        ):
            resp = client.get("/api/v1/cbb/edge")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/cbb/sharp
# ---------------------------------------------------------------------------

class TestGetSharpSignals:
    def test_returns_200(self, client, mock_sharp_signals):
        with _patch_sharp(mock_sharp_signals):
            resp = client.get("/api/v1/cbb/sharp")
        assert resp.status_code == 200

    def test_body_has_signals_key(self, client, mock_sharp_signals):
        with _patch_sharp(mock_sharp_signals):
            resp = client.get("/api/v1/cbb/sharp")
        assert "signals" in resp.json()

    def test_total_signals_count(self, client, mock_sharp_signals):
        with _patch_sharp(mock_sharp_signals):
            resp = client.get("/api/v1/cbb/sharp")
        assert resp.json()["total_signals"] == 1

    def test_signal_type_legend_present(self, client, mock_sharp_signals):
        with _patch_sharp(mock_sharp_signals):
            resp = client.get("/api/v1/cbb/sharp")
        assert "signal_type_legend" in resp.json()

    def test_min_score_param_forwarded(self, client):
        with patch.object(
            cbb_router_module.sharp_tracker,
            "get_sharp_signals",
            new=AsyncMock(return_value=[]),
        ) as mock_fn:
            client.get("/api/v1/cbb/sharp?min_score=3")
            mock_fn.assert_awaited_once_with(min_score=3)

    def test_error_returns_500(self, client):
        with patch.object(
            cbb_router_module.sharp_tracker,
            "get_sharp_signals",
            new=AsyncMock(side_effect=RuntimeError("fail")),
        ):
            resp = client.get("/api/v1/cbb/sharp")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/cbb/line-movement
# ---------------------------------------------------------------------------

class TestGetLineMovement:
    def test_returns_200(self, client):
        with _patch_line_movement([]):
            resp = client.get("/api/v1/cbb/line-movement")
        assert resp.status_code == 200

    def test_body_has_movement_data_key(self, client):
        movement = [{"game_id": "g1", "spread_movement": 0.5}]
        with _patch_line_movement(movement):
            resp = client.get("/api/v1/cbb/line-movement")
        assert "movement_data" in resp.json()

    def test_total_games_reflects_movement_count(self, client):
        movement = [{"game_id": "g1"}, {"game_id": "g2"}]
        with _patch_line_movement(movement):
            resp = client.get("/api/v1/cbb/line-movement")
        assert resp.json()["total_games"] == 2

    def test_error_returns_500(self, client):
        with patch.object(
            cbb_router_module.sharp_tracker,
            "get_line_movement_report",
            new=AsyncMock(side_effect=Exception("fail")),
        ):
            resp = client.get("/api/v1/cbb/line-movement")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/cbb/book-divergence
# ---------------------------------------------------------------------------

class TestGetBookDivergence:
    def test_returns_200(self, client, mock_divergences):
        with _patch_divergence(mock_divergences):
            resp = client.get("/api/v1/cbb/book-divergence")
        assert resp.status_code == 200

    def test_body_has_divergences_key(self, client, mock_divergences):
        with _patch_divergence(mock_divergences):
            resp = client.get("/api/v1/cbb/book-divergence")
        assert "divergences" in resp.json()

    def test_total_divergences_count(self, client, mock_divergences):
        with _patch_divergence(mock_divergences):
            resp = client.get("/api/v1/cbb/book-divergence")
        assert resp.json()["total_divergences"] == 1

    def test_divergence_threshold_in_response(self, client, mock_divergences):
        with _patch_divergence(mock_divergences):
            resp = client.get("/api/v1/cbb/book-divergence")
        assert "divergence_threshold" in resp.json()

    def test_error_returns_500(self, client):
        with patch.object(
            cbb_router_module.sharp_tracker,
            "get_book_divergence",
            new=AsyncMock(side_effect=Exception("fail")),
        ):
            resp = client.get("/api/v1/cbb/book-divergence")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/cbb/best-bets
# ---------------------------------------------------------------------------

class TestGetBestBets:
    def _patch_both(self, games, signals):
        edge_patch = patch.object(
            cbb_router_module.edge_calc,
            "get_games_with_edge",
            new=AsyncMock(return_value=games),
        )
        sharp_patch = patch.object(
            cbb_router_module.sharp_tracker,
            "get_sharp_signals",
            new=AsyncMock(return_value=signals),
        )
        return edge_patch, sharp_patch

    def test_returns_200(self, client, mock_games, mock_sharp_signals):
        ep, sp = self._patch_both(mock_games, mock_sharp_signals)
        with ep, sp:
            resp = client.get("/api/v1/cbb/best-bets")
        assert resp.status_code == 200

    def test_body_has_bets_key(self, client, mock_games, mock_sharp_signals):
        ep, sp = self._patch_both(mock_games, mock_sharp_signals)
        with ep, sp:
            resp = client.get("/api/v1/cbb/best-bets")
        assert "bets" in resp.json()

    def test_filters_in_response(self, client, mock_games, mock_sharp_signals):
        ep, sp = self._patch_both(mock_games, mock_sharp_signals)
        with ep, sp:
            resp = client.get("/api/v1/cbb/best-bets")
        assert "filters" in resp.json()

    def test_ranking_method_in_response(self, client, mock_games, mock_sharp_signals):
        ep, sp = self._patch_both(mock_games, mock_sharp_signals)
        with ep, sp:
            resp = client.get("/api/v1/cbb/best-bets")
        assert "ranking_method" in resp.json()

    def test_limit_param_respected(self, client, mock_games, mock_sharp_signals):
        ep, sp = self._patch_both(mock_games * 5, mock_sharp_signals)
        with ep, sp:
            resp = client.get("/api/v1/cbb/best-bets?limit=2")
        assert len(resp.json()["bets"]) <= 2

    def test_error_returns_500(self, client):
        with patch.object(
            cbb_router_module.edge_calc,
            "get_games_with_edge",
            new=AsyncMock(side_effect=Exception("fail")),
        ):
            resp = client.get("/api/v1/cbb/best-bets")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/cbb/summary
# ---------------------------------------------------------------------------

class TestGetCBBSummary:
    def _patch_all(self, games, signals, divergences):
        return (
            patch.object(cbb_router_module.edge_calc, "get_games_with_edge",
                         new=AsyncMock(return_value=games)),
            patch.object(cbb_router_module.sharp_tracker, "get_sharp_signals",
                         new=AsyncMock(return_value=signals)),
            patch.object(cbb_router_module.sharp_tracker, "get_book_divergence",
                         new=AsyncMock(return_value=divergences)),
        )

    def test_returns_200(self, client, mock_games, mock_sharp_signals, mock_divergences):
        p1, p2, p3 = self._patch_all(mock_games, mock_sharp_signals, mock_divergences)
        with p1, p2, p3:
            resp = client.get("/api/v1/cbb/summary")
        assert resp.status_code == 200

    def test_body_has_active_games(self, client, mock_games, mock_sharp_signals, mock_divergences):
        p1, p2, p3 = self._patch_all(mock_games, mock_sharp_signals, mock_divergences)
        with p1, p2, p3:
            resp = client.get("/api/v1/cbb/summary")
        assert "active_games" in resp.json()

    def test_active_games_count(self, client, mock_games, mock_sharp_signals, mock_divergences):
        p1, p2, p3 = self._patch_all(mock_games, mock_sharp_signals, mock_divergences)
        with p1, p2, p3:
            resp = client.get("/api/v1/cbb/summary")
        assert resp.json()["active_games"] == 1

    def test_sharp_signal_count(self, client, mock_games, mock_sharp_signals, mock_divergences):
        p1, p2, p3 = self._patch_all(mock_games, mock_sharp_signals, mock_divergences)
        with p1, p2, p3:
            resp = client.get("/api/v1/cbb/summary")
        assert resp.json()["sharp_signal_count"] == 1

    def test_top_signals_included(self, client, mock_games, mock_sharp_signals, mock_divergences):
        p1, p2, p3 = self._patch_all(mock_games, mock_sharp_signals, mock_divergences)
        with p1, p2, p3:
            resp = client.get("/api/v1/cbb/summary")
        assert "top_signals" in resp.json()

    def test_error_returns_500(self, client):
        with patch.object(
            cbb_router_module.edge_calc,
            "get_games_with_edge",
            new=AsyncMock(side_effect=Exception("fail")),
        ):
            resp = client.get("/api/v1/cbb/summary")
        assert resp.status_code == 500
