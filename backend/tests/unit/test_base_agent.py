"""
Unit tests for BaseAgent (app/agents/base_agent.py).

BaseAgent is abstract, so we test through a minimal concrete subclass.
All tests are synchronous-friendly via pytest-asyncio.
"""
import pytest
from app.agents.base_agent import BaseAgent


# ---------------------------------------------------------------------------
# Minimal concrete implementation for testing the abstract base
# ---------------------------------------------------------------------------

class ConcreteAgent(BaseAgent):
    async def execute(self, task):
        return {"status": "ok", "task": task}

    async def learn_from_mistake(self, mistake):
        pass


@pytest.fixture
def agent():
    return ConcreteAgent(name="test_agent")


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInitialisation:
    def test_name_is_stored(self, agent):
        assert agent.name == "test_agent"

    def test_history_starts_empty(self, agent):
        assert agent.history == []

    def test_mistakes_starts_empty(self, agent):
        assert agent.mistakes == []

    def test_agent_id_contains_name(self, agent):
        assert "test_agent" in agent.agent_id

    def test_two_agents_have_different_ids(self):
        a1 = ConcreteAgent(name="agent_a")
        a2 = ConcreteAgent(name="agent_b")
        assert a1.agent_id != a2.agent_id


# ---------------------------------------------------------------------------
# record_execution
# ---------------------------------------------------------------------------

class TestRecordExecution:
    def test_appends_one_entry(self, agent):
        agent.record_execution({"type": "test"}, {"result": "ok"})
        assert len(agent.history) == 1

    def test_entry_contains_task(self, agent):
        task = {"type": "analyze", "data": [1, 2, 3]}
        agent.record_execution(task, {})
        assert agent.history[0]["task"] == task

    def test_entry_contains_result(self, agent):
        result = {"predictions": [0.6, 0.7]}
        agent.record_execution({}, result)
        assert agent.history[0]["result"] == result

    def test_entry_contains_agent_name(self, agent):
        agent.record_execution({}, {})
        assert agent.history[0]["agent"] == "test_agent"

    def test_entry_contains_timestamp(self, agent):
        agent.record_execution({}, {})
        assert "timestamp" in agent.history[0]

    def test_multiple_executions_all_recorded(self, agent):
        for i in range(5):
            agent.record_execution({"i": i}, {"ok": True})
        assert len(agent.history) == 5

    def test_entries_are_ordered(self, agent):
        agent.record_execution({"seq": 1}, {})
        agent.record_execution({"seq": 2}, {})
        assert agent.history[0]["task"]["seq"] == 1
        assert agent.history[1]["task"]["seq"] == 2


# ---------------------------------------------------------------------------
# record_mistake
# ---------------------------------------------------------------------------

class TestRecordMistake:
    def test_appends_one_entry(self, agent):
        agent.record_mistake({"type": "data_error"})
        assert len(agent.mistakes) == 1

    def test_agent_name_merged_in(self, agent):
        agent.record_mistake({"type": "data_error"})
        assert agent.mistakes[0]["agent"] == "test_agent"

    def test_timestamp_added(self, agent):
        agent.record_mistake({"type": "data_error"})
        assert "timestamp" in agent.mistakes[0]

    def test_original_keys_preserved(self, agent):
        agent.record_mistake({"type": "mapping_error", "player": "LeBron James"})
        assert agent.mistakes[0]["player"] == "LeBron James"
        assert agent.mistakes[0]["type"] == "mapping_error"

    def test_multiple_mistakes_accumulated(self, agent):
        for _ in range(4):
            agent.record_mistake({"type": "err"})
        assert len(agent.mistakes) == 4


# ---------------------------------------------------------------------------
# get_agent_status
# ---------------------------------------------------------------------------

