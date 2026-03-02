"""
Odds refresh background tasks.

Pulls fresh FanDuel (primary book) odds for both NBA and NCAAB every 4 hours
and caches them in Redis so the analysis pipeline always has a warm, recent
snapshot without burning Odds API credits on every request.

Schedule: configured in celery_app.py via crontab(minute=0, hour="*/4").
"""

import anyio
from typing import Any, Dict, List

from loguru import logger

from app.celery_app import app
from app.config import settings
from app.services.cache import RedisCache
from app.services.sports_api import SportsAPIService

# Redis cache keys
_CACHE_KEY_NBA = "fanduel:odds:nba:latest"
_CACHE_KEY_NCAAB = "fanduel:odds:ncaab:latest"

# 4-hour TTL — slightly longer than the refresh interval so a slow/failed
# refresh doesn't leave the cache empty.
_TTL_SECONDS = int(settings.ODDS_REFRESH_INTERVAL_MINUTES * 60 * 1.25)

_SPORT_KEYS = {
    "nba": "basketball_nba",
    "ncaab": "basketball_ncaab",
}


def _cache_key(sport: str) -> str:
    return f"fanduel:odds:{sport}:latest"


@app.task(name="app.tasks.odds.refresh_fanduel_odds")
def refresh_fanduel_odds() -> Dict[str, Any]:
    """
    Fetch FanDuel odds for NBA and NCAAB and cache them in Redis.

    Runs every 4 hours via Celery beat. The primary book is read from
    settings.PRIMARY_BOOK so it can be changed without code edits.
    Filters the Odds API response to include only:
      - Pinnacle / sharp books  (for devigging)
      - The primary retail book (for bet placement, defaults to FanDuel)

    Returns a summary dict with game counts per sport.
    """
    book = settings.PRIMARY_BOOK
    cache = RedisCache.get_sync()
    service = SportsAPIService()

    results: Dict[str, Any] = {"ok": True, "book": book, "counts": {}}

    for sport, sport_key in _SPORT_KEYS.items():

        async def _fetch(sk: str = sport_key) -> List[Dict[str, Any]]:
            return await service.get_odds(sk)

        try:
            raw: List[Dict[str, Any]] = anyio.run(_fetch)
        except Exception as exc:
            logger.error(f"Odds fetch failed for {sport}: {exc}")
            results["counts"][sport] = 0
            results["ok"] = False
            continue

        # Filter bookmakers: keep sharp lines + primary retail book only
        filtered = _filter_bookmakers(raw, book)

        payload = {
            "sport": sport_key,
            "book": book,
            "count": len(filtered),
            "games": filtered,
        }
        cache.set_json(_cache_key(sport), payload, ttl=_TTL_SECONDS)
        results["counts"][sport] = len(filtered)
        logger.info(
            f"Cached {len(filtered)} {sport.upper()} games for {book} "
            f"(TTL {_TTL_SECONDS}s)"
        )

    return results


def _filter_bookmakers(
    games: List[Dict[str, Any]], primary_book: str
) -> List[Dict[str, Any]]:
    """
    Strip every bookmaker from each game's odds list except:
      - Pinnacle   (sharp reference for devigging)
      - primary_book (retail book for bet placement)

    Games with no matching bookmakers are still returned — the outer
    pipeline already handles missing books gracefully.
    """
    keep = {"pinnacle", primary_book.lower()}
    filtered = []
    for game in games:
        bookmakers = game.get("bookmakers") or []
        slim_bookmakers = [
            bm for bm in bookmakers if bm.get("key", "").lower() in keep
        ]
        filtered.append({**game, "bookmakers": slim_bookmakers})
    return filtered
