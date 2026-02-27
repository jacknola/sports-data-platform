"""
Sports API Service — Multi-source game discovery and odds fetching.

Architecture:
    1. ESPN Scoreboard (free, no API key) → game discovery
    2. The Odds API /events endpoint   → secondary game discovery
    3. The Odds API /odds endpoint     → odds enrichment
    4. TTL in-memory cache             → serve stale when APIs fail
    5. Hardcoded fallback              → absolute last resort (logged as error)

All methods track their data source so callers can tag reports
with [LIVE], [CACHED], or [FALLBACK].
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from app.config import settings

# ─────────────────────────────────────────────────────────────────
# ESPN sport keys → The Odds API sport keys mapping
# ─────────────────────────────────────────────────────────────────
ESPN_SPORT_MAP = {
    "basketball_ncaab": "basketball/mens-college-basketball",
    "basketball_nba": "basketball/nba",
}

ODDS_API_SPORT_DISPLAY = {
    "basketball_ncaab": "NCAAB",
    "basketball_nba": "NBA",
}

# Bookmakers to request (reduces credit burn vs. requesting all)
SHARP_BOOKMAKERS = {"pinnacle", "circa", "betonlineag", "lowvig", "betcris", "bookmaker", "betfair", "matchbook"}
RETAIL_BOOKMAKERS = {
    "draftkings", "fanduel", "betmgm", "caesars", "pointsbet", "bovada", 
    "betrivers", "williamhill_us", "unibet_us", "superbook", "betway", 
    "sugarhouse", "foxbet", "barstool", "twinspires", "pointsbetus", 
    "wynnbet", "betright", "topsport", "ladbrokes", "neds", "unibet"
}
BOOKMAKER_FILTER = ",".join(sorted(SHARP_BOOKMAKERS | RETAIL_BOOKMAKERS))
BOOKMAKER_FILTER = ",".join(sorted(SHARP_BOOKMAKERS | RETAIL_BOOKMAKERS))

# ESPN conference ID → display name (NCAAB only)
_ESPN_CONF_MAP: Dict[str, str] = {}  # populated lazily from ESPN data


# ─────────────────────────────────────────────────────────────────
# TTL Cache
# ─────────────────────────────────────────────────────────────────
@dataclass
class _CacheEntry:
    data: Any
    ts: float = field(default_factory=time.time)
    source: str = "live"


# ─────────────────────────────────────────────────────────────────
# Data source tag
# ─────────────────────────────────────────────────────────────────
@dataclass
class FetchResult:
    """Wraps API results with provenance metadata."""

    data: List[Dict[str, Any]]
    source: str  # "espn_live", "oddsapi_live", "cached", "stale_cache", "fallback"
    source_label: str = ""  # human-friendly, e.g. "[LIVE]"
    game_count: int = 0
    api_requests_remaining: Optional[int] = None
    api_requests_used: Optional[int] = None

    def __post_init__(self):
        self.game_count = len(self.data)
        labels = {
            "espn_live": "[LIVE - ESPN]",
            "oddsapi_live": "[LIVE - Odds API]",
            "oddsapi_events": "[LIVE - Odds API Events]",
            "cached": "[CACHED]",
            "cached_db": "[DB CACHE]",
            "stale_cache": "[STALE CACHE]",
            "sportsgameodds_live": "[LIVE - SportsGameOdds]",
            "odds_api_io_live": "[LIVE - Odds-API.io]",
            "fallback": "[FALLBACK]",
        }
        self.source_label = labels.get(self.source, f"[{self.source.upper()}]")


class TTLCache:
    """Simple in-memory cache with per-key TTL (seconds)."""

    def __init__(self, default_ttl: int = 300):
        self._store: Dict[str, _CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[_CacheEntry]:
        entry = self._store.get(key)
        if entry is None:
            return None
        age = time.time() - entry.ts
        if age > (ttl or self._default_ttl):
            return None  # expired
        return entry

    def get_stale(self, key: str) -> Optional[_CacheEntry]:
        """Return entry even if expired — for graceful degradation."""
        return self._store.get(key)

    def set(self, key: str, data: Any, source: str = "live") -> None:
        self._store[key] = _CacheEntry(data=data, ts=time.time(), source=source)

    def age(self, key: str) -> Optional[float]:
        entry = self._store.get(key)
        return (time.time() - entry.ts) if entry else None


class PersistentCache:
    """Database-backed persistent cache for API responses."""

    def __init__(self, default_ttl: int = 3600):
        self._enabled = False
        try:
            from app.database import SessionLocal, engine, Base
            from app.models.api_cache import APICache

            self._Session = SessionLocal
            self._Model = APICache
            self._default_ttl = default_ttl

            # Ensure tables are created
            Base.metadata.create_all(bind=engine)
            self._enabled = True
            logger.info("Persistent cache initialized successfully")
        except (ImportError, Exception) as e:
            logger.warning(f"Persistent cache disabled: {e}")

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[FetchResult]:
        """Retrieve from database if not expired."""
        if not self._enabled:
            return None

        session = self._Session()
        try:
            entry = session.query(self._Model).filter_by(key=key).first()
            if not entry:
                return None

            age = (datetime.utcnow() - entry.timestamp).total_seconds()
            if age > (ttl or self._default_ttl):
                return None  # Expired

            import json

            return FetchResult(
                data=json.loads(str(entry.data if not hasattr(entry.data, 'value') else entry.data.value)),
                source="cached_db",
                game_count=0,  # FetchResult __post_init__ handles this
            )
        except Exception as e:
            logger.error(f"Persistent cache retrieval failed: {e}")
            return None
        finally:
            session.close()

    def set(self, key: str, data: Any, source: str = "live"):
        """Save to database, updating if key exists."""
        if not self._enabled:
            return

        session = self._Session()
        try:
            import json

            entry = session.query(self._Model).filter_by(key=key).first()
            if entry:
                setattr(entry, "data", json.dumps(data))
                setattr(entry, "source", source)
                setattr(entry, "timestamp", datetime.utcnow())
            else:
                new_entry = self._Model(
                    key=key,
                    data=json.dumps(data),
                    source=source,
                    timestamp=datetime.utcnow(),
                )
                session.add(new_entry)
            session.commit()
        except Exception as e:
            logger.error(f"Persistent cache storage failed: {e}")
            session.rollback()
        finally:
            session.close()


# Module-level singletons so cache persists across calls within a process
_cache = TTLCache(default_ttl=300)  # 5 minute default
_db_cache = PersistentCache(default_ttl=3600)  # 1 hour default

# Odds API exhaustion tracking (shared across instances like _cache)
_odds_api_exhausted: bool = False
_odds_api_exhausted_at: float = 0.0  # timestamp when flagged
_EXHAUSTION_RESET_SECONDS: float = 3600.0  # auto-reset after 1 hour


# ─────────────────────────────────────────────────────────────────
# Team name normalization
# ─────────────────────────────────────────────────────────────────

# ESPN uses slightly different names than The Odds API.  This map
# covers the most common discrepancies for NCAAB + NBA.
_TEAM_NAME_ALIASES: Dict[str, str] = {
    # NCAAB
    "UConn Huskies": "Connecticut Huskies",
    "UConn": "Connecticut Huskies",
    "UCONN": "Connecticut Huskies",
    "Pitt Panthers": "Pittsburgh Panthers",
    "SMU Mustangs": "Southern Methodist Mustangs",
    "Ole Miss Rebels": "Mississippi Rebels",
    "UNLV Rebels": "UNLV Runnin' Rebels",
    "LSU Tigers": "LSU Tigers",
    "USC Trojans": "Southern California Trojans",
    "UCF Knights": "Central Florida Knights",
    "BYU Cougars": "Brigham Young Cougars",
    "VCU Rams": "Virginia Commonwealth Rams",
    # NBA
    "LA Clippers": "Los Angeles Clippers",
}


def normalize_team_name(name: str) -> str:
    """Normalize a team name to a canonical form."""
    return _TEAM_NAME_ALIASES.get(name, name)


# ─────────────────────────────────────────────────────────────────
# Main Service
# ─────────────────────────────────────────────────────────────────
class SportsAPIService:
    """Multi-source sports data service.

    Game discovery waterfall:
        ESPN Scoreboard → Odds API /events → TTL cache → stale cache → (caller fallback)

    Odds enrichment:
        Odds API /odds → TTL cache → (caller uses defaults)
    """

    def __init__(self):
        # Dual API key resolution (from sports-betting-edge-tool branch)
        self.odds_api_key = (
            getattr(settings, "ODDS_API_KEY", None)
            or getattr(settings, "ODDSAPI_API_KEY", None)
            or getattr(settings, "THE_ODDS_API_KEY", None)
        )
        self.sportsradar_key = getattr(settings, "SPORTSRADAR_API_KEY", None)
        self.base_url = "https://api.the-odds-api.com/v4"
        self._last_quota_remaining: Optional[int] = None
        self._last_quota_used: Optional[int] = None

    # ──────────────────────────────────────────────────────────────
    # Phase 1: ESPN Scoreboard (primary game discovery)
    # ──────────────────────────────────────────────────────────────

    async def get_espn_scoreboard(self, sport: str) -> FetchResult:
        """Fetch today's games from ESPN's free scoreboard API.

        No API key required.  Returns structured game dicts with
        home/away teams, tip time, conference, and ESPN game ID.

        Args:
            sport: Odds API sport key (e.g. 'basketball_ncaab')

        Returns:
            FetchResult with list of game dicts
        """
        espn_path = ESPN_SPORT_MAP.get(sport)
        if not espn_path:
            logger.warning(f"No ESPN mapping for sport '{sport}'")
            return FetchResult(data=[], source="espn_live")

        today_str = datetime.now().strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_path}/scoreboard"
        cache_key = f"espn_scoreboard_{sport}_{today_str}"

        # 1. Check in-memory cache
        mem_cached = _cache.get(cache_key)
        if mem_cached:
            return FetchResult(data=mem_cached.data, source="cached")

        # 2. Check persistent database cache
        db_cached = _db_cache.get(cache_key, ttl=3600)  # 1 hour persistence
        if db_cached:
            # Re-populate in-memory cache
            _cache.set(cache_key, db_cached.data, source="cached_db")
            return db_cached

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            raw = response.json()
            events = raw.get("events", [])
            games = []

            for event in events:
                try:
                    competition = event["competitions"][0]
                    competitors = competition.get("competitors", [])
                    if len(competitors) < 2:
                        continue

                    home = next(
                        (c for c in competitors if c.get("homeAway") == "home"), None
                    )
                    away = next(
                        (c for c in competitors if c.get("homeAway") == "away"), None
                    )
                    if not home or not away:
                        continue

                    home_team = home.get("team", {}).get("displayName", "")
                    away_team = away.get("team", {}).get("displayName", "")

                    # Conference (NCAAB only — extracted from group name)
                    conference = ""
                    for comp in competitors:
                        conf_name = comp.get("team", {}).get("conferenceId", "")
                        # ESPN sometimes puts conference in different spots
                        groups = event.get("competitions", [{}])[0].get("groups", {})
                        if groups:
                            conference = groups.get("name", "")
                            break

                    # Tip time
                    commence_time = event.get("date", "")

                    # Game status
                    status_type = (
                        competition.get("status", {})
                        .get("type", {})
                        .get("name", "STATUS_SCHEDULED")
                    )

                    # Skip completed games
                    if status_type == "STATUS_FINAL":
                        continue

                    game = {
                        "espn_id": event.get("id", ""),
                        "home_team": normalize_team_name(home_team),
                        "away_team": normalize_team_name(away_team),
                        "commence_time": commence_time,
                        "conference": conference,
                        "status": status_type,
                        "sport": sport,
                    }
                    games.append(game)

                except (KeyError, IndexError, StopIteration) as e:
                    logger.debug(f"Skipping ESPN event parse error: {e}")
                    continue

            result = FetchResult(data=games, source="espn_live")
            if games:
                _cache.set(cache_key, games, source="espn_live")
                _db_cache.set(cache_key, games, source="espn_live")
                logger.info(
                    f"ESPN scoreboard: {len(games)} games for "
                    f"{ODDS_API_SPORT_DISPLAY.get(sport, sport)}"
                )
            else:
                logger.warning(f"ESPN scoreboard returned 0 games for {sport}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"ESPN HTTP error for {sport}: {e.response.status_code} — "
                f"{e.response.text[:200]}"
            )
        except Exception as e:
            logger.error(f"ESPN scoreboard failed for {sport}: {e}")

        # Try cache on failure
        cached = _cache.get(cache_key, ttl=600)  # 10 min grace
        if cached:
            logger.info(
                f"Serving cached ESPN data for {sport} (age: {_cache.age(cache_key):.0f}s)"
            )
            return FetchResult(data=cached.data, source="cached")

        return FetchResult(data=[], source="espn_live")

    # ──────────────────────────────────────────────────────────────
    # Phase 1: Odds API /events (secondary game discovery)
    # ──────────────────────────────────────────────────────────────

    async def get_events(self, sport: str) -> FetchResult:
        """Fetch upcoming events from The Odds API /events endpoint.

        This returns games regardless of whether odds are posted yet,
        decoupling game discovery from odds availability.

        Args:
            sport: Odds API sport key (e.g. 'basketball_ncaab')

        Returns:
            FetchResult with list of event dicts
        """
        if not self.odds_api_key:
            logger.warning("No Odds API key — cannot call /events")
            return FetchResult(data=[], source="oddsapi_events")

        cache_key = f"oddsapi_events_{sport}"

        # 1. Check in-memory cache
        mem_cached = _cache.get(cache_key)
        if mem_cached:
            return FetchResult(data=mem_cached.data, source="cached")

        # 2. Check persistent database cache
        db_cached = _db_cache.get(
            cache_key, ttl=14400
        )  # 4 hours persistence for events
        if db_cached:
            _cache.set(cache_key, db_cached.data, source="cached_db")
            return db_cached

        url = f"{self.base_url}/sports/{sport}/events"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    url,
                    params={"apiKey": self.odds_api_key},
                )
                self._track_quota(response)
                response.raise_for_status()

            events = response.json()
            result = FetchResult(
                data=events,
                source="oddsapi_events",
                api_requests_remaining=self._last_quota_remaining,
                api_requests_used=self._last_quota_used,
            )
            if events:
                _cache.set(cache_key, events, source="oddsapi_events")
                _db_cache.set(cache_key, events, source="oddsapi_events")
                logger.info(
                    f"Odds API /events: {len(events)} events for "
                    f"{ODDS_API_SPORT_DISPLAY.get(sport, sport)}"
                )
            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Odds API /events HTTP {e.response.status_code} for {sport}: "
                f"{e.response.text[:200]}"
            )
        except Exception as e:
            logger.error(f"Odds API /events failed for {sport}: {e}")

        # Try cache
        cached = _cache.get(cache_key, ttl=600)
        if cached:
            return FetchResult(data=cached.data, source="cached")

        return FetchResult(data=[], source="oddsapi_events")

    # ──────────────────────────────────────────────────────────────
    # Phase 2: Odds API /odds (enrichment — with filtering + cache)
    # ──────────────────────────────────────────────────────────────

    async def _try_odds_api_io_fallback(self, sport: str) -> List[Dict[str, Any]]:
        """Try fetching odds from Odds-API.io as a fallback source."""
        key = getattr(settings, "ODDS_API_IO_KEY", None)
        if not key:
            return []

        try:
            from app.services.odds_api_io import OddsApiIoService
            oio = OddsApiIoService(key)
            data = await oio.get_odds(sport)
            if data:
                cache_key = f"oddsapi_odds_{sport}"
                _cache.set(cache_key, data, source="odds_api_io_live")
                _db_cache.set(cache_key, data, source="odds_api_io_live")
            return data
        except Exception as e:
            logger.error(f"OddsApiIo fallback failed for {sport}: {e}")
            return []

    async def _try_sportsgameodds_fallback(self, sport: str) -> List[Dict[str, Any]]:
        """Try fetching odds from SportsGameOdds as a fallback source.

        Returns normalized game data or empty list on failure.
        """
        try:
            from app.services.sports_game_odds import SportsGameOddsService
        except ImportError:
            return []

        sgo = SportsGameOddsService()
        if not sgo.is_configured:
            return []

        try:
            data = await sgo.get_odds_by_sport_key(sport)
            if data:
                cache_key = f"oddsapi_odds_{sport}"
                _cache.set(cache_key, data, source="sportsgameodds_live")
                _db_cache.set(cache_key, data, source="sportsgameodds_live")
                logger.info(
                    f"SportsGameOdds fallback: {len(data)} games for {sport}"
                )
            return data
        except Exception as e:
            logger.error(f"SportsGameOdds fallback failed for {sport}: {e}")
            return []

    async def get_odds(
        self,
        sport: str,
        markets: str = "h2h,spreads,totals",
        bookmakers: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch current odds for a sport with caching + quota tracking.

        Waterfall:
            1. In-memory cache / DB cache
            2. The Odds API (if key configured and not exhausted)
            3. SportsGameOdds API (fallback)
            4. Stale cache
            5. Empty list

        Args:
            sport: Sport identifier (e.g. 'basketball_ncaab')
            markets: Comma-separated market types
            bookmakers: Comma-separated bookmaker keys (defaults to
                        SHARP + RETAIL set to reduce credit burn)

        Returns:
            List of odds event objects (empty list on failure)
        """
        global _odds_api_exhausted, _odds_api_exhausted_at

        # Auto-reset exhaustion flag after 1 hour
        if _odds_api_exhausted and (time.time() - _odds_api_exhausted_at) > _EXHAUSTION_RESET_SECONDS:
            logger.info("Odds API exhaustion flag auto-reset after 1 hour — will retry")
            _odds_api_exhausted = False
            _odds_api_exhausted_at = 0.0

        cache_key = f"oddsapi_odds_{sport}"

        # 1. Check in-memory cache
        mem_cached = _cache.get(cache_key)
        if mem_cached:
            return mem_cached.data

        # 2. Check persistent database cache
        db_cached = _db_cache.get(cache_key, ttl=1800)  # 30 mins persistence for odds
        if db_cached:
            _cache.set(cache_key, db_cached.data, source="cached_db")
            return db_cached.data if isinstance(db_cached.data, list) else []

        # 3. If Odds API key missing or exhausted, skip straight to SGO fallback
        if not self.odds_api_key or _odds_api_exhausted:
            reason = "exhausted" if _odds_api_exhausted else "not configured"
            logger.warning(f"Odds API {reason} — trying fallbacks for {sport}")
            
            # Try Odds-API.io first (better data)
            oio_data = await self._try_odds_api_io_fallback(sport)
            if oio_data:
                return oio_data
                
            # Try SGO second
            sgo_data = await self._try_sportsgameodds_fallback(sport)
            if sgo_data:
                return sgo_data
            # Fall through to stale cache
            stale = _cache.get_stale(cache_key)
            if stale:
                logger.info(f"Serving stale cached odds for {sport}")
                return stale.data
            return []

        # 4. Try The Odds API
        try:
            params: Dict[str, Any] = {
                "regions": "us",
                "markets": markets,
                "apiKey": self.odds_api_key,
                "oddsFormat": "american",
            }
            if bookmakers:
                params["bookmakers"] = bookmakers
            else:
                params["bookmakers"] = BOOKMAKER_FILTER

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.base_url}/sports/{sport}/odds",
                    params=params,
                )
                self._track_quota(response)
                response.raise_for_status()

            data = response.json()

            # ── commence_time filtering ──
            # Only keep games starting within the next 48 hours
            now_ts = datetime.now(timezone.utc)
            filtered = []
            for game in data:
                ct = game.get("commence_time", "")
                if ct:
                    try:
                        game_time = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                        hours_until = (game_time - now_ts).total_seconds() / 3600
                        # Keep games: not yet started OR started within last 3 hours
                        if -3.0 <= hours_until <= 48.0:
                            filtered.append(game)
                    except (ValueError, TypeError):
                        filtered.append(game)  # keep if unparseable
                else:
                    filtered.append(game)

            if filtered:
                _cache.set(cache_key, filtered, source="oddsapi_live")
                _db_cache.set(cache_key, filtered, source="oddsapi_live")
            logger.info(
                f"Odds API: {len(filtered)}/{len(data)} games for {sport} "
                f"(filtered to ±24h window) | "
                f"Quota: {self._last_quota_remaining} remaining"
            )
            return filtered

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text[:200]
            if status in (401, 429):
                label = "quota exhausted" if status == 401 else "rate-limited"
                logger.error(f"Odds API {status} ({label}) for {sport}: {body}")
                _odds_api_exhausted = True
                _odds_api_exhausted_at = time.time()
                # Try fallbacks immediately
                oio_data = await self._try_odds_api_io_fallback(sport)
                if oio_data: return oio_data
                
                sgo_data = await self._try_sportsgameodds_fallback(sport)
                if sgo_data: return sgo_data
            else:
                logger.error(f"Odds API HTTP {status} for {sport}: {body}")
                # Try fallbacks for other HTTP errors too
                oio_data = await self._try_odds_api_io_fallback(sport)
                if oio_data: return oio_data
                
                sgo_data = await self._try_sportsgameodds_fallback(sport)
                if sgo_data: return sgo_data
        except Exception as e:
            logger.error(f"Odds API /odds failed for {sport}: {e}")
            # Try fallbacks for network/timeout errors
            oio_data = await self._try_odds_api_io_fallback(sport)
            if oio_data: return oio_data
            
            sgo_data = await self._try_sportsgameodds_fallback(sport)
            if sgo_data: return sgo_data

        # 5. Serve from cache on failure
        cached = _cache.get(cache_key, ttl=600)
        if cached:
            logger.info(
                f"Serving cached odds for {sport} (age: {_cache.age(cache_key):.0f}s)"
            )
            return cached.data

        # 6. Try stale cache as last resort
        stale = _cache.get_stale(cache_key)
        if stale:
            logger.warning(
                f"Serving STALE cached odds for {sport} "
                f"(age: {_cache.age(cache_key):.0f}s)"
            )
            return stale.data

        logger.error(
            f"ALL ODDS SOURCES FAILED for {sport} — "
            f"No Odds API, no SportsGameOdds, no cache. "
            f"Returning empty list; callers will use mock data."
        )
        return []

    # ──────────────────────────────────────────────────────────────
    # Game discovery waterfall (combines ESPN + Odds API)
    # ──────────────────────────────────────────────────────────────

    async def discover_games(self, sport: str) -> FetchResult:
        """High-level game discovery with multi-source waterfall.

        1. ESPN Scoreboard (free, no key)
        2. Odds API /events
        3. TTL cache
        4. Stale cache

        Callers should check result.source to decide on fallback behavior.

        Args:
            sport: Odds API sport key

        Returns:
            FetchResult with game list + provenance
        """
        # 1. ESPN first (free, no credit cost)
        espn_result = await self.get_espn_scoreboard(sport)
        if espn_result.data:
            return espn_result

        # 2. Odds API /events
        events_result = await self.get_events(sport)
        if events_result.data:
            return events_result

        # 3. Check caches
        for cache_key in [f"espn_scoreboard_{sport}", f"oddsapi_events_{sport}"]:
            stale = _cache.get_stale(cache_key)
            if stale and stale.data:
                age = _cache.age(cache_key) or 0
                logger.warning(
                    f"All live sources failed for {sport}. "
                    f"Serving stale cache (age: {age:.0f}s)"
                )
                return FetchResult(data=stale.data, source="stale_cache")

        logger.error(
            f"All game discovery sources failed for {sport} — "
            f"no ESPN, no Odds API, no cache."
        )
        return FetchResult(data=[], source="fallback")

    # ──────────────────────────────────────────────────────────────
    # Scores (unchanged but with better error handling)
    # ──────────────────────────────────────────────────────────────

    async def get_scores(self, sport: str, days_from: int = 1) -> List[Dict[str, Any]]:
        """Fetch completed game scores over the last N days."""
        if not self.odds_api_key:
            logger.warning("Odds API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.base_url}/sports/{sport}/scores",
                    params={
                        "daysFrom": days_from,
                        "apiKey": self.odds_api_key,
                    },
                )
                self._track_quota(response)
                response.raise_for_status()

            data = response.json()
            completed = [g for g in data if g.get("completed")]
            logger.info(
                f"Scores for {sport}: {len(completed)} completed "
                f"(last {days_from} days)"
            )
            return completed

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Scores HTTP {e.response.status_code} for {sport}: "
                f"{e.response.text[:200]}"
            )
            return []
        except Exception as e:
            logger.error(f"Scores fetch failed for {sport}: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Player Props — per-event odds endpoint
    # ──────────────────────────────────────────────────────────────

    # Core 8 prop markets — singles + combos (good credit/value ratio)
    CORE_PROP_MARKETS: List[str] = [
        "player_points",
        "player_rebounds",
        "player_assists",
        "player_threes",
        # Combinations removed per user request to focus on main stats + alternate lines
    ]

    # Extended markets (use when credit budget allows)
    EXTENDED_PROP_MARKETS: List[str] = [
        "player_blocks",
        "player_steals",
        "player_blocks_steals",
        "player_turnovers",
        "player_double_double",
    ]

    PROP_BOOKMAKERS: str = BOOKMAKER_FILTER  # Use combined sharp + retail books for wider odds ranges

    async def get_event_player_props(
        self,
        sport: str,
        event_id: str,
        markets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Fetch player prop odds for a single event.

        Uses The Odds API /events/{eventId}/odds endpoint.
        Each market × region = 1 API credit.

        Args:
            sport: Sport key (e.g. 'basketball_nba')
            event_id: Event UUID from get_events()
            markets: List of market keys (defaults to CORE_PROP_MARKETS)

        Returns:
            Raw Odds API response dict with bookmakers/markets, or
            empty dict on failure.
        """
        if not self.odds_api_key:
            logger.warning("No API key — cannot fetch player props")
            return {}

        if markets is None:
            markets = self.CORE_PROP_MARKETS

        markets_csv = ",".join(markets)
        cache_key = f"props_{sport}_{event_id}_{markets_csv}"

        # 1. Check in-memory cache
        mem_cached = _cache.get(cache_key, ttl=180)  # 3-min TTL for props
        if mem_cached:
            return mem_cached.data

        # 2. Check persistent database cache
        db_cached = _db_cache.get(cache_key, ttl=3600)  # 1 hour persistence for props
        if db_cached:
            _cache.set(cache_key, db_cached.data, source="cached_db")
            return db_cached.data if isinstance(db_cached.data, dict) else {}

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.get(
                    f"{self.base_url}/sports/{sport}/events/{event_id}/odds",
                    params={
                        "apiKey": self.odds_api_key,
                        "regions": "us,eu,uk,au",
                        "markets": markets_csv,
                        "oddsFormat": "american",
                        "bookmakers": self.PROP_BOOKMAKERS,
                    },
                )
                self._track_quota(response)
                response.raise_for_status()

            data = response.json()
            if data:
                _cache.set(cache_key, data, source="oddsapi_props")
                _db_cache.set(cache_key, data, source="oddsapi_props")
            logger.info(
                f"Props for event {event_id[:8]}...: "
                f"{len(data.get('bookmakers', []))} bookmakers, "
                f"{len(markets)} markets"
            )
            return data

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 422:
                # Event may not have prop markets available
                logger.debug(f"No prop markets for event {event_id[:8]}... ({sport})")
            elif status == 429:
                logger.error(
                    f"Odds API rate-limited fetching props for {event_id[:8]}..."
                )
            else:
                logger.error(
                    f"Props HTTP {status} for {event_id[:8]}...: "
                    f"{e.response.text[:200]}"
                )
        except Exception as e:
            logger.error(f"Props fetch failed for {event_id[:8]}...: {e}")

        # Serve stale cache on failure
        stale = _cache.get_stale(cache_key)
        if stale:
            return stale.data

        return {}

    async def get_all_player_props(
        self,
        sport: str,
        markets: Optional[List[str]] = None,
        max_events: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch player props for ALL today's events in a sport.

        Waterfall: discover events → fetch props per event → merge results.
        Respects quota: stops if remaining credits < 20.

        Args:
            sport: Sport key (e.g. 'basketball_nba')
            markets: Market keys (defaults to CORE_PROP_MARKETS)
            max_events: Cap on events to scan (None = all)

        Returns:
            List of enriched prop dicts, each containing:
            - player: str
            - prop_type: str (market key)
            - line: float
            - over_odds: int
            - under_odds: int
            - book: str (best book)
            - book_key: str
            - event_id: str
            - home_team: str
            - away_team: str
            - offerings: List[Dict] (all books)
            - devigged_over_prob: float
            - devigged_under_prob: float
        """
        if markets is None:
            markets = self.CORE_PROP_MARKETS

        cache_key = f"all_props_{sport}"

        # 1. Check in-memory cache
        mem_cached = _cache.get(cache_key, ttl=180)
        if mem_cached:
            logger.info(f"Serving cached prop scan for {sport}")
            return mem_cached.data

        # 2. Check persistent database cache
        db_cached = _db_cache.get(
            cache_key, ttl=600
        )  # 10 mins persistence for full scans
        if db_cached:
            _cache.set(cache_key, db_cached.data, source="cached_db")
            return db_cached.data

        # Step 1: Get events with Odds API IDs (required for prop endpoints).
        # discover_games() often returns ESPN data which lacks Odds API UUIDs,
        # so we fetch from get_odds() which always has 'id' fields.
        odds_events = await self.get_odds(sport, markets="h2h")
        if not odds_events:
            # Fallback: try /events endpoint directly
            events_result = await self.get_events(sport)
            odds_events = events_result.data if events_result.data else []

        if not odds_events:
            logger.warning(f"No Odds API events for {sport} — cannot scan props")
            return []

        # Step 2: Get event IDs
        event_ids: List[str] = []
        event_meta: Dict[str, Dict[str, str]] = {}

        for ev in odds_events:
            eid = ev.get("id", "")
            if not eid:
                continue
            event_ids.append(eid)
            event_meta[eid] = {
                "home_team": ev.get("home_team", ""),
                "away_team": ev.get("away_team", ""),
            }

        if max_events:
            event_ids = event_ids[:max_events]

        logger.info(
            f"Prop scan: {len(event_ids)} events × {len(markets)} markets "
            f"for {sport} (~{len(event_ids) * len(markets)} credits)"
        )

        # Step 3: Check quota before proceeding
        estimated_cost = len(event_ids) * len(markets)
        if (
            self._last_quota_remaining is not None
            and self._last_quota_remaining < estimated_cost + 20
        ):
            logger.warning(
                f"Insufficient quota for prop scan: need ~{estimated_cost}, "
                f"only {self._last_quota_remaining} remaining. Skipping."
            )
            stale = _cache.get_stale(cache_key)
            if stale:
                return stale.data
            return []

        # Step 4: Fetch props per event
        all_raw_props: List[Dict[str, Any]] = []

        for eid in event_ids:
            event_data = await self.get_event_player_props(sport, eid, markets)
            if not event_data:
                continue

            meta = event_meta.get(eid, {})
            home = meta.get("home_team", event_data.get("home_team", ""))
            away = meta.get("away_team", event_data.get("away_team", ""))

            # Parse bookmakers → extract props
            for book in event_data.get("bookmakers", []):
                book_key = book.get("key", "")
                book_title = book.get("title", book_key)

                for market in book.get("markets", []):
                    market_key = market.get("key", "")
                    outcomes = market.get("outcomes", [])

                    # Pair Over/Under by player description + line to support alternate lines
                    player_pairs: Dict[str, Dict[str, Any]] = {}
                    for out in outcomes:
                        player = out.get("description", "")
                        line = out.get("point", 0.0)
                        if not player:
                            continue

                        # Key by player + line to distinguish alternate lines (+250, +300 props)
                        player_key = f"{player}|{line}"
                        if player_key not in player_pairs:
                            player_pairs[player_key] = {"player": player, "line": line}

                        side = out.get("name", "").lower()
                        if side == "over":
                            player_pairs[player_key]["over_odds"] = out.get("price", -110)
                        elif side == "under":
                            player_pairs[player_key]["under_odds"] = out.get("price", -110)

                    for pk, pair in player_pairs.items():
                        if "over_odds" in pair and "under_odds" in pair:
                            all_raw_props.append(
                                {
                                    "player": pair["player"],
                                    "prop_type": market_key,
                                    "line": pair["line"],
                                    "over_odds": pair["over_odds"],
                                    "under_odds": pair["under_odds"],
                                    "book": book_title,
                                    "book_key": book_key,
                                    "event_id": eid,
                                    "home_team": home,
                                    "away_team": away,
                                }
                            )
                            all_raw_props.append(
                                {
                                    "player": player,
                                    "prop_type": market_key,
                                    "line": pair.get("line", 0.0),
                                    "over_odds": pair["over_odds"],
                                    "under_odds": pair["under_odds"],
                                    "book": book_title,
                                    "book_key": book_key,
                                    "event_id": eid,
                                    "home_team": home,
                                    "away_team": away,
                                }
                            )

            # Brief pause between events to avoid hammering
            import asyncio

            await asyncio.sleep(0.1)

        if not all_raw_props:
            logger.warning(f"Prop scan found 0 props for {sport}")
            return []

        # Step 5: Group by player|prop_type, enrich with devig + best lines
        grouped = self._group_and_enrich_props(all_raw_props)

        logger.info(
            f"Prop scan complete: {len(grouped)} unique player props "
            f"from {len(event_ids)} events"
        )

        _cache.set(cache_key, grouped, source="oddsapi_props")
        _db_cache.set(cache_key, grouped, source="oddsapi_props")
        return grouped

    def _group_and_enrich_props(
        self,
        raw_props: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Group raw props by player|prop_type and enrich with devig + best lines.

        Args:
            raw_props: Flat list of per-book prop offerings

        Returns:
            List of grouped, enriched prop dicts
        """
        # Group by player + prop_type + line to distinguish alternate props
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for prop in raw_props:
            # Adding line to key so alternate lines (+250, +300 odds) are treated as separate props
            key = f"{prop['player']}|{prop['prop_type']}|{prop['line']}"
            if key not in groups:
                groups[key] = []
            groups[key].append(prop)
        enriched: List[Dict[str, Any]] = []

        for key, offerings in groups.items():
            if not offerings:
                continue

            # Find best over and under odds across all books for this specific line
            best_over = max(offerings, key=lambda x: x.get("over_odds", -999))
            best_under = max(offerings, key=lambda x: x.get("under_odds", -999))

            # Since we group by line now, canonical_line is just the line of the offerings
            first = offerings[0]
            canonical_line = first.get("line", 0)

            # Devig using best available odds (sharp book preferred)
            over_odds = best_over.get("over_odds", -110)
            under_odds = best_under.get("under_odds", -110)
            devig_over, devig_under = self._devig_american(over_odds, under_odds)
            enriched.append(
                {
                    "player": first["player"],
                    "prop_type": first["prop_type"],
                    "line": canonical_line,
                    "over_odds": over_odds,
                    "under_odds": under_odds,
                    "best_over_book": best_over.get("book", ""),
                    "best_over_odds": over_odds,
                    "best_under_book": best_under.get("book", ""),
                    "best_under_odds": under_odds,
                    "devigged_over_prob": devig_over,
                    "devigged_under_prob": devig_under,
                    "books_offering": len(offerings),
                    "event_id": first.get("event_id", ""),
                    "home_team": first.get("home_team", ""),
                    "away_team": first.get("away_team", ""),
                    "offerings": offerings,
                }
            )

        return enriched

    @staticmethod
    def _devig_american(over_odds: float, under_odds: float) -> tuple:
        """Devig a two-way prop market using multiplicative method.

        Args:
            over_odds: American over odds
            under_odds: American under odds

        Returns:
            (true_over_prob, true_under_prob) summing to ~1.0
        """

        def _to_implied(odds: float) -> float:
            if odds >= 100:
                return 100.0 / (odds + 100.0)
            else:
                return abs(odds) / (abs(odds) + 100.0)

        imp_over = _to_implied(over_odds)
        imp_under = _to_implied(under_odds)
        total = imp_over + imp_under

        if total <= 0:
            return (0.50, 0.50)

        return (imp_over / total, imp_under / total)

    # ──────────────────────────────────────────────────────────────
    # Phase 4: Quota tracking
    # ──────────────────────────────────────────────────────────────

    def _track_quota(self, response: httpx.Response) -> None:
        """Parse Odds API quota headers and log usage."""
        remaining = response.headers.get("x-requests-remaining")
        used = response.headers.get("x-requests-used")
        if remaining is not None:
            try:
                self._last_quota_remaining = int(remaining)
            except ValueError:
                pass
        if used is not None:
            try:
                self._last_quota_used = int(used)
            except ValueError:
                pass
        if self._last_quota_remaining is not None:
            logger.info(
                f"Odds API quota: {self._last_quota_used} used / "
                f"{self._last_quota_remaining} remaining"
            )
            if self._last_quota_remaining < 50:
                logger.warning(
                    f"⚠ Odds API quota LOW: only {self._last_quota_remaining} "
                    f"requests remaining!"
                )

    @property
    def quota_remaining(self) -> Optional[int]:
        return self._last_quota_remaining

    @property
    def quota_used(self) -> Optional[int]:
        return self._last_quota_used