class TestGetAgentStatus:
    def test_returns_all_required_keys(self, agent):
        status = agent.get_agent_status()
        for key in ["name", "id", "total_executions", "total_mistakes",
                    "mistake_rate", "recent_mistakes"]:
            assert key in status

    def test_name_matches(self, agent):
        assert agent.get_agent_status()["name"] == "test_agent"

    def test_zero_executions_zero_rate(self, agent):
        status = agent.get_agent_status()
        assert status["total_executions"] == 0
        assert status["mistake_rate"] == 0.0

    def test_mistake_rate_calculation(self, agent):
        agent.record_execution({}, {})
        agent.record_execution({}, {})
        agent.record_mistake({"type": "err"})
        status = agent.get_agent_status()
        assert status["mistake_rate"] == pytest.approx(0.5)

    def test_recent_mistakes_capped_at_five(self, agent):
        for i in range(10):
            agent.record_mistake({"type": f"err_{i}"})
        status = agent.get_agent_status()
        assert len(status["recent_mistakes"]) == 5

    def test_recent_mistakes_shows_last_five(self, agent):
        for i in range(10):
            agent.record_mistake({"type": f"err_{i}"})
        status = agent.get_agent_status()
        # The last 5 mistakes should be err_5 through err_9
        types = [m["type"] for m in status["recent_mistakes"]]
        assert "err_9" in types
        assert "err_0" not in types

    def test_fewer_than_five_mistakes_all_shown(self, agent):
        for i in range(3):
            agent.record_mistake({"type": f"err_{i}"})
        status = agent.get_agent_status()
        assert len(status["recent_mistakes"]) == 3

    def test_total_executions_count(self, agent):
        for _ in range(7):
            agent.record_execution({}, {})
        assert agent.get_agent_status()["total_executions"] == 7

    def test_total_mistakes_count(self, agent):
        for _ in range(3):
            agent.record_mistake({"type": "err"})
        assert agent.get_agent_status()["total_mistakes"] == 3


# ---------------------------------------------------------------------------
# should_use_ai
# ---------------------------------------------------------------------------

class TestShouldUseAI:
    @pytest.mark.asyncio
    async def test_high_complexity_triggers_ai(self, agent):
        assert await agent.should_use_ai({"complexity": 8}) is True

    @pytest.mark.asyncio
    async def test_complexity_at_threshold_not_triggered(self, agent):
        # complexity > 7 triggers; == 7 does not
        assert await agent.should_use_ai({"complexity": 7}) is False

    @pytest.mark.asyncio
    async def test_low_complexity_no_ai(self, agent):
        assert await agent.should_use_ai({"complexity": 3}) is False

    @pytest.mark.asyncio
    async def test_high_confidence_required_triggers_ai(self, agent):
        assert await agent.should_use_ai({"confidence_required": 0.9}) is True

    @pytest.mark.asyncio
    async def test_confidence_at_threshold_not_triggered(self, agent):
        # > 0.8 triggers; == 0.8 does not
        assert await agent.should_use_ai({"confidence_required": 0.8}) is False

    @pytest.mark.asyncio
    async def test_three_similar_mistakes_triggers_ai(self, agent):
        for _ in range(3):
            agent.record_mistake({"type": "err", "task_type": "analyze"})
        result = await agent.should_use_ai({"type": "analyze", "complexity": 1})
        assert result is True

    @pytest.mark.asyncio
    async def test_two_similar_mistakes_not_enough(self, agent):
        for _ in range(2):
            agent.record_mistake({"type": "err", "task_type": "analyze"})
        result = await agent.should_use_ai({"type": "analyze", "complexity": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_different_task_type_mistakes_not_counted(self, agent):
        for _ in range(5):
            agent.record_mistake({"type": "err", "task_type": "predict"})
        # Task type is "analyze" — none of the mistakes match
        result = await agent.should_use_ai({"type": "analyze", "complexity": 1})
        assert result is False


# ---------------------------------------------------------------------------
# _find_similar_mistakes
# ---------------------------------------------------------------------------

class TestFindSimilarMistakes:
    def test_returns_mistakes_with_matching_task_type(self, agent):
        agent.record_mistake({"type": "err", "task_type": "analyze"})
        agent.record_mistake({"type": "err", "task_type": "predict"})
        similar = agent._find_similar_mistakes({"type": "analyze"})
        assert len(similar) == 1

    def test_no_match_returns_empty_list(self, agent):
        agent.record_mistake({"type": "err", "task_type": "analyze"})
        similar = agent._find_similar_mistakes({"type": "predict"})
        assert similar == []

    def test_empty_mistakes_returns_empty_list(self, agent):
        similar = agent._find_similar_mistakes({"type": "analyze"})
        assert similar == []

    def test_multiple_matches_all_returned(self, agent):
        for _ in range(4):
            agent.record_mistake({"type": "err", "task_type": "analyze"})
        similar = agent._find_similar_mistakes({"type": "analyze"})
        assert len(similar) == 4

    def test_missing_task_type_in_task_matches_empty_task_type_in_mistakes(self, agent):
        agent.record_mistake({"type": "err", "task_type": ""})
        # task has no "type" key -> task_type=""
        similar = agent._find_similar_mistakes({})
        assert len(similar) == 1
