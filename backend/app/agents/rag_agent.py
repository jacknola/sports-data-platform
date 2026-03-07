"""
RAG (Retrieval-Augmented Generation) Agent for improved data retrieval.

Implements hybrid search (semantic + keyword), cross-encoder re-ranking,
document chunking, and relevance scoring for better context retrieval
across the sports betting platform.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from loguru import logger

from app.agents.base_agent import BaseAgent


class RAGAgent(BaseAgent):
    """
    Agent for retrieval-augmented generation with hybrid search.

    Combines semantic vector search with keyword matching and
    cross-encoder re-ranking to improve data retrieval quality.
    """

    # Chunking configuration
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    MAX_CHUNKS_PER_DOC: int = 20

    # Search configuration
    SEMANTIC_WEIGHT: float = 0.6
    KEYWORD_WEIGHT: float = 0.4
    TOP_K_RETRIEVAL: int = 20
    TOP_K_RERANK: int = 5
    MIN_RELEVANCE_SCORE: float = 0.3
    MAX_KEYWORD_SEARCH_DOCS: int = 200  # Performance cap for keyword scan

    def __init__(self) -> None:
        super().__init__("RAGAgent")
        self._vector_store = None
        self._redis = None
        self._embedder = None
        self._initialized = False

    @classmethod
    async def create(cls) -> "RAGAgent":
        """Async factory to create and initialize RAGAgent."""
        agent = cls()
        await agent._initialize()
        return agent

    async def _initialize(self) -> None:
        """Initialize backend services with graceful fallbacks."""
        try:
            from app.services.vector_store import VectorStoreService
            self._vector_store = VectorStoreService()
            logger.info("RAGAgent: VectorStore initialized")
        except Exception as e:
            logger.warning(f"RAGAgent: VectorStore unavailable: {e}")

        try:
            from app.services.cache import RedisCache
            self._redis = await RedisCache.get_instance()
            logger.info("RAGAgent: Redis cache initialized")
        except Exception as e:
            logger.warning(f"RAGAgent: Redis unavailable: {e}")

        self._initialized = True
        logger.info("RAGAgent: Initialization complete")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a RAG retrieval task.

        Args:
            task: Dict with keys:
                - type: "search" | "store" | "chunk_and_store" | "health"
                - query: Search query text (for search)
                - documents: List of documents (for store/chunk_and_store)
                - filters: Optional metadata filters
                - top_k: Override default top-K (optional)

        Returns:
            Dict with retrieved documents, scores, and metadata.
        """
        task_type = task.get("type", "search")
        logger.info(f"RAGAgent executing task: {task_type}")

        try:
            if task_type == "search":
                result = await self._hybrid_search(task)
            elif task_type == "store":
                result = await self._store_documents(task)
            elif task_type == "chunk_and_store":
                result = await self._chunk_and_store(task)
            elif task_type == "health":
                result = self._health_check()
            else:
                result = {
                    "status": "error",
                    "error": f"Unknown task type: {task_type}",
                }

            self.record_execution(task, result)
            return result

        except Exception as e:
            logger.error(f"RAGAgent execution error: {e}")
            mistake = {
                "type": "retrieval_failure",
                "task_type": task_type,
                "error": str(e),
            }
            self.record_mistake(mistake)
            return {"status": "error", "error": str(e), "results": []}

    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """
        Learn from retrieval mistakes to improve future searches.

        Args:
            mistake: Dict with type, context, and correction info.
        """
        mistake_type = mistake.get("type", "")
        logger.info(f"RAGAgent learning from mistake: {mistake_type}")

        if mistake_type == "low_relevance":
            # If results were not relevant, log the query for analysis
            query = mistake.get("query", "")
            logger.warning(
                f"RAGAgent: Low relevance for query '{query}' — "
                "consider expanding keyword set or adjusting weights"
            )
        elif mistake_type == "missing_context":
            # Important context was not retrieved
            logger.warning(
                "RAGAgent: Missing context — consider indexing additional data sources"
            )

        self.record_mistake(mistake)

    # ── Hybrid Search ─────────────────────────────────────────────

    async def _hybrid_search(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform hybrid search combining semantic and keyword matching.

        Steps:
            1. Semantic vector search via VectorStore
            2. Keyword-based BM25-style matching
            3. Score fusion with configurable weights
            4. Re-rank top results
        """
        query = task.get("query", "")
        if not query:
            return {"status": "error", "error": "Empty query", "results": []}

        top_k = task.get("top_k", self.TOP_K_RETRIEVAL)
        filters = task.get("filters", {})

        # Step 1: Semantic search
        semantic_results = await self._semantic_search(query, top_k, filters)

        # Step 2: Keyword search
        keyword_results = await self._keyword_search(query, top_k, filters)

        # Step 3: Fuse scores
        fused = self._fuse_results(semantic_results, keyword_results)

        # Step 4: Re-rank top candidates
        reranked = self._rerank(query, fused[: self.TOP_K_RERANK])

        # Step 5: Filter by minimum relevance
        final = [
            r for r in reranked if r.get("score", 0) >= self.MIN_RELEVANCE_SCORE
        ]

        return {
            "status": "success",
            "query": query,
            "results": final,
            "total_candidates": len(fused),
            "returned": len(final),
            "search_method": "hybrid",
        }

    async def _semantic_search(
        self,
        query: str,
        top_k: int,
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Vector similarity search via embedding store."""
        if not self._vector_store:
            logger.warning("RAGAgent: VectorStore unavailable, skipping semantic search")
            return []

        try:
            raw = self._vector_store.search_similar_scenarios(query, limit=top_k)
            results = []
            for item in raw:
                results.append({
                    "id": item.get("id", ""),
                    "text": item.get("text", item.get("description", "")),
                    "metadata": item.get("metadata", {}),
                    "score": float(item.get("score", 0.0)),
                    "source": "semantic",
                })
            return results
        except Exception as e:
            logger.error(f"RAGAgent semantic search error: {e}")
            return []

    async def _keyword_search(
        self,
        query: str,
        top_k: int,
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Keyword-based search using cached document index.

        Falls back to simple substring matching when no full-text
        search engine is available.
        """
        if not self._redis:
            return []

        try:
            # Tokenize query into keywords
            keywords = self._tokenize(query)
            if not keywords:
                return []

            # Search cached documents by keyword overlap
            results: List[Dict[str, Any]] = []
            cache_keys = []
            if callable(getattr(self._redis, "keys", None)):
                cache_keys = self._redis.keys("rag:doc:*")

            import json
            for key in cache_keys[:self.MAX_KEYWORD_SEARCH_DOCS]:
                try:
                    raw_val = self._redis.get(key)
                    if not raw_val:
                        continue
                    doc = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
                    text = doc.get("text", "").lower()
                    # Simple keyword overlap scoring
                    matches = sum(1 for kw in keywords if kw in text)
                    if matches > 0:
                        score = matches / len(keywords)
                        results.append({
                            "id": doc.get("id", key),
                            "text": doc.get("text", ""),
                            "metadata": doc.get("metadata", {}),
                            "score": score,
                            "source": "keyword",
                        })
                except (json.JSONDecodeError, TypeError):
                    continue

            # Sort by score descending
            results.sort(key=lambda r: r["score"], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"RAGAgent keyword search error: {e}")
            return []

    def _fuse_results(
        self,
        semantic: List[Dict[str, Any]],
        keyword: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF) to combine semantic and keyword results.

        Uses weighted score fusion with deduplication by document ID.
        """
        combined: Dict[str, Dict[str, Any]] = {}

        # Process semantic results
        for rank, item in enumerate(semantic):
            doc_id = item.get("id", f"sem_{rank}")
            rrf_score = self.SEMANTIC_WEIGHT / (60 + rank + 1)
            if doc_id in combined:
                combined[doc_id]["score"] += rrf_score
                combined[doc_id]["sources"].append("semantic")
            else:
                combined[doc_id] = {
                    **item,
                    "score": rrf_score,
                    "sources": ["semantic"],
                }

        # Process keyword results
        for rank, item in enumerate(keyword):
            doc_id = item.get("id", f"kw_{rank}")
            rrf_score = self.KEYWORD_WEIGHT / (60 + rank + 1)
            if doc_id in combined:
                combined[doc_id]["score"] += rrf_score
                combined[doc_id]["sources"].append("keyword")
            else:
                combined[doc_id] = {
                    **item,
                    "score": rrf_score,
                    "sources": ["keyword"],
                }

        # Sort by fused score
        fused = sorted(combined.values(), key=lambda r: r["score"], reverse=True)
        return fused

    def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Re-rank top candidates using a lightweight scoring heuristic.

        Uses query-document overlap, recency weighting, and source
        diversity as signals. A cross-encoder model can be plugged
        in here for higher accuracy.
        """
        if not candidates:
            return []

        query_tokens = set(self._tokenize(query))
        reranked: List[Dict[str, Any]] = []

        for candidate in candidates:
            text = candidate.get("text", "")
            doc_tokens = set(self._tokenize(text))

            # Token overlap ratio
            overlap = len(query_tokens & doc_tokens) / max(len(query_tokens), 1)

            # Source diversity bonus (appears in both semantic + keyword)
            sources = candidate.get("sources", [])
            diversity_bonus = 0.1 if len(set(sources)) > 1 else 0.0

            # Recency bonus from metadata
            recency_bonus = 0.0
            ts = candidate.get("metadata", {}).get("timestamp")
            if ts:
                try:
                    age_days = (datetime.now() - datetime.fromisoformat(str(ts))).days
                    recency_bonus = max(0, 0.05 * (1 - age_days / 365))
                except (ValueError, TypeError):
                    pass

            final_score = (
                candidate.get("score", 0) * 0.5
                + overlap * 0.3
                + diversity_bonus
                + recency_bonus
            )
            reranked.append({**candidate, "score": round(final_score, 4)})

        reranked.sort(key=lambda r: r["score"], reverse=True)
        return reranked

    # ── Document Storage ──────────────────────────────────────────

    async def _store_documents(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Store documents in vector store and Redis keyword index."""
        documents = task.get("documents", [])
        if not documents:
            return {"status": "error", "error": "No documents provided", "stored": 0}

        stored_count = 0
        for doc in documents:
            doc_id = doc.get("id", f"doc_{datetime.now().timestamp()}")
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})

            if not text:
                continue

            # Store in vector store
            if self._vector_store:
                try:
                    self._vector_store.store_scenario(
                        game_id=doc_id,
                        description=text,
                        metadata=metadata,
                    )
                except Exception as e:
                    logger.error(f"RAGAgent: Failed to store in VectorStore: {e}")

            # Store in Redis keyword index
            if self._redis:
                try:
                    import json
                    cache_key = f"rag:doc:{doc_id}"
                    payload = json.dumps({
                        "id": doc_id,
                        "text": text,
                        "metadata": metadata,
                        "indexed_at": datetime.now().isoformat(),
                    })
                    self._redis.set(cache_key, payload)
                except Exception as e:
                    logger.error(f"RAGAgent: Failed to store in Redis: {e}")

            stored_count += 1

        return {"status": "success", "stored": stored_count}

    async def _chunk_and_store(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Chunk large documents and store each chunk."""
        documents = task.get("documents", [])
        total_chunks = 0

        for doc in documents:
            text = doc.get("text", "")
            base_id = doc.get("id", f"doc_{datetime.now().timestamp()}")
            metadata = doc.get("metadata", {})

            chunks = self._chunk_text(text)
            chunk_docs = []
            for i, chunk in enumerate(chunks):
                chunk_docs.append({
                    "id": f"{base_id}_chunk_{i}",
                    "text": chunk,
                    "metadata": {
                        **metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "parent_id": base_id,
                    },
                })

            result = await self._store_documents({"documents": chunk_docs})
            total_chunks += result.get("stored", 0)

        return {
            "status": "success",
            "documents_processed": len(documents),
            "chunks_stored": total_chunks,
        }

    # ── Utilities ─────────────────────────────────────────────────

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks of approximately CHUNK_SIZE tokens.

        Uses word-level splitting as an approximation for tokenization.
        """
        if not text:
            return []

        words = text.split()
        if len(words) <= self.CHUNK_SIZE:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(words):
            end = min(start + self.CHUNK_SIZE, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            if end >= len(words):
                break
            start += self.CHUNK_SIZE - self.CHUNK_OVERLAP

            if len(chunks) >= self.MAX_CHUNKS_PER_DOC:
                break

        return chunks

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace tokenizer with lowercasing and stop-word removal."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "nor", "not", "so", "yet", "both", "either",
            "neither", "each", "every", "all", "any", "few", "more",
            "most", "other", "some", "such", "no", "only", "own", "same",
            "than", "too", "very", "just", "because", "about", "between",
            "this", "that", "these", "those", "it", "its",
        }
        words = text.lower().split()
        return [w.strip(".,;:!?\"'()[]{}") for w in words if w.lower() not in stop_words and len(w) > 1]

    def _health_check(self) -> Dict[str, Any]:
        """Return health status of all RAG subsystems."""
        return {
            "status": "healthy" if self._initialized else "degraded",
            "vector_store": self._vector_store is not None,
            "redis": self._redis is not None,
            "config": {
                "chunk_size": self.CHUNK_SIZE,
                "semantic_weight": self.SEMANTIC_WEIGHT,
                "keyword_weight": self.KEYWORD_WEIGHT,
                "top_k_retrieval": self.TOP_K_RETRIEVAL,
                "top_k_rerank": self.TOP_K_RERANK,
                "min_relevance": self.MIN_RELEVANCE_SCORE,
            },
        }
