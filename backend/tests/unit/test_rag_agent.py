"""
Unit tests for RAGAgent.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rag_agent():
    """Create a RAGAgent instance with mocked dependencies."""
    with patch("app.agents.rag_agent.RAGAgent._initialize", new_callable=AsyncMock):
        from app.agents.rag_agent import RAGAgent
        agent = RAGAgent()
        agent._initialized = True
        # Mock vector store
        agent._vector_store = MagicMock()
        agent._vector_store.search_similar_scenarios = MagicMock(return_value=[
            {"id": "game_1", "text": "Lakers vs Celtics high-scoring game", "score": 0.85},
            {"id": "game_2", "text": "Bucks defensive masterclass", "score": 0.72},
        ])
        agent._vector_store.store_scenario = MagicMock()
        # Mock redis
        agent._redis = MagicMock()
        agent._redis.keys = MagicMock(return_value=[])
        agent._redis.set = MagicMock()
        agent._redis.get = MagicMock(return_value=None)
        return agent


# ---------------------------------------------------------------------------
# Test Initialization
# ---------------------------------------------------------------------------

class TestInitialisation:
    def test_name_is_rag_agent(self, rag_agent):
        assert rag_agent.name == "RAGAgent"

    def test_history_starts_empty(self, rag_agent):
        assert rag_agent.history == []

    def test_mistakes_starts_empty(self, rag_agent):
        assert rag_agent.mistakes == []


# ---------------------------------------------------------------------------
# Test Hybrid Search
# ---------------------------------------------------------------------------

class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, rag_agent):
        result = await rag_agent.execute({"type": "search", "query": "Lakers points over"})
        assert result["status"] == "success"
        assert "results" in result
        assert result["search_method"] == "hybrid"

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self, rag_agent):
        result = await rag_agent.execute({"type": "search", "query": ""})
        assert result["status"] == "error"
        assert "empty" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_search_records_execution(self, rag_agent):
        await rag_agent.execute({"type": "search", "query": "test query"})
        assert len(rag_agent.history) == 1

    @pytest.mark.asyncio
    async def test_search_with_top_k(self, rag_agent):
        result = await rag_agent.execute({
            "type": "search",
            "query": "rebounds over",
            "top_k": 3,
        })
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Test Document Storage
# ---------------------------------------------------------------------------

class TestDocumentStorage:
    @pytest.mark.asyncio
    async def test_store_documents(self, rag_agent):
        result = await rag_agent.execute({
            "type": "store",
            "documents": [
                {"id": "doc_1", "text": "Game analysis document", "metadata": {"sport": "nba"}},
            ],
        })
        assert result["status"] == "success"
        assert result["stored"] == 1

    @pytest.mark.asyncio
    async def test_store_empty_documents(self, rag_agent):
        result = await rag_agent.execute({"type": "store", "documents": []})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_chunk_and_store(self, rag_agent):
        long_text = " ".join(["word"] * 1000)
        result = await rag_agent.execute({
            "type": "chunk_and_store",
            "documents": [
                {"id": "long_doc", "text": long_text, "metadata": {}},
            ],
        })
        assert result["status"] == "success"
        assert result["chunks_stored"] > 1


# ---------------------------------------------------------------------------
# Test Health Check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self, rag_agent):
        result = await rag_agent.execute({"type": "health"})
        assert result["status"] == "healthy"
        assert result["vector_store"] is True
        assert result["redis"] is True

    @pytest.mark.asyncio
    async def test_health_degraded(self, rag_agent):
        rag_agent._initialized = False
        result = await rag_agent.execute({"type": "health"})
        assert result["status"] == "degraded"


# ---------------------------------------------------------------------------
# Test Utilities
# ---------------------------------------------------------------------------

class TestUtilities:
    def test_tokenize_removes_stop_words(self, rag_agent):
        tokens = rag_agent._tokenize("the quick brown fox jumps over the lazy dog")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "fox" in tokens
        assert "brown" in tokens

    def test_chunk_text_short(self, rag_agent):
        chunks = rag_agent._chunk_text("short text")
        assert len(chunks) == 1
        assert chunks[0] == "short text"

    def test_chunk_text_long(self, rag_agent):
        long_text = " ".join(["word"] * 1000)
        chunks = rag_agent._chunk_text(long_text)
        assert len(chunks) > 1

    def test_chunk_text_empty(self, rag_agent):
        chunks = rag_agent._chunk_text("")
        assert chunks == []

    def test_fuse_results_deduplicates(self, rag_agent):
        semantic = [{"id": "a", "text": "doc a", "score": 0.9, "metadata": {}}]
        keyword = [{"id": "a", "text": "doc a", "score": 0.8, "metadata": {}}]
        fused = rag_agent._fuse_results(semantic, keyword)
        assert len(fused) == 1
        assert "semantic" in fused[0]["sources"]
        assert "keyword" in fused[0]["sources"]

    def test_rerank_empty(self, rag_agent):
        result = rag_agent._rerank("test query", [])
        assert result == []


# ---------------------------------------------------------------------------
# Test Error Handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_unknown_task_type(self, rag_agent):
        result = await rag_agent.execute({"type": "invalid_type"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_vector_store_failure(self, rag_agent):
        rag_agent._vector_store.search_similar_scenarios.side_effect = Exception("Connection failed")
        result = await rag_agent.execute({"type": "search", "query": "test"})
        # Should still succeed (graceful degradation) with empty results from semantic
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_learn_from_mistake(self, rag_agent):
        await rag_agent.learn_from_mistake({
            "type": "low_relevance",
            "query": "test query",
        })
        assert len(rag_agent.mistakes) == 1
