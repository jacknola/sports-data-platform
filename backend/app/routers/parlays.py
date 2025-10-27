"""
Parlay ingestion and search endpoints
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.services.parlay_ingest import ParlayIngestionService
from app.services.rag_service import RAGService


router = APIRouter()
_ingestor = ParlayIngestionService()
_rag = RAGService()
_rag_initialized = False


@router.post("/parlays/ingest/twitter")
async def ingest_parlays_from_twitter(
    username: str = Query(..., description="Twitter username, e.g., 'dansaisp'"),
    max_results: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    try:
        result = await _ingestor.ingest_user_parlays(username=username, max_results=max_results)
        return result
    except Exception as e:
        logger.error(f"Parlay ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parlays/search")
async def search_parlays(
    q: str = Query(..., description="Free text query over parlay content"),
    k: int = Query(5, ge=1, le=20)
) -> Dict[str, Any]:
    try:
        global _rag_initialized
        if not _rag_initialized:
            await _rag.init()
            _rag_initialized = True
        hits = await _rag.similarity_search(q, k=k)
        return {
            "query": q,
            "results": [
                {"doc_id": doc.doc_id, "metadata": doc.metadata, "score": score} for doc, score in hits
            ],
        }
    except Exception as e:
        logger.error(f"Parlay search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
