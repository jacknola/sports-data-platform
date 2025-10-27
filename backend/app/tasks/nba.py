"""
NBA-related background tasks
"""
from typing import List, Dict, Any
from loguru import logger

from app.celery_app import app
from app.services.sports_api import SportsAPIService
from app.services.cache import RedisCache

NBA_ODDS_CACHE_KEY = "nba:odds:today"
NBA_ODDS_TTL_SECONDS = 60 * 60 * 6  # 6 hours


@app.task(name="app.tasks.nba.refresh_nba_odds")
def refresh_nba_odds() -> Dict[str, Any]:
    """Fetch NBA odds and cache them for the day.
    Runs via celery-beat daily. Can also be called on-demand.
    """
    logger.info("Starting NBA odds refresh task")

    cache = RedisCache.get_sync()
    service = SportsAPIService()

    # The Odds API sport key for NBA is usually 'basketball_nba'
    sport_key = "basketball_nba"

    # SportsAPIService.get_odds is async; run it synchronously using httpx's internal loop via anyio
    import anyio

    async def _fetch() -> List[Dict[str, Any]]:
        return await service.get_odds(sport_key)

    odds_data: List[Dict[str, Any]] = []
    try:
        odds_data = anyio.run(_fetch)
    except Exception as e:
        logger.error(f"NBA odds fetch failed: {e}")

    payload = {
        "sport": sport_key,
        "count": len(odds_data),
        "games": odds_data,
    }

    cache.set_json(NBA_ODDS_CACHE_KEY, payload, ttl=NBA_ODDS_TTL_SECONDS)
    logger.info(f"Cached NBA odds for {payload['count']} games")
    return {"ok": True, "count": payload["count"]}
