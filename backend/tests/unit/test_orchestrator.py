"""
Unit tests for app/agents/orchestrator.py

All sub-agents and the AgentMemory are mocked so no real I/O happens.
Tests verify the orchestration flow, agent delegation, and result structure.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_async_agent(name, execute_result=None):
    """Return a mock agent with an async execute() and sync get_agent_status()."""
    agent = MagicMock()
    agent.execute = AsyncMock(return_value=execute_result or {"status": "ok"})
    agent.should_use_ai = AsyncMock(return_value=False)
    agent.get_agent_status = MagicMock(return_value={"name": name, "total_executions": 0})
    agent.learn_from_mistake = AsyncMock()
    return agent


@pytest.fixture
def mock_odds_result():
    return {
        "sport": "nba",
        "value_bets": [
            {"market": "Moneyline", "edge": 0.06, "odds": -110, "posterior_p": 0.58},
        ],
    }


@pytest.fixture
def mock_analysis_result():
    return {"agent": "AnalysisAgent", "posterior_prob": 0.62, "recommendation": "BET"}


@pytest.fixture
def mock_dvp_result():
    return {"count": 4, "high_value_count": 1, "projections": []}


@pytest.fixture
def orchestrator(mock_odds_result, mock_analysis_result, mock_dvp_result):
    """Return an OrchestratorAgent with all sub-agents mocked."""
    with (
        patch("app.agents.orchestrator.OddsAgent",
              return_value=_make_async_agent("OddsAgent", mock_odds_result)),
        patch("app.agents.orchestrator.AnalysisAgent",
              return_value=_make_async_agent("AnalysisAgent", mock_analysis_result)),
        patch("app.agents.orchestrator.TwitterAgent",
              return_value=_make_async_agent("TwitterAgent", {"sentiment": "neutral"})),
        patch("app.agents.orchestrator.ExpertAgent",
              return_value=_make_async_agent("ExpertAgent", {"recommendation": "pass"})),
        patch("app.agents.orchestrator.DvPAgent",
              return_value=_make_async_agent("DvPAgent", mock_dvp_result)),
        patch("app.agents.orchestrator.NCAABDvPAgent",
              return_value=_make_async_agent("NCAABDvPAgent", {"count": 2})),
        patch("app.agents.orchestrator.AgentMemory", return_value=MagicMock(
            store_decision=AsyncMock(),
            get_relevant_context=AsyncMock(return_value=[]),
        )),
    ):
        from app.agents.orchestrator import OrchestratorAgent
        orch = OrchestratorAgent()
    return orch


# ---------------------------------------------------------------------------
# execute_full_analysis
# ---------------------------------------------------------------------------

class TestExecuteFullAnalysis:
    @pytest.mark.asyncio
    async def test_returns_dict(self, orchestrator):
        result = await orchestrator.execute_full_analysis({"sport": "nfl", "teams": []})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_sport_propagated(self, orchestrator):
        result = await orchestrator.execute_full_analysis({"sport": "nfl", "teams": []})
        assert result["sport"] == "nfl"

    @pytest.mark.asyncio
    async def test_odds_agent_called(self, orchestrator):
        await orchestrator.execute_full_analysis({"sport": "nba", "teams": []})
        orchestrator.odds_agent.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_odds_result_in_response(self, orchestrator):
        result = await orchestrator.execute_full_analysis({"sport": "nba", "teams": []})
        assert result["odds"] is not None

    @pytest.mark.asyncio
    async def test_agents_used_list_includes_odds(self, orchestrator):
        result = await orchestrator.execute_full_analysis({"sport": "nba", "teams": []})
        assert "OddsAgent" in result["agents_used"]

    @pytest.mark.asyncio
    async def test_twitter_agent_called_per_team(self, orchestrator):
        await orchestrator.execute_full_analysis({
            "sport": "nba",
            "teams": ["Lakers", "Celtics"],
        })
        assert orchestrator.twitter_agent.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_analysis_agent_called_for_value_bets(self, orchestrator):
        result = await orchestrator.execute_full_analysis({"sport": "nba", "teams": []})
        # 1 value bet in mock → analysis_agent.execute called once
        orchestrator.analysis_agent.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expert_agent_called_when_value_bets_exist(self, orchestrator):
        result = await orchestrator.execute_full_analysis({"sport": "nba", "teams": []})
        orchestrator.expert_agent.execute.assert_awaited_once()
        assert "expert_recommendation" in result

    @pytest.mark.asyncio
    async def test_dvp_agent_called_for_nba(self, orchestrator):
        result = await orchestrator.execute_full_analysis({
            "sport": "basketball_nba",
            "teams": [],
        })
        orchestrator.dvp_agent.execute.assert_awaited_once()
        assert "dvp" in result

    @pytest.mark.asyncio
    async def test_dvp_agent_not_called_for_ncaab(self, orchestrator):
        await orchestrator.execute_full_analysis({"sport": "ncaab", "teams": []})
        orchestrator.dvp_agent.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ncaab_dvp_agent_called_for_ncaab(self, orchestrator):
        result = await orchestrator.execute_full_analysis({
            "sport": "basketball_ncaab",
            "teams": [],
        })
        orchestrator.ncaab_dvp_agent.execute.assert_awaited_once()
        assert "ncaab_dvp" in result

    @pytest.mark.asyncio
    async def test_dvp_failure_is_non_fatal(self, orchestrator):
        orchestrator.dvp_agent.execute = AsyncMock(side_effect=RuntimeError("nba_api down"))
        result = await orchestrator.execute_full_analysis({
            "sport": "basketball_nba",
            "teams": [],
        })
        # Should not raise; dvp key should be None
        assert result.get("dvp") is None

    @pytest.mark.asyncio
    async def test_ncaab_dvp_failure_is_non_fatal(self, orchestrator):
        orchestrator.ncaab_dvp_agent.execute = AsyncMock(
            side_effect=RuntimeError("odds API down")
        )
        result = await orchestrator.execute_full_analysis({
            "sport": "basketball_ncaab",
            "teams": [],
        })
        assert result.get("ncaab_dvp") is None

    @pytest.mark.asyncio
    async def test_no_value_bets_skips_expert_agent(self, orchestrator):
        orchestrator.odds_agent.execute = AsyncMock(
            return_value={"sport": "nba", "value_bets": []}
        )
        result = await orchestrator.execute_full_analysis({"sport": "nba", "teams": []})
        orchestrator.expert_agent.execute.assert_not_awaited()
        assert "expert_recommendation" not in result

    @pytest.mark.asyncio
    async def test_odds_failure_propagates(self, orchestrator):
        orchestrator.odds_agent.execute = AsyncMock(
            side_effect=RuntimeError("fatal odds failure")
        )
        with pytest.raises(RuntimeError):
            await orchestrator.execute_full_analysis({"sport": "nba", "teams": []})


# ---------------------------------------------------------------------------
# get_agent_status
# ---------------------------------------------------------------------------

class TestGetAgentStatus:
    @pytest.mark.asyncio
    async def test_returns_dict_with_orchestrator_key(self, orchestrator):
        status = await orchestrator.get_agent_status()
        assert status["orchestrator"] == "active"

    @pytest.mark.asyncio
    async def test_returns_all_agent_statuses(self, orchestrator):
        status = await orchestrator.get_agent_status()
        for key in ("odds", "analysis", "twitter", "expert", "dvp", "ncaab_dvp"):
            assert key in status["agents"]


# ---------------------------------------------------------------------------
# learn_from_outcome
# ---------------------------------------------------------------------------

class TestLearnFromOutcome:
    @pytest.mark.asyncio
    async def test_does_not_raise(self, orchestrator):
        # Basic smoke test — outcome learning should complete without errors
        await orchestrator.learn_from_outcome(
            analysis_id="test_001",
            actual_outcome={"result": "won"},
            predictions={"analysis": [{"agent": "AnalysisAgent", "pick": "home"}]},
        )
