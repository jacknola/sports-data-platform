"""
Unit tests for ExpertAgent RAG enhancement.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.agents.expert_agent import ExpertAgent

@pytest.mark.asyncio
async def test_expert_agent_execution_with_rag():
    # Setup mocks
    thinking_mock = AsyncMock()
    thinking_mock.research_topic.return_value = "NotebookLM findings"
    thinking_mock.decide_if_bet.return_value = {"should_bet": True, "rationale": "High confidence"}
    
    similarity_mock = MagicMock()
    similarity_mock.find_similar_games.return_value = [
        {"game_id": "HIST_1", "outcome": "covered"}
    ]
    
    with patch("app.agents.expert_agent.SequentialThinkingService", return_value=thinking_mock), \
         patch("app.agents.expert_agent.SimilaritySearchService", return_value=similarity_mock):
        
        agent = ExpertAgent()
        task = {
            "bet_analysis": {
                "sport": "nba",
                "market": "spread",
                "teams": ["LAL", "GSW"]
            }
        }
        
        result = await agent.execute(task)
        
        # Verify
        assert result["status"] == "success"
        similarity_mock.find_similar_games.assert_called_once()
        # Verify bet_analysis context was enriched
        call_args = thinking_mock.decide_if_bet.call_args[0][0]
        assert "historical_analogs" in call_args
        assert len(call_args["historical_analogs"]) == 1
