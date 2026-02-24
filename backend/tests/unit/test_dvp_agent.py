"""
Unit tests for DvPAgent (app/agents/dvp_agent.py).

The NBADvPAnalyzer is patched throughout so no NBA API calls are made.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from app.agents.dvp_agent import DvPAgent


@pytest.fixture
def agent():
    return DvPAgent()


@pytest.fixture
def single_row_df():
    """A one-row DataFrame representing a HIGH VALUE OVER projection."""
    return pd.DataFrame([{
        "Player": "LeBron James",
        "Position": "SF",
        "Team": "LAL",
        "Opponent": "BOS",
        "Stat_Category": "PTS",
        "Season_Avg": 25.0,
        "Projected_Line": 28.5,
        "Sportsbook_Line": 25.0,
        "DvP_Advantage_%": 14.0,
        "Recommendation": "HIGH VALUE OVER",
    }])


@pytest.fixture
def multi_row_df(single_row_df):
    """Two-row DataFrame: one HIGH VALUE, one LEAN OVER."""
    lean_row = single_row_df.copy()
    lean_row["Recommendation"] = "LEAN OVER"
    lean_row["Player"] = "Anthony Davis"
    lean_row["DvP_Advantage_%"] = 7.0
    return pd.concat([single_row_df, lean_row], ignore_index=True)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInitialisation:
    def test_name_is_dvp_agent(self, agent):
        assert agent.name == "dvp_agent"

    def test_analyzer_created(self, agent):
        assert agent.analyzer.__class__.__name__ == "NBADvPAnalyzer"


# ---------------------------------------------------------------------------
# full_analysis dispatch
# ---------------------------------------------------------------------------

class TestFullAnalysisDispatch:
    @pytest.mark.asyncio
    async def test_returns_projections_key(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            result = await agent.execute({"type": "full_analysis"})
        assert "projections" in result

    @pytest.mark.asyncio
    async def test_count_matches_dataframe_length(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            result = await agent.execute({"type": "full_analysis"})
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_high_value_count_correct(self, agent, multi_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=multi_row_df):
            result = await agent.execute({"type": "full_analysis"})
        assert result["high_value_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_dataframe_returns_zero_count(self, agent):
        with patch.object(agent.analyzer, "run_analysis", return_value=pd.DataFrame()):
            result = await agent.execute({"type": "full_analysis"})
        assert result["count"] == 0
        assert result["projections"] == []

    @pytest.mark.asyncio
    async def test_default_type_is_full_analysis(self, agent, single_row_df):
        """Task with no 'type' key should default to full_analysis."""
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            result = await agent.execute({})
        assert "projections" in result

    @pytest.mark.asyncio
    async def test_num_recent_passed_to_analyzer(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df) as mock_run:
            await agent.execute({"type": "full_analysis", "num_recent": 10})
        mock_run.assert_called_once_with(
            slate_data=None, num_recent_games=10, export_csv=None
        )

    @pytest.mark.asyncio
    async def test_slate_data_forwarded_to_analyzer(self, agent, single_row_df):
        slate = {"games": []}
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df) as mock_run:
            await agent.execute({"type": "full_analysis", "slate_data": slate})
        mock_run.assert_called_once_with(
            slate_data=slate, num_recent_games=15, export_csv=None
        )


# ---------------------------------------------------------------------------
# high_value_only dispatch
# ---------------------------------------------------------------------------

class TestHighValueOnlyDispatch:
    @pytest.mark.asyncio
    async def test_calls_get_high_value_plays(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df), \
             patch.object(agent.analyzer, "get_high_value_plays", return_value=single_row_df) as mock_hv:
            await agent.execute({"type": "high_value_only"})
        mock_hv.assert_called_once()

    @pytest.mark.asyncio
    async def test_result_has_task_type_key(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df), \
             patch.object(agent.analyzer, "get_high_value_plays", return_value=single_row_df):
            result = await agent.execute({"type": "high_value_only"})
        assert result["task_type"] == "high_value_only"


# ---------------------------------------------------------------------------
# implied_totals dispatch
# ---------------------------------------------------------------------------

class TestImpliedTotalsDispatch:
    @pytest.mark.asyncio
    async def test_returns_implied_totals_key(self, agent):
        totals = {"LAL": 112.75, "BOS": 107.25}
        with patch.object(agent.analyzer, "load_slate"), \
             patch.object(agent.analyzer, "compute_all_implied_totals", return_value=totals):
            result = await agent.execute({"type": "implied_totals"})
        assert result["implied_totals"] == totals

    @pytest.mark.asyncio
    async def test_load_slate_called_with_slate_data(self, agent):
        slate = {"games": []}
        with patch.object(agent.analyzer, "load_slate") as mock_load, \
             patch.object(agent.analyzer, "compute_all_implied_totals", return_value={}):
            await agent.execute({"type": "implied_totals", "slate_data": slate})
        mock_load.assert_called_once_with(slate)


# ---------------------------------------------------------------------------
# single_player dispatch
# ---------------------------------------------------------------------------

class TestSinglePlayerDispatch:
    @pytest.mark.asyncio
    async def test_player_found_returns_row_dict(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            result = await agent.execute({
                "type": "single_player",
                "player_name": "LeBron James",
                "stat_category": "PTS",
            })
        assert result.get("Player") == "LeBron James"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_player_not_found_returns_error(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            result = await agent.execute({
                "type": "single_player",
                "player_name": "Unknown Player",
                "stat_category": "PTS",
            })
        assert "error" in result

    @pytest.mark.asyncio
    async def test_wrong_stat_category_returns_error(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            result = await agent.execute({
                "type": "single_player",
                "player_name": "LeBron James",
                "stat_category": "REB",  # only PTS exists in fixture
            })
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_dataframe_returns_error(self, agent):
        with patch.object(agent.analyzer, "run_analysis", return_value=pd.DataFrame()):
            result = await agent.execute({
                "type": "single_player",
                "player_name": "LeBron James",
                "stat_category": "PTS",
            })
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_includes_available_players(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            result = await agent.execute({
                "type": "single_player",
                "player_name": "Unknown",
                "stat_category": "PTS",
            })
        assert "available_players" in result


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_exception_returns_error_dict(self, agent):
        with patch.object(agent.analyzer, "run_analysis", side_effect=RuntimeError("API down")):
            result = await agent.execute({"type": "full_analysis"})
        assert "error" in result
        assert "API down" in result["error"]

    @pytest.mark.asyncio
    async def test_exception_records_mistake(self, agent):
        with patch.object(agent.analyzer, "run_analysis", side_effect=RuntimeError("fail")):
            await agent.execute({"type": "full_analysis"})
        assert len(agent.mistakes) == 1

    @pytest.mark.asyncio
    async def test_exception_does_not_record_to_history(self, agent):
        with patch.object(agent.analyzer, "run_analysis", side_effect=RuntimeError("fail")):
            await agent.execute({"type": "full_analysis"})
        assert len(agent.history) == 0

    @pytest.mark.asyncio
    async def test_successful_execution_recorded_in_history(self, agent, single_row_df):
        with patch.object(agent.analyzer, "run_analysis", return_value=single_row_df):
            await agent.execute({"type": "full_analysis"})
        assert len(agent.history) == 1
        assert len(agent.mistakes) == 0

    @pytest.mark.asyncio
    async def test_error_result_includes_task_type(self, agent):
        with patch.object(agent.analyzer, "run_analysis", side_effect=ValueError("bad data")):
            result = await agent.execute({"type": "full_analysis"})
        assert result.get("task_type") == "full_analysis"


# ---------------------------------------------------------------------------
# learn_from_mistake
# ---------------------------------------------------------------------------

class TestLearnFromMistake:
    @pytest.mark.asyncio
    async def test_stale_data_refreshes_dvp(self, agent):
        with patch.object(agent.analyzer, "fetch_team_dvp", return_value={}) as mock_dvp, \
             patch.object(agent.analyzer, "fetch_team_pace", return_value={}):
            await agent.learn_from_mistake({"type": "stale_data"})
        mock_dvp.assert_called_once()

    @pytest.mark.asyncio
    async def test_stale_data_refreshes_pace(self, agent):
        with patch.object(agent.analyzer, "fetch_team_dvp", return_value={}), \
             patch.object(agent.analyzer, "fetch_team_pace", return_value={}) as mock_pace:
            await agent.learn_from_mistake({"type": "stale_data"})
        mock_pace.assert_called_once()

    @pytest.mark.asyncio
    async def test_mistake_recorded_regardless_of_type(self, agent):
        await agent.learn_from_mistake({"type": "unknown_type"})
        assert len(agent.mistakes) == 1
