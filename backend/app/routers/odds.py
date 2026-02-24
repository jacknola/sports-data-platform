"""
Odds data endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from loguru import logger

from app.services.cache import RedisCache
from app.tasks.nba import NBA_ODDS_CACHE_KEY
from app.celery_app import app as celery_app

router = APIRouter()


@router.get("/odds/{sport}")
async def get_current_odds(sport: str) -> Dict[str, Any]:
    """
    Get current odds for a sport
    
    Args:
        sport: Sport name (nfl, nba, mlb, etc.)
        
    Returns:
        Current odds data
    """
    logger.info(f"Fetching odds for {sport}")

    # Currently, only NBA odds are cached via background tasks
    if sport.lower() in {"nba", "basketball_nba"}:
        cache = await RedisCache.get_instance()
        data = cache.get_json(NBA_ODDS_CACHE_KEY)
        if data:
            return data
        else:
            raise HTTPException(status_code=404, detail="NBA odds not available yet. Try refreshing.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported sport for odds endpoint")


@router.post("/odds/nba/refresh")
async def refresh_nba_odds() -> Dict[str, Any]:
    """Trigger a background refresh of NBA odds."""
    try:
        result = celery_app.send_task("app.tasks.nba.refresh_nba_odds", args=[])
        return {"queued": True, "task_id": result.id}
    except Exception as e:
        logger.error(f"Failed to enqueue NBA odds refresh: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue refresh task")

