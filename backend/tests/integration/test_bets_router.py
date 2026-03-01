"""
Integration tests for the bets router (app/routers/bets.py).

Endpoints tested:
  GET  /api/v1/bets            – best bets (NBA ML + fallback)
  POST /api/v1/bayesian        – Bayesian analysis
  GET  /api/v1/predictions/nba/today – NBA predictions
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.bets as bets_router_module

# ---------------------------------------------------------------------------
# Lightweight test app
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(bets_router_module.router, prefix="/api/v1")


@pytest.fixture(scope="module")
def client():
    with TestClient(_test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_predictions():
    return [
        {
            "home_team": "Lakers",
            "away_team": "Celtics",
            "moneyline_prediction": {
                "home_win_prob": 0.60,
                "away_win_prob": 0.40,
            },
            "underover_prediction": {
                "over_prob": 0.65,
                "under_prob": 0.35,
                "recommendation": "over",
                "total_points": 224.5,
            },
            "expected_value": {
                "home_ev": 0.08,
                "best_bet": "home",
                "home_ev": 0.08,
                "home_odds": -150,
            },
            "confidence": 0.70,
            "kelly_criterion": 0.025,
        }
    ]


@pytest.fixture
def mock_bayesian_result():
    return {
        "posterior_prob": 0.62,
        "credible_interval": [0.55, 0.69],
        "edge": 0.07,
        "recommendation": "BET",
    }


def _patch_predictor(return_value):
    return patch.object(
        bets_router_module.nba_predictor,
        "predict_today_games",
        new=AsyncMock(return_value=return_value),
    )


def _patch_bayesian(return_value):
    return patch.object(
        bets_router_module.bayesian_analyzer,
        "compute_posterior",
        return_value=return_value,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/bets  (NBA)
# ---------------------------------------------------------------------------

class TestGetBestBetsNBA:
    def test_returns_200(self, client, mock_predictions):
        with _patch_predictor(mock_predictions):
            resp = client.get("/api/v1/bets?sport=nba")
        assert resp.status_code == 200

    def test_returns_list(self, client, mock_predictions):
        with _patch_predictor(mock_predictions):
            resp = client.get("/api/v1/bets?sport=nba")
        assert isinstance(resp.json(), list)

    def test_bets_sorted_by_edge_descending(self, client, mock_predictions):
        # Duplicate the prediction to get multiple bets
        preds = mock_predictions * 3
        with _patch_predictor(preds):
            resp = client.get("/api/v1/bets?sport=nba&min_edge=0.0")
        bets = resp.json()
        edges = [b["edge"] for b in bets]
        assert edges == sorted(edges, reverse=True)

    def test_limit_respected(self, client, mock_predictions):
        with _patch_predictor(mock_predictions * 5):
            resp = client.get("/api/v1/bets?sport=nba&limit=2&min_edge=0.0")
        assert len(resp.json()) <= 2

    def test_error_returns_500(self, client):
        with patch.object(
            bets_router_module.nba_predictor,
            "predict_today_games",
            new=AsyncMock(side_effect=RuntimeError("model failure")),
        ):
            resp = client.get("/api/v1/bets?sport=nba")
        assert resp.status_code == 500


class TestGetBestBetsOtherSport:
    def test_non_nba_returns_fallback_bet(self, client):
        resp = client.get("/api/v1/bets?sport=nfl")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["sport"] == "nfl"


# ---------------------------------------------------------------------------
# POST /api/v1/bayesian
# ---------------------------------------------------------------------------

class TestRunBayesianAnalysis:
    def test_returns_200(self, client, mock_bayesian_result):
        with _patch_bayesian(mock_bayesian_result):
            resp = client.post(
                "/api/v1/bayesian",
                json={"devig_prob": 0.55, "implied_prob": 0.48, "features": {}},
            )
        assert resp.status_code == 200

    def test_returns_posterior_prob(self, client, mock_bayesian_result):
        with _patch_bayesian(mock_bayesian_result):
            resp = client.post(
                "/api/v1/bayesian",
                json={"devig_prob": 0.55, "implied_prob": 0.48, "features": {}},
            )
        assert "posterior_prob" in resp.json()

    def test_error_returns_500(self, client):
        with patch.object(
            bets_router_module.bayesian_analyzer,
            "compute_posterior",
            side_effect=Exception("model error"),
        ):
            resp = client.post(
                "/api/v1/bayesian",
                json={"devig_prob": 0.55, "implied_prob": 0.48},
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/nba/today
# ---------------------------------------------------------------------------

class TestGetNBAPredictionsToday:
    def test_returns_200(self, client, mock_predictions):
        with _patch_predictor(mock_predictions):
            resp = client.get("/api/v1/predictions/nba/today")
        assert resp.status_code == 200

    def test_body_has_predictions_key(self, client, mock_predictions):
        with _patch_predictor(mock_predictions):
            resp = client.get("/api/v1/predictions/nba/today")
        assert "predictions" in resp.json()

    def test_sport_is_nba(self, client, mock_predictions):
        with _patch_predictor(mock_predictions):
            resp = client.get("/api/v1/predictions/nba/today")
        assert resp.json()["sport"] == "NBA"

    def test_total_games_count(self, client, mock_predictions):
        with _patch_predictor(mock_predictions):
            resp = client.get("/api/v1/predictions/nba/today")
        assert resp.json()["total_games"] == 1

    def test_method_is_xgboost(self, client, mock_predictions):
        with _patch_predictor(mock_predictions):
            resp = client.get("/api/v1/predictions/nba/today")
        assert resp.json()["method"] == "xgboost"

    def test_error_returns_500(self, client):
        with patch.object(
            bets_router_module.nba_predictor,
            "predict_today_games",
            new=AsyncMock(side_effect=RuntimeError("fetch failed")),
        ):
            resp = client.get("/api/v1/predictions/nba/today")
        assert resp.status_code == 500
