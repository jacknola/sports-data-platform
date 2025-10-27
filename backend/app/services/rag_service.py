"""
Simple embedding and RAG storage using sentence-transformers and Redis for metadata.
"""
from __future__ import annotations

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from sentence_transformers import SentenceTransformer
import numpy as np

from app.services.cache import RedisCache


@dataclass
class RAGDocument:
    doc_id: str
    text: str
    metadata: Dict[str, Any]


class RAGService:
    """Lightweight RAG: embeds text, stores vectors and metadata in Redis."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)
        self._redis: Optional[RedisCache] = None

    async def init(self) -> None:
        self._redis = await RedisCache.get_instance()

    def _embed(self, texts: List[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True))

    def _vec_to_str(self, vec: np.ndarray) -> str:
        return json.dumps(vec.tolist())

    def _str_to_vec(self, s: str) -> np.ndarray:
        return np.asarray(json.loads(s))

    def _key_vec(self, doc_id: str) -> str:
        return f"rag:vec:{doc_id}"

    def _key_meta(self, doc_id: str) -> str:
        return f"rag:meta:{doc_id}"

    async def upsert(self, documents: List[RAGDocument]) -> None:
        if not self._redis:
            logger.warning("RAGService not initialized; skipping upsert")
            return
        texts = [d.text for d in documents]
        vectors = self._embed(texts)
        for doc, vec in zip(documents, vectors):
            self._redis.set(self._key_vec(doc.doc_id), self._vec_to_str(vec), ttl=86400 * 180)
            self._redis.set(self._key_meta(doc.doc_id), json.dumps(doc.metadata), ttl=86400 * 180)

    async def similarity_search(self, query: str, k: int = 5) -> List[Tuple[RAGDocument, float]]:
        if not self._redis:
            logger.warning("RAGService not initialized; returning empty search results")
            return []
        # Fetch all known ids from metadata keys (simple index)
        # Note: RedisCache doesn't expose scan; we keep a manual list under rag:index
        index_json = self._redis.get("rag:index")
        if not index_json:
            return []
        doc_ids: List[str] = json.loads(index_json)

        # Load vectors and metadata
        vectors = []
        metas = []
        valid_ids = []
        for doc_id in doc_ids:
            v_str = self._redis.get(self._key_vec(doc_id))
            m_str = self._redis.get(self._key_meta(doc_id))
            if not v_str or not m_str:
                continue
            vectors.append(self._str_to_vec(v_str))
            metas.append(json.loads(m_str))
            valid_ids.append(doc_id)

        if not vectors:
            return []

        matrix = np.vstack(vectors)
        q = self._embed([query])[0]
        sims = matrix @ q  # cosine since normalized
        top_idx = np.argsort(-sims)[:k]

        results: List[Tuple[RAGDocument, float]] = []
        for i in top_idx:
            results.append(
                (
                    RAGDocument(doc_id=valid_ids[i], text="", metadata=metas[i]),
                    float(sims[i]),
                )
            )
        return results

    async def add_to_index(self, doc_ids: List[str]) -> None:
        if not self._redis:
            return
        current = self._redis.get("rag:index")
        ids: List[str] = [] if not current else json.loads(current)
        merged = sorted(list(set(ids + doc_ids)))
        self._redis.set("rag:index", json.dumps(merged), ttl=86400 * 365)
