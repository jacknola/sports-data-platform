"""
Unit tests for app/agents/ncaab_dvp_agent.py

Mirrors test_dvp_agent.py in style.
NCAABDvPAnalyzer is mocked so no real API calls or slate files are needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_ANALYSIS_RESULT = {
    "projections": [
        {"team": "Duke", "implied_total": 78.5, "efficiency_edge": "HIGH VALUE OVER"},
        {"team": "UNC", "implied_total": 74.0, "efficiency_edge": "LEAN UNDER"},
    ],
    "count": 2,
    "high_value_count": 1,
}

HIGH_VALUE_RESULT = {
    "projections": [
        {"team": "Duke", "implied_total": 78.5, "efficiency_edge": "HIGH VALUE OVER"},
    ],
    "count": 1,
    "high_value_count": 1,
}

TOTALS_RESULT = {
    "implied_totals": {"Duke": 78.5, "UNC": 74.0},
}


@pytest.fixture
def mock_analyzer():
    """Return a mock NCAABDvPAnalyzer with async methods."""
    analyzer = MagicMock()
    analyzer.load_slate = MagicMock()
    analyzer.load_slate_from_odds_api = AsyncMock()
    analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
    analyzer.get_high_value_plays = AsyncMock(return_value=[
        {"team": "Duke", "implied_total": 78.5, "efficiency_edge": "HIGH VALUE OVER"},
    ])
    analyzer.compute_all_implied_totals = MagicMock(
        return_value={"Duke": 78.5, "UNC": 74.0}
    )
    return analyzer


@pytest.fixture
def agent(mock_analyzer):
    """NCAABDvPAgent with the analyzer replaced by mock_analyzer."""
    with patch("app.agents.ncaab_dvp_agent.NCAABDvPAnalyzer", return_value=mock_analyzer):
        from app.agents.ncaab_dvp_agent import NCAABDvPAgent
        return NCAABDvPAgent()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInitialisation:
    def test_name_is_ncaab_dvp_agent(self, agent):
        assert agent.name == "ncaab_dvp_agent"

    def test_history_starts_empty(self, agent):
        assert agent.history == []

    def test_mistakes_starts_empty(self, agent):
        assert agent.mistakes == []


# ---------------------------------------------------------------------------
# execute – full_analysis
# ---------------------------------------------------------------------------

class TestExecuteFullAnalysis:
    @pytest.mark.asyncio
    async def test_returns_dict(self, agent, mock_analyzer):
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        result = await agent.execute({"type": "full_analysis"})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_result_has_count(self, agent, mock_analyzer):
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        result = await agent.execute({"type": "full_analysis"})
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_execution_recorded_in_history(self, agent, mock_analyzer):
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        await agent.execute({"type": "full_analysis"})
        assert len(agent.history) == 1

    @pytest.mark.asyncio
    async def test_loads_slate_from_odds_api_when_no_slate_data(self, agent, mock_analyzer):
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        await agent.execute({"type": "full_analysis"})
        mock_analyzer.load_slate_from_odds_api.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_provided_slate_data(self, agent, mock_analyzer):
        slate_data = {"date": "2026-03-01", "games": []}
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        await agent.execute({"type": "full_analysis", "slate_data": slate_data})
        # When slate_data is provided, odds API should NOT be called
        mock_analyzer.load_slate_from_odds_api.assert_not_awaited()


# ---------------------------------------------------------------------------
# execute – high_value_only
# ---------------------------------------------------------------------------

class TestExecuteHighValueOnly:
    @pytest.mark.asyncio
    async def test_returns_high_value_plays(self, agent, mock_analyzer):
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        mock_analyzer.get_high_value_plays = AsyncMock(return_value=[
            {"team": "Duke", "efficiency_edge": "HIGH VALUE OVER"}
        ])
        result = await agent.execute({"type": "high_value_only"})
        projections = result.get("projections", [])
        assert all("HIGH VALUE" in p["efficiency_edge"] for p in projections)

    @pytest.mark.asyncio
    async def test_count_reflects_high_value_only(self, agent, mock_analyzer):
        hv = [{"team": "Duke", "efficiency_edge": "HIGH VALUE OVER"}]
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        mock_analyzer.get_high_value_plays = AsyncMock(return_value=hv)
        result = await agent.execute({"type": "high_value_only"})
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# execute – implied_totals
# ---------------------------------------------------------------------------

class TestExecuteImpliedTotals:
    @pytest.mark.asyncio
    async def test_returns_implied_totals_dict(self, agent, mock_analyzer):
        slate_data = {
            "date": "2026-03-01",
            "games": [{"home": "Duke", "away": "UNC", "spread": -3.5, "over_under": 152.5}],
        }
        result = await agent.execute({"type": "implied_totals", "slate_data": slate_data})
        assert "implied_totals" in result

    @pytest.mark.asyncio
    async def test_implied_totals_calls_analyzer(self, agent, mock_analyzer):
        slate_data = {"date": "2026-03-01", "games": []}
        await agent.execute({"type": "implied_totals", "slate_data": slate_data})
        mock_analyzer.compute_all_implied_totals.assert_called_once()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_analyzer_error_returns_error_dict(self, agent, mock_analyzer):
        mock_analyzer.load_slate_from_odds_api = AsyncMock(
            side_effect=Exception("odds API down")
        )
        mock_analyzer.run_analysis = AsyncMock(
            side_effect=RuntimeError("analyzer failed")
        )
        result = await agent.execute({"type": "full_analysis"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_recorded_as_mistake(self, agent, mock_analyzer):
        mock_analyzer.run_analysis = AsyncMock(side_effect=RuntimeError("boom"))
        await agent.execute({"type": "full_analysis"})
        assert len(agent.mistakes) == 1

    @pytest.mark.asyncio
    async def test_error_dict_contains_task_type(self, agent, mock_analyzer):
        mock_analyzer.run_analysis = AsyncMock(side_effect=RuntimeError("boom"))
        result = await agent.execute({"type": "full_analysis"})
        assert result.get("task_type") == "full_analysis"

    @pytest.mark.asyncio
    async def test_odds_api_fallback_to_file_slate(self, agent, mock_analyzer):
        # When odds API fails, agent should fall back to file slate
        mock_analyzer.load_slate_from_odds_api = AsyncMock(
            side_effect=Exception("API down")
        )
        mock_analyzer.run_analysis = AsyncMock(return_value=FULL_ANALYSIS_RESULT)
        result = await agent.execute({"type": "full_analysis"})
        mock_analyzer.load_slate.assert_called_once()
        assert "error" not in result


# ---------------------------------------------------------------------------
# learn_from_mistake
# ---------------------------------------------------------------------------

class TestLearnFromMistake:
    @pytest.mark.asyncio
    async def test_records_mistake(self, agent):
        mistake = {"type": "ncaab_dvp_analysis_error", "task_type": "full_analysis"}
        await agent.learn_from_mistake(mistake)
        assert len(agent.mistakes) == 1

    @pytest.mark.asyncio
    async def test_multiple_mistakes_accumulated(self, agent):
        for i in range(3):
            await agent.learn_from_mistake({"type": f"error_{i}", "task_type": "x"})
        assert len(agent.mistakes) == 3
