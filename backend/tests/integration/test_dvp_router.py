"""
Integration tests for the DvP router (app/routers/dvp.py).

A minimal FastAPI test app is built around just the DvP router so we
avoid having to wire up the full lifespan (DB init, Redis, etc.).
The module-level dvp_agent instance is patched per test.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.dvp as dvp_router_module

# ---------------------------------------------------------------------------
# Build a lightweight test app — no lifespan events
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(dvp_router_module.router, prefix="/api/v1")


@pytest.fixture(scope="module")
def client():
    with TestClient(_test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_analysis_result():
    return {
        "task_type": "full_analysis",
        "count": 2,
        "high_value_count": 1,
        "projections": [
            {"Player": "LeBron James", "Recommendation": "HIGH VALUE OVER",
             "Projected_Line": 28.5, "Stat_Category": "PTS"},
            {"Player": "Anthony Davis", "Recommendation": "LEAN OVER",
             "Projected_Line": 14.0, "Stat_Category": "REB"},
        ],
    }


@pytest.fixture
def agent_error_result():
    return {"error": "nba_api rate-limited"}


def _patch_agent(return_value):
    """Helper: patch dvp_agent.execute with a fixed return value."""
    return patch.object(
        dvp_router_module.dvp_agent,
        "execute",
        new=AsyncMock(return_value=return_value),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/dvp/analysis
# ---------------------------------------------------------------------------

class TestGetDvpAnalysis:
    def test_success_returns_200(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result):
            resp = client.get("/api/v1/dvp/analysis")
        assert resp.status_code == 200

    def test_success_body_has_projections(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result):
            resp = client.get("/api/v1/dvp/analysis")
        assert "projections" in resp.json()

    def test_success_count_correct(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result):
            resp = client.get("/api/v1/dvp/analysis")
        assert resp.json()["count"] == 2

    def test_agent_error_returns_500(self, client, agent_error_result):
        with _patch_agent(agent_error_result):
            resp = client.get("/api/v1/dvp/analysis")
        assert resp.status_code == 500

    def test_default_query_params_send_full_analysis_type(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result) as mock_exec:
            client.get("/api/v1/dvp/analysis")
        call_task = mock_exec.call_args[0][0]
        assert call_task["type"] == "full_analysis"

    def test_high_value_only_true_sends_correct_type(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result) as mock_exec:
            client.get("/api/v1/dvp/analysis?high_value_only=true")
        call_task = mock_exec.call_args[0][0]
        assert call_task["type"] == "high_value_only"

    def test_high_value_only_false_sends_full_analysis_type(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result) as mock_exec:
            client.get("/api/v1/dvp/analysis?high_value_only=false")
        call_task = mock_exec.call_args[0][0]
        assert call_task["type"] == "full_analysis"

    def test_num_recent_param_forwarded(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result) as mock_exec:
            client.get("/api/v1/dvp/analysis?num_recent=10")
        call_task = mock_exec.call_args[0][0]
        assert call_task["num_recent"] == 10

    def test_default_num_recent_is_15(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result) as mock_exec:
            client.get("/api/v1/dvp/analysis")
        call_task = mock_exec.call_args[0][0]
        assert call_task["num_recent"] == 15


# ---------------------------------------------------------------------------
# POST /api/v1/dvp/analysis
# ---------------------------------------------------------------------------

class TestPostDvpAnalysis:
    def test_success_returns_200(self, client, full_analysis_result):
        with _patch_agent(full_analysis_result):
            resp = client.post("/api/v1/dvp/analysis", json={"type": "full_analysis"})
        assert resp.status_code == 200

    def test_custom_slate_forwarded_to_agent(self, client, full_analysis_result):
        payload = {"type": "full_analysis", "slate_data": {"games": []}}
        with _patch_agent(full_analysis_result) as mock_exec:
            client.post("/api/v1/dvp/analysis", json=payload)
        call_task = mock_exec.call_args[0][0]
        assert call_task["slate_data"] == {"games": []}

    def test_agent_error_returns_500(self, client, agent_error_result):
        with _patch_agent(agent_error_result):
            resp = client.post("/api/v1/dvp/analysis", json={})
        assert resp.status_code == 500

    def test_error_detail_present_in_500_response(self, client, agent_error_result):
        with _patch_agent(agent_error_result):
            resp = client.post("/api/v1/dvp/analysis", json={})
        assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/v1/dvp/implied-totals
# ---------------------------------------------------------------------------

class TestGetImpliedTotals:
    def test_success_returns_200(self, client):
        result = {"implied_totals": {"LAL": 112.75, "BOS": 107.25}}
        with _patch_agent(result):
            resp = client.get("/api/v1/dvp/implied-totals")
        assert resp.status_code == 200

    def test_implied_totals_in_body(self, client):
        result = {"implied_totals": {"LAL": 112.75, "BOS": 107.25}}
        with _patch_agent(result):
            resp = client.get("/api/v1/dvp/implied-totals")
        assert "implied_totals" in resp.json()

    def test_agent_error_returns_500(self, client, agent_error_result):
        with _patch_agent(agent_error_result):
            resp = client.get("/api/v1/dvp/implied-totals")
        assert resp.status_code == 500

    def test_sends_implied_totals_task_type(self, client):
        with _patch_agent({"implied_totals": {}}) as mock_exec:
            client.get("/api/v1/dvp/implied-totals")
        call_task = mock_exec.call_args[0][0]
        assert call_task["type"] == "implied_totals"


# ---------------------------------------------------------------------------
# GET /api/v1/dvp/player/{player_name}
# ---------------------------------------------------------------------------

class TestGetPlayerProjection:
    def test_player_found_returns_200(self, client):
        result = {"Player": "LeBron James", "Projected_Line": 28.5, "Stat_Category": "PTS"}
        with _patch_agent(result):
            resp = client.get("/api/v1/dvp/player/LeBron%20James")
        assert resp.status_code == 200

    def test_player_found_body_has_projection(self, client):
        result = {"Player": "LeBron James", "Projected_Line": 28.5}
        with _patch_agent(result):
            resp = client.get("/api/v1/dvp/player/LeBron%20James")
        assert resp.json()["Projected_Line"] == 28.5

    def test_player_not_found_returns_404(self, client):
        error_result = {"error": "Player 'Unknown' not found for stat 'PTS'"}
        with _patch_agent(error_result):
            resp = client.get("/api/v1/dvp/player/Unknown")
        assert resp.status_code == 404

    def test_404_not_500_for_missing_player(self, client):
        """Router must raise 404 (not 500) for player lookup failures."""
        error_result = {"error": "Player not found"}
        with _patch_agent(error_result):
            resp = client.get("/api/v1/dvp/player/ghost")
        assert resp.status_code == 404

    def test_default_stat_is_pts(self, client):
        result = {"Player": "LeBron James", "Projected_Line": 28.5}
        with _patch_agent(result) as mock_exec:
            client.get("/api/v1/dvp/player/LeBron%20James")
        call_task = mock_exec.call_args[0][0]
        assert call_task["stat_category"] == "PTS"

    def test_stat_param_forwarded(self, client):
        result = {"Player": "LeBron James", "Projected_Line": 10.0}
        with _patch_agent(result) as mock_exec:
            client.get("/api/v1/dvp/player/LeBron%20James?stat=REB")
        call_task = mock_exec.call_args[0][0]
        assert call_task["stat_category"] == "REB"

    def test_player_name_forwarded_url_decoded(self, client):
        result = {"Player": "LeBron James", "Projected_Line": 28.5}
        with _patch_agent(result) as mock_exec:
            client.get("/api/v1/dvp/player/LeBron%20James")
        call_task = mock_exec.call_args[0][0]
        assert call_task["player_name"] == "LeBron James"

    def test_task_type_is_single_player(self, client):
        result = {"Player": "LeBron James", "Projected_Line": 28.5}
        with _patch_agent(result) as mock_exec:
            client.get("/api/v1/dvp/player/LeBron%20James")
        call_task = mock_exec.call_args[0][0]
        assert call_task["type"] == "single_player"


# ---------------------------------------------------------------------------
# GET /api/v1/dvp/status
# ---------------------------------------------------------------------------

class TestGetDvpStatus:
    def test_returns_200(self, client):
        resp = client.get("/api/v1/dvp/status")
        assert resp.status_code == 200

    def test_response_has_name(self, client):
        resp = client.get("/api/v1/dvp/status")
        assert "name" in resp.json()

    def test_response_has_execution_counts(self, client):
        resp = client.get("/api/v1/dvp/status")
        data = resp.json()
        assert "total_executions" in data
        assert "total_mistakes" in data

    def test_response_has_mistake_rate(self, client):
        resp = client.get("/api/v1/dvp/status")
        assert "mistake_rate" in resp.json()

    def test_does_not_call_agent_execute(self, client):
        """Status endpoint reads state directly — must NOT call execute()."""
        with patch.object(
            dvp_router_module.dvp_agent, "execute", new=AsyncMock()
        ) as mock_exec:
            client.get("/api/v1/dvp/status")
        mock_exec.assert_not_called()
