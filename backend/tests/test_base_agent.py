"""Tests for BaseAgent abstract class"""
import pytest
from typing import Dict, Any
from app.agents.base_agent import BaseAgent


class ConcreteAgent(BaseAgent):
    """Minimal concrete implementation for testing"""

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "task": task}

    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        self.record_mistake(mistake)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def test_agent_initializes_with_name():
    agent = ConcreteAgent("test_agent")
    assert agent.name == "test_agent"
    assert agent.agent_id.startswith("test_agent_")


def test_agent_starts_with_empty_history():
    agent = ConcreteAgent("test_agent")
    assert agent.history == []
    assert agent.mistakes == []


# ---------------------------------------------------------------------------
# record_execution
# ---------------------------------------------------------------------------

def test_record_execution_adds_to_history():
    agent = ConcreteAgent("recorder")
    task = {"type": "odds_fetch", "game_id": "123"}
    result = {"status": "ok"}
    agent.record_execution(task, result)

    assert len(agent.history) == 1
    entry = agent.history[0]
    assert entry["task"] == task
    assert entry["result"] == result
    assert entry["agent"] == "recorder"
    assert "timestamp" in entry


def test_record_execution_accumulates():
    agent = ConcreteAgent("accumulator")
    for i in range(5):
        agent.record_execution({"step": i}, {"done": True})
    assert len(agent.history) == 5


# ---------------------------------------------------------------------------
# record_mistake
# ---------------------------------------------------------------------------

def test_record_mistake_adds_to_mistakes():
    agent = ConcreteAgent("mistake_agent")
    mistake = {"type": "api_error", "message": "timeout"}
    agent.record_mistake(mistake)

    assert len(agent.mistakes) == 1
    recorded = agent.mistakes[0]
    assert recorded["type"] == "api_error"
    assert recorded["agent"] == "mistake_agent"
    assert "timestamp" in recorded


# ---------------------------------------------------------------------------
# get_agent_status
# ---------------------------------------------------------------------------

def test_get_agent_status_with_no_history():
    agent = ConcreteAgent("status_agent")
    status = agent.get_agent_status()

    assert status["name"] == "status_agent"
    assert status["total_executions"] == 0
    assert status["total_mistakes"] == 0
    assert status["mistake_rate"] == 0.0
    assert status["recent_mistakes"] == []


def test_get_agent_status_calculates_mistake_rate():
    agent = ConcreteAgent("rate_agent")
    for i in range(10):
        agent.record_execution({"step": i}, {"ok": True})
    for i in range(2):
        agent.record_mistake({"type": "error", "task_type": "test"})

    status = agent.get_agent_status()
    assert status["total_executions"] == 10
    assert status["total_mistakes"] == 2
    assert abs(status["mistake_rate"] - 0.2) < 1e-9


def test_get_agent_status_recent_mistakes_capped_at_5():
    agent = ConcreteAgent("cap_agent")
    for i in range(8):
        agent.record_mistake({"type": "error", "task_type": "x"})

    status = agent.get_agent_status()
    assert len(status["recent_mistakes"]) == 5


# ---------------------------------------------------------------------------
# should_use_ai
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_use_ai_high_complexity():
    agent = ConcreteAgent("ai_agent")
    result = await agent.should_use_ai({"complexity": 8})
    assert result is True


@pytest.mark.asyncio
async def test_should_use_ai_high_confidence_required():
    agent = ConcreteAgent("ai_agent")
    result = await agent.should_use_ai({"confidence_required": 0.9})
    assert result is True


@pytest.mark.asyncio
async def test_should_use_ai_many_similar_mistakes():
    agent = ConcreteAgent("ai_agent")
    for _ in range(3):
        agent.record_mistake({"type": "err", "task_type": "odds_fetch"})
    result = await agent.should_use_ai({"type": "odds_fetch"})
    assert result is True


@pytest.mark.asyncio
async def test_should_use_ai_returns_false_for_simple_task():
    agent = ConcreteAgent("ai_agent")
    result = await agent.should_use_ai({"type": "simple", "complexity": 3})
    assert result is False


# ---------------------------------------------------------------------------
# execute (concrete impl)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_returns_result():
    agent = ConcreteAgent("exec_agent")
    task = {"type": "test", "data": 42}
    result = await agent.execute(task)
    assert result["status"] == "ok"
    assert result["task"] == task
