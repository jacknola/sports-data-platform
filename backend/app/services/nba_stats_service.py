"""
NBA Stats Service - Fetches player stats, game logs, matchup data, and injury reports
from public APIs (balldontlie.io, the-odds-api.com) for prop bet analysis.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

import httpx
from loguru import logger

from app.config import settings

# nba_api — scrapes NBA.com directly, no API key required
try:
    from nba_api.stats.static import players as nba_static_players
    from nba_api.stats.static import teams as nba_static_teams
    from nba_api.stats.endpoints import (
        playercareerstats,
        playergamelog,
        leaguedashteamstats,
    )

    _NBA_API_AVAILABLE = True
except ImportError:
    _NBA_API_AVAILABLE = False
    logger.warning("nba_api not installed — install with: pip install nba_api")


# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------


class TTLCache:
    """Simple in-memory cache with per-key TTL expiration."""

    def __init__(self, default_ttl: int = 300):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if it exists and has not expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with a TTL (seconds)."""
        ttl = ttl if ttl is not None else self._default_ttl
        self._store[key] = (value, time.time() + ttl)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._store.clear()

    def evict_expired(self) -> int:
        """Remove all expired entries and return the count of evicted keys."""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)


# ---------------------------------------------------------------------------
# Stat-key mappings
# ---------------------------------------------------------------------------

# Map from prop-type shorthand to the balldontlie field names
PROP_STAT_KEYS: Dict[str, List[str]] = {
    "points": ["pts"],
    "rebounds": ["reb"],
    "assists": ["ast"],
    "steals": ["stl"],
    "blocks": ["blk"],
    "threes": ["fg3m"],
    "pts+reb+ast": ["pts", "reb", "ast"],
    "pts+reb": ["pts", "reb"],
    "pts+ast": ["pts", "ast"],
    "reb+ast": ["reb", "ast"],
    "stl+blk": ["stl", "blk"],
    "turnovers": ["turnover"],
    "minutes": ["min"],
}

# All individual stat fields returned on season-average responses
ALL_STAT_FIELDS: List[str] = [
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "turnover",
    "min",
    "fg_pct",
    "fg3_pct",
    "ft_pct",
    "games_played",
]


# ---------------------------------------------------------------------------
# NBA Stats Service
# ---------------------------------------------------------------------------


class NBAStatsService:
    """
    Service for fetching NBA player statistics, game logs, matchup data,
    and injury reports from public APIs.

    Primary data source: balldontlie.io (free NBA stats API)
    Secondary data source: the-odds-api.com (odds / prop lines)
    """

    BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"
    ODDS_API_BASE = "https://api.the-odds-api.com/v4"

    # Cache TTLs in seconds
    CACHE_TTL_PLAYER_SEARCH = 3600  # 1 hour
    CACHE_TTL_SEASON_AVERAGES = 600  # 10 minutes
    CACHE_TTL_GAME_LOGS = 300  # 5 minutes
    CACHE_TTL_TEAM_STATS = 900  # 15 minutes
    CACHE_TTL_INJURY = 180  # 3 minutes
    CACHE_TTL_MATCHUP = 600  # 10 minutes

    def __init__(self) -> None:
        # Accept both env var naming conventions
        self.balldontlie_api_key: Optional[str] = (
            settings.BALLDONTLIE_API_KEY
            or getattr(settings, "BALL_DONT_LIE_API_KEY", None)
        )
        self.odds_api_key: Optional[str] = settings.THE_ODDS_API_KEY
        self._cache = TTLCache(default_ttl=300)
        self._current_season: int = self._resolve_current_season()
        logger.info("NBAStatsService initialized")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_current_season() -> int:
        """Return the NBA season year (e.g. 2025 for the 2025-26 season)."""
        today = datetime.utcnow()
        # NBA season starts in October; if we are before October, the
        # "current" season started last calendar year.
        return today.year if today.month >= 10 else today.year - 1

    def _bdl_headers(self) -> Dict[str, str]:
        """Return headers for balldontlie.io requests."""
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self.balldontlie_api_key:
            headers["Authorization"] = self.balldontlie_api_key
        return headers

    @property
    def is_available(self) -> bool:
        """Whether balldontlie.io API is configured (has API key)."""
        return bool(self.balldontlie_api_key)

    @staticmethod
    def _nba_season_str(season_year: int) -> str:
        """Convert season year int to nba_api season string.

        e.g. 2024 → "2024-25", 2025 → "2025-26"
        """
        return f"{season_year}-{str(season_year + 1)[2:]}"

    # ------------------------------------------------------------------
    # nba_api helpers (NBA.com — no API key, rate-limited ~1 req/sec)
    # ------------------------------------------------------------------

    async def _nba_api_player_id(self, name: str) -> Optional[int]:
        """Resolve a player name to their NBA.com player_id via nba_api.

        Uses nba_api.stats.static.players (local lookup, instant, no HTTP).
        Tries exact match first, then relaxed first+last name match.

        Args:
            name: Player full name e.g. "Cade Cunningham"

        Returns:
            NBA.com player_id (int) or None if not found.
        """
        if not _NBA_API_AVAILABLE:
            return None

        cache_key = f"nba_api_id:{name.lower().strip()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached if cached != -1 else None

        try:

            def _lookup() -> Optional[int]:
                # Exact match first
                results = nba_static_players.find_players_by_full_name(name)
                # Filter to active players
                active = [p for p in results if p.get("is_active")]
                if active:
                    return int(active[0]["id"])
                if results:
                    return int(results[0]["id"])

                # Fallback: search by last name only
                parts = name.strip().split()
                if len(parts) >= 2:
                    last = parts[-1]
                    first = parts[0]
                    all_players = nba_static_players.get_players()
                    matches = [
                        p
                        for p in all_players
                        if p.get("last_name", "").lower() == last.lower()
                        and p.get("first_name", "")
                        .lower()
                        .startswith(first[:3].lower())
                    ]
                    active_matches = [p for p in matches if p.get("is_active")]
                    if active_matches:
                        return int(active_matches[0]["id"])
                    if matches:
                        return int(matches[0]["id"])
                return None

            nba_id = await asyncio.to_thread(_lookup)

            if nba_id:
                logger.debug(f"nba_api player_id for '{name}': {nba_id}")
                self._cache.set(cache_key, nba_id, 86400)  # 24hr — IDs never change
                return nba_id
            else:
                logger.debug(f"nba_api: player not found: '{name}'")
                self._cache.set(cache_key, -1, 3600)  # cache miss for 1hr
                return None

        except Exception as exc:
            logger.error(f"nba_api player lookup failed for '{name}': {exc}")
            return None

    async def _nba_api_season_averages(
        self, nba_player_id: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch current-season per-game averages from NBA.com via nba_api.

        Args:
            nba_player_id: NBA.com player_id

        Returns:
            Dict with lowercase stat keys: pts, reb, ast, stl, blk, fg3m,
            turnover, min, fg_pct, fg3_pct, ft_pct, games_played. Or None.
        """
        if not _NBA_API_AVAILABLE:
            return None

        cache_key = f"nba_avg:{nba_player_id}:{self._current_season}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            season_str = self._nba_season_str(self._current_season)

            def _fetch() -> Optional[Dict[str, Any]]:
                await_secs = 0.6
                time.sleep(await_secs)  # NBA.com rate limit
                career = playercareerstats.PlayerCareerStats(
                    player_id=nba_player_id,
                    per_mode36="PerGame",
                    timeout=30,
                )
                df = career.season_totals_regular_season.get_data_frame()
                if df.empty:
                    return None

                # Filter to current season
                season_df = df[df["SEASON_ID"] == season_str]
                if season_df.empty:
                    # Fall back to most recent season
                    season_df = df.tail(1)

                row = season_df.iloc[-1].to_dict()

                # Normalize keys to lowercase and rename to our schema
                return {
                    "pts": float(row.get("PTS", 0) or 0),
                    "reb": float(row.get("REB", 0) or 0),
                    "ast": float(row.get("AST", 0) or 0),
                    "stl": float(row.get("STL", 0) or 0),
                    "blk": float(row.get("BLK", 0) or 0),
                    "fg3m": float(row.get("FG3M", 0) or 0),
                    "turnover": float(row.get("TOV", 0) or 0),
                    "min": float(str(row.get("MIN", 0) or 0).split(":")[0]),
                    "fg_pct": float(row.get("FG_PCT", 0) or 0),
                    "fg3_pct": float(row.get("FG3_PCT", 0) or 0),
                    "ft_pct": float(row.get("FT_PCT", 0) or 0),
                    "games_played": int(row.get("GP", 0) or 0),
                }

            result = await asyncio.to_thread(_fetch)

            if result:
                self._cache.set(cache_key, result, self.CACHE_TTL_SEASON_AVERAGES)
                logger.info(
                    f"nba_api season avgs for player {nba_player_id} "
                    f"({season_str}): pts={result.get('pts')}"
                )
            return result

        except Exception as exc:
            logger.error(
                f"nba_api season averages failed for player {nba_player_id}: {exc}"
            )
            return None

    async def _nba_api_game_logs(
        self,
        nba_player_id: int,
        last_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch per-game stats from NBA.com via nba_api.

        Args:
            nba_player_id: NBA.com player_id
            last_n: If set, return only the most recent N games.

        Returns:
            List of per-game stat dicts with lowercase keys matching
            the existing _extract_stat_values() schema.
            Most-recent game first.
        """
        if not _NBA_API_AVAILABLE:
            return []

        season_str = self._nba_season_str(self._current_season)
        cache_key = f"nba_logs:{nba_player_id}:{season_str}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached[:last_n] if last_n else cached

        try:

            def _fetch() -> List[Dict[str, Any]]:
                time.sleep(0.6)  # NBA.com rate limit
                gl = playergamelog.PlayerGameLog(
                    player_id=nba_player_id,
                    season=season_str,
                    timeout=30,
                )
                df = gl.player_game_log.get_data_frame()
                if df.empty:
                    return []

                logs: List[Dict[str, Any]] = []
                for _, row in df.iterrows():
                    _pts = float(row.get("PTS", 0) or 0)
                    _reb = float(row.get("REB", 0) or 0)
                    _ast = float(row.get("AST", 0) or 0)
                    _stl = float(row.get("STL", 0) or 0)
                    _blk = float(row.get("BLK", 0) or 0)
                    _fg3m = float(row.get("FG3M", 0) or 0)
                    _tov = float(row.get("TOV", 0) or 0)
                    _matchup = str(row.get("MATCHUP", ""))
                    logs.append(
                        {
                            # Core stats — lowercase to match _extract_stat_values()
                            "pts": _pts,
                            "reb": _reb,
                            "ast": _ast,
                            "stl": _stl,
                            "blk": _blk,
                            "fg3m": _fg3m,
                            "turnover": _tov,
                            "min": float(str(row.get("MIN", "0")).split(":")[0]),
                            # Pre-computed combo stats for EVCalculator hit-rate windows
                            "pra": _pts + _reb + _ast,
                            "p+r": _pts + _reb,
                            "p+a": _pts + _ast,
                            "r+a": _reb + _ast,
                            "s+b": _stl + _blk,
                            # Game metadata
                            "game_date": str(row.get("GAME_DATE", "")),
                            "matchup": _matchup,
                            "wl": str(row.get("WL", "")),
                            # Home if "vs." in matchup (home), "@" means away
                            "is_home": "@" not in _matchup,
                            # Balldontlie-compatible dicts for compute_* methods
                            "game": {
                                "date": str(row.get("GAME_DATE", "")),
                                "home_team_id": (
                                    nba_player_id if "@" not in _matchup else -1
                                ),
                            },
                            "team": {"id": nba_player_id},
                        }
                    )

                # Most-recent first (DataFrame is already sorted this way by NBA.com)
                return logs

            logs = await asyncio.to_thread(_fetch)

            if logs:
                self._cache.set(cache_key, logs, self.CACHE_TTL_GAME_LOGS)
                logger.info(
                    f"nba_api game logs for player {nba_player_id} "
                    f"({season_str}): {len(logs)} games"
                )

            return logs[:last_n] if last_n else logs

        except Exception as exc:
            logger.error(f"nba_api game logs failed for player {nba_player_id}: {exc}")
            return []

    async def _nba_api_all_team_stats(self) -> Dict[str, Dict[str, Any]]:
        """Fetch advanced team stats (pace, off_rating, def_rating) for all 30 teams.

        Single NBA.com call covers all teams. Cached 30 minutes.

        Returns:
            Dict keyed by team abbreviation → {pace, off_rating, def_rating,
            team_name, team_id}
        """
        if not _NBA_API_AVAILABLE:
            return {}

        season_str = self._nba_season_str(self._current_season)
        cache_key = f"nba_team_stats:{season_str}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:

            def _fetch() -> Dict[str, Dict[str, Any]]:
                time.sleep(0.6)
                stats = leaguedashteamstats.LeagueDashTeamStats(
                    measure_type_detailed_defense="Advanced",
                    per_mode_detailed="PerGame",
                    season=season_str,
                    timeout=30,
                )
                df = stats.league_dash_team_stats.get_data_frame()
                if df.empty:
                    return {}

                # Build abbrev lookup from nba_api static teams (instant, local)
                team_abbrev_map: Dict[int, str] = {}
                try:
                    for t in nba_static_teams.get_teams():
                        team_abbrev_map[int(t["id"])] = t["abbreviation"]
                except Exception:
                    pass

                result: Dict[str, Dict[str, Any]] = {}
                for _, row in df.iterrows():
                    tid = int(row.get("TEAM_ID", 0) or 0)
                    abbrev = team_abbrev_map.get(
                        tid, str(row.get("TEAM_ABBREVIATION", "") or "")
                    )
                    if not abbrev:
                        continue
                    result[abbrev] = {
                        "team_id": tid,
                        "team_name": str(row.get("TEAM_NAME", "")),
                        "pace": float(row.get("PACE", 100.0) or 100.0),
                        "off_rating": float(row.get("OFF_RATING", 113.0) or 113.0),
                        "def_rating": float(row.get("DEF_RATING", 113.0) or 113.0),
                        "net_rating": float(row.get("NET_RATING", 0.0) or 0.0),
                    }
                return result

            team_stats = await asyncio.to_thread(_fetch)

            if team_stats:
                self._cache.set(cache_key, team_stats, 1800)  # 30min
                logger.info(
                    f"nba_api team stats: {len(team_stats)} teams ({season_str})"
                )

            return team_stats

        except Exception as exc:
            logger.error(f"nba_api team stats failed: {exc}")
            return {}

    async def _bdl_get(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GET against the balldontlie API with standard error handling.

        Returns empty dict if no API key is configured (graceful degradation).
        """
        if not self.balldontlie_api_key:
            logger.debug(f"Skipping balldontlie request {path} — no API key configured")
            return {"data": []}

        url = f"{self.BALLDONTLIE_BASE}{path}"
        response = await client.get(
            url,
            params=params or {},
            headers=self._bdl_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Player search
    # ------------------------------------------------------------------

    async def search_player(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Search for an NBA player by name.

        Strategy: Search by last name (balldontlie partial match works best
        on single tokens), then filter results by first name to find the
        exact player.  Falls back to first-name search if last-name yields
        nothing.

        Args:
            name: Player name (e.g. "LeBron James", "Cade Cunningham")

        Returns:
            Player dict with id, first_name, last_name, team, position, etc.
            or None if not found.
        """
        cache_key = f"player_search:{name.lower().strip()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        parts = name.strip().split()
        if not parts:
            return None

        # Determine first/last name tokens for filtering
        first_token = parts[0].lower()
        last_token = parts[-1].lower() if len(parts) > 1 else ""

        # Search by last name first (more unique), fallback to first name
        search_terms = []
        if last_token:
            search_terms.append(last_token)
        search_terms.append(first_token)

        try:
            async with httpx.AsyncClient() as client:
                for term in search_terms:
                    data = await self._bdl_get(
                        client, "/players", {"search": term, "per_page": 25}
                    )
                    players = data.get("data", [])

                    if not players:
                        continue

                    # If we have both first and last, filter for exact match
                    if first_token and last_token:
                        for p in players:
                            p_first = (p.get("first_name") or "").lower()
                            p_last = (p.get("last_name") or "").lower()
                            if p_first == first_token and p_last == last_token:
                                self._cache.set(
                                    cache_key, p, self.CACHE_TTL_PLAYER_SEARCH
                                )
                                logger.info(
                                    f"Found player: {p.get('first_name')} "
                                    f"{p.get('last_name')} (id={p.get('id')})"
                                )
                                return p

                        # Relaxed match: first name starts with token
                        for p in players:
                            p_first = (p.get("first_name") or "").lower()
                            p_last = (p.get("last_name") or "").lower()
                            if (
                                p_first.startswith(first_token[:3])
                                and p_last == last_token
                            ):
                                self._cache.set(
                                    cache_key, p, self.CACHE_TTL_PLAYER_SEARCH
                                )
                                logger.info(
                                    f"Found player (relaxed): "
                                    f"{p.get('first_name')} {p.get('last_name')} "
                                    f"(id={p.get('id')})"
                                )
                                return p
                    else:
                        # Single name — return first result
                        player = players[0]
                        self._cache.set(cache_key, player, self.CACHE_TTL_PLAYER_SEARCH)
                        return player

            logger.debug(f"No player found for: {name}")
            # Cache the miss to avoid repeated lookups
            self._cache.set(cache_key, None, 300)
            return None

        except httpx.HTTPStatusError as exc:
            logger.error(
                f"HTTP error searching player '{name}': {exc.response.status_code}"
            )
            return None
        except Exception as exc:
            logger.error(f"Error searching player '{name}': {exc}")
            return None

    # ------------------------------------------------------------------
    # Season averages
    # ------------------------------------------------------------------

    async def get_season_averages(
        self,
        player_id: int,
        season: Optional[int] = None,
        nba_api_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch season averages for a player.

        Waterfall:
            1. balldontlie (works on paid tier)
            2. nba_api / NBA.com (free, no key) — primary for free tier

        Args:
            player_id: balldontlie player id
            season: Season year (defaults to current)
            nba_api_id: NBA.com player_id for nba_api fallback

        Returns:
            Dict with: pts, reb, ast, stl, blk, fg3m, turnover, min,
            fg_pct, fg3_pct, ft_pct, games_played. Or None.
        """
        season = season or self._current_season

        # Try balldontlie first (works on paid tier)
        try:
            async with httpx.AsyncClient() as client:
                data = await self._bdl_get(
                    client,
                    "/season_averages",
                    {"season": season, "player_ids[]": player_id},
                )
            averages = data.get("data", [])
            if averages:
                result = averages[0]
                self._cache.set(
                    f"season_avg:{player_id}:{season}",
                    result,
                    self.CACHE_TTL_SEASON_AVERAGES,
                )
                logger.info(
                    f"balldontlie season averages for player_id={player_id} ({season})"
                )
                return result
        except Exception:
            pass  # Fall through to nba_api

        # nba_api fallback
        if nba_api_id:
            return await self._nba_api_season_averages(nba_api_id)

        logger.warning(
            f"No season averages available for player_id={player_id} "
            f"(balldontlie failed, no nba_api_id)"
        )
        return None

    # ------------------------------------------------------------------
    # Game logs
    # ------------------------------------------------------------------

    async def get_game_logs(
        self,
        player_id: int,
        season: Optional[int] = None,
        last_n: Optional[int] = None,
        nba_api_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch game logs for a player.

        Waterfall:
            1. nba_api / NBA.com (primary — free, reliable)
            2. balldontlie (fallback — only works on paid tier)

        Args:
            player_id: balldontlie player id (used for cache key + bdl fallback)
            season: NBA season year (defaults to current)
            last_n: If set, return only the most recent N games
            nba_api_id: NBA.com player_id (primary source)

        Returns:
            List of per-game dicts sorted most-recent first.
            Keys: pts, reb, ast, stl, blk, fg3m, turnover, min,
                  game_date, matchup, wl, is_home, game{}, team{}
        """
        season = season or self._current_season

        # Primary: nba_api
        if nba_api_id:
            logs = await self._nba_api_game_logs(nba_api_id, last_n)
            if logs:
                return logs

        # Fallback: balldontlie (paid tier)
        logs = await self._fetch_all_game_logs_bdl(player_id, season)
        if logs:
            logs.sort(key=lambda g: g.get("game", {}).get("date", ""), reverse=True)
        return logs[:last_n] if last_n else logs

    async def _fetch_all_game_logs_bdl(
        self, player_id: int, season: int
    ) -> List[Dict[str, Any]]:
        """Paginate balldontlie /stats endpoint (fallback, requires paid tier)."""
        all_logs: List[Dict[str, Any]] = []
        page = 1
        per_page = 100

        try:
            async with httpx.AsyncClient() as client:
                while True:
                    data = await self._bdl_get(
                        client,
                        "/stats",
                        {
                            "seasons[]": season,
                            "player_ids[]": player_id,
                            "per_page": per_page,
                            "page": page,
                        },
                    )
                    page_data = data.get("data", [])
                    all_logs.extend(page_data)
                    meta = data.get("meta", {})
                    next_page = meta.get("next_page")
                    if next_page is None or not page_data:
                        break
                    page = next_page

            logger.info(
                f"balldontlie: {len(all_logs)} game logs for "
                f"player_id={player_id} ({season})"
            )
        except httpx.HTTPStatusError as exc:
            logger.debug(
                f"balldontlie game logs HTTP {exc.response.status_code} "
                f"for player_id={player_id} (likely free tier limit)"
            )
        except Exception as exc:
            logger.error(
                f"balldontlie game logs error for player_id={player_id}: {exc}"
            )

        return all_logs

    # ------------------------------------------------------------------
    # Rolling averages & splits
    # ------------------------------------------------------------------

    def compute_rolling_averages(
        self,
        game_logs: List[Dict[str, Any]],
        stat_keys: List[str],
        windows: Optional[List[int]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute rolling averages over the given windows.

        Args:
            game_logs: Game logs sorted most-recent first.
            stat_keys: List of stat field names to average (e.g. ["pts", "reb"]).
            windows: List of window sizes (default [5, 10, 20]).

        Returns:
            e.g. {"L5": {"pts": 28.4, "reb": 7.2}, "L10": {...}, ...}
        """
        if windows is None:
            windows = [5, 10, 20]

        result: Dict[str, Dict[str, float]] = {}
        for w in windows:
            window_logs = game_logs[:w]
            if not window_logs:
                result[f"L{w}"] = {k: 0.0 for k in stat_keys}
                continue

            avgs: Dict[str, float] = {}
            for key in stat_keys:
                values = self._extract_stat_values(window_logs, key)
                avgs[key] = round(sum(values) / len(values), 2) if values else 0.0
            result[f"L{w}"] = avgs

        return result

    def compute_hit_rates(
        self,
        game_logs: List[Dict[str, Any]],
        stat_keys: List[str],
        line: float,
        windows: Optional[List[int]] = None,
    ) -> Dict[str, float]:
        """
        Calculate the fraction of games where the combined stat total went
        OVER *line* for the given windows plus the full season.

        Args:
            game_logs: Game logs sorted most-recent first.
            stat_keys: Stat field names that are summed per game.
            line: The prop line number.
            windows: Rolling windows (default [5, 10, 20]).

        Returns:
            e.g. {"L5": 0.80, "L10": 0.70, "L20": 0.65, "season": 0.62}
        """
        if windows is None:
            windows = [5, 10, 20]

        def _rate(logs: List[Dict[str, Any]]) -> float:
            if not logs:
                return 0.0
            overs = 0
            for log in logs:
                total = sum(self._extract_single_stat(log, k) for k in stat_keys)
                if total > line:
                    overs += 1
            return round(overs / len(logs), 4)

        result: Dict[str, float] = {}
        for w in windows:
            result[f"L{w}"] = _rate(game_logs[:w])
        result["season"] = _rate(game_logs)
        return result

    def compute_home_away_splits(
        self,
        game_logs: List[Dict[str, Any]],
        stat_keys: List[str],
        player_team_id: Optional[int] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Split game logs into home and away buckets and compute averages.

        Returns:
            {"home": {"pts": 29.1, ...}, "away": {"pts": 26.3, ...}}
        """
        home_logs: List[Dict[str, Any]] = []
        away_logs: List[Dict[str, Any]] = []

        for log in game_logs:
            game = log.get("game", {})
            home_team_id = game.get("home_team_id")
            team = log.get("team", {})
            team_id = team.get("id") or player_team_id

            if team_id is not None and home_team_id == team_id:
                home_logs.append(log)
            else:
                away_logs.append(log)

        def _avg(logs: List[Dict[str, Any]]) -> Dict[str, float]:
            if not logs:
                return {k: 0.0 for k in stat_keys}
            avgs: Dict[str, float] = {}
            for key in stat_keys:
                values = self._extract_stat_values(logs, key)
                avgs[key] = round(sum(values) / len(values), 2) if values else 0.0
            return avgs

        return {
            "home": _avg(home_logs),
            "away": _avg(away_logs),
            "home_games": len(home_logs),
            "away_games": len(away_logs),
        }

    def compute_vs_team_history(
        self,
        game_logs: List[Dict[str, Any]],
        stat_keys: List[str],
        opponent_team_id: int,
    ) -> Dict[str, Any]:
        """
        Filter game logs to matchups against a specific opponent team and
        return averages plus individual game totals.

        Returns:
            {"avg": {"pts": 31.5, ...}, "games": 4, "game_totals": [...]}
        """
        matched: List[Dict[str, Any]] = []
        for log in game_logs:
            game = log.get("game", {})
            home_id = game.get("home_team_id")
            visitor_id = game.get("visitor_team_id")
            player_team = log.get("team", {}).get("id")

            # The opponent is whichever team is *not* the player's team
            if player_team == home_id and visitor_id == opponent_team_id:
                matched.append(log)
            elif player_team == visitor_id and home_id == opponent_team_id:
                matched.append(log)

        if not matched:
            return {"avg": {k: 0.0 for k in stat_keys}, "games": 0, "game_totals": []}

        avgs: Dict[str, float] = {}
        game_totals: List[Dict[str, float]] = []
        for key in stat_keys:
            values = self._extract_stat_values(matched, key)
            avgs[key] = round(sum(values) / len(values), 2) if values else 0.0

        for log in matched:
            total: Dict[str, float] = {}
            for key in stat_keys:
                total[key] = self._extract_single_stat(log, key)
            game_totals.append(total)

        return {"avg": avgs, "games": len(matched), "game_totals": game_totals}

    # ------------------------------------------------------------------
    # Team stats (pace, offensive/defensive rating)
    # ------------------------------------------------------------------

    async def get_team_stats(
        self,
        team_id: int,
        team_abbreviation: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch team-level advanced stats: pace, off_rating, def_rating.

        Waterfall:
            1. nba_api LeagueDashTeamStats (real pace/ratings from NBA.com)
            2. balldontlie /teams/{id} (basic info only, no advanced stats)

        Args:
            team_id: balldontlie team id
            team_abbreviation: Optional abbreviation e.g. "DET" for faster lookup

        Returns:
            Dict with pace, off_rating, def_rating, team_name. Or None.
        """
        cache_key = f"team_stats:{team_id}:{self._current_season}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Primary: nba_api advanced stats (all teams in one call)
        all_team_stats = await self._nba_api_all_team_stats()
        if all_team_stats:
            # Look up by abbreviation if provided
            if team_abbreviation and team_abbreviation.upper() in all_team_stats:
                result = all_team_stats[team_abbreviation.upper()]
                self._cache.set(cache_key, result, self.CACHE_TTL_TEAM_STATS)
                return result

            # Look up by team_id
            for abbrev, stats in all_team_stats.items():
                if stats.get("team_id") == team_id:
                    self._cache.set(cache_key, stats, self.CACHE_TTL_TEAM_STATS)
                    return stats

        # Fallback: balldontlie basic team info (no advanced stats)
        try:
            async with httpx.AsyncClient() as client:
                data = await self._bdl_get(client, f"/teams/{team_id}")
            team_info = data if "id" in data else data.get("data", data)
            result = {
                "team_id": team_info.get("id"),
                "team_name": team_info.get("full_name"),
                "abbreviation": team_info.get("abbreviation"),
                "conference": team_info.get("conference"),
                "pace": 100.0,  # default league average
                "off_rating": 113.0,
                "def_rating": 113.0,
            }
            self._cache.set(cache_key, result, self.CACHE_TTL_TEAM_STATS)
            return result
        except Exception as exc:
            logger.error(f"get_team_stats failed for team_id={team_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Matchup / defensive data
    # ------------------------------------------------------------------

    async def get_matchup_data(
        self,
        opponent_team_id: int,
        player_position: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gather matchup-relevant defensive data for the opponent team.

        Includes team defensive rating placeholder and positional context.
        """
        cache_key = (
            f"matchup:{opponent_team_id}:{player_position}:{self._current_season}"
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        team_stats = await self.get_team_stats(opponent_team_id)

        result: Dict[str, Any] = {
            "opponent_team": team_stats.get("name") if team_stats else None,
            "opponent_abbreviation": team_stats.get("abbreviation")
            if team_stats
            else None,
            "def_rating": team_stats.get("def_rating") if team_stats else None,
            "pace": team_stats.get("pace") if team_stats else None,
            "player_position": player_position,
            # Placeholder: defensive ranking vs position
            "position_def_rank": None,
            "position_def_rating": None,
        }

        self._cache.set(cache_key, result, self.CACHE_TTL_MATCHUP)
        return result

    # ------------------------------------------------------------------
    # Injury reports
    # ------------------------------------------------------------------

    async def get_injury_report(
        self,
        team_abbreviation: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch current NBA injury report.

        Uses the-odds-api.com injuries endpoint when available, falling back
        to an empty list if the key is missing.

        Args:
            team_abbreviation: Optional filter (e.g. "LAL").

        Returns:
            List of injury dicts with player_name, team, status, description.
        """
        cache_key = f"injuries:{team_abbreviation or 'all'}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.odds_api_key:
            logger.warning(
                "THE_ODDS_API_KEY not configured; cannot fetch injury report"
            )
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.ODDS_API_BASE}/sports/basketball_nba/injuries",
                    params={"apiKey": self.odds_api_key},
                    timeout=30.0,
                )
                response.raise_for_status()
                raw_injuries = response.json()

            injuries: List[Dict[str, Any]] = []
            for entry in raw_injuries if isinstance(raw_injuries, list) else []:
                player_injuries = entry.get("injuries", [])
                team = entry.get("team", "")
                for inj in player_injuries:
                    record = {
                        "player_name": inj.get("player", ""),
                        "team": team,
                        "status": inj.get("status", ""),
                        "description": inj.get("description", ""),
                    }
                    if (
                        team_abbreviation is None
                        or team.upper() == team_abbreviation.upper()
                    ):
                        injuries.append(record)

            self._cache.set(cache_key, injuries, self.CACHE_TTL_INJURY)
            logger.info(
                f"Fetched {len(injuries)} injury entries"
                f"{' for ' + team_abbreviation if team_abbreviation else ''}"
            )
            return injuries

        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP error fetching injuries: {exc.response.status_code}")
            return []
        except Exception as exc:
            logger.error(f"Error fetching injury report: {exc}")
            return []

    # ------------------------------------------------------------------
    # Prop-relevant aggregate helper
    # ------------------------------------------------------------------

    async def get_player_prop_research(
        self,
        player_name: str,
        prop_type: str,
        line: float,
        opponent_team_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        High-level convenience method: given a player name and prop type,
        return a research bundle with season averages, rolling averages,
        hit rates, splits, and matchup data.

        Args:
            player_name: Full player name.
            prop_type: One of the keys in PROP_STAT_KEYS.
            line: The prop line number.
            opponent_team_id: Optional opponent team id for matchup data.

        Returns:
            Comprehensive research dict.
        """
        stat_keys = PROP_STAT_KEYS.get(prop_type, [prop_type])

        # Resolve both IDs in parallel: balldontlie (team/position) + NBA.com (stats)
        player, nba_api_id = await asyncio.gather(
            self.search_player(player_name),
            self._nba_api_player_id(player_name),
        )

        if player is None and nba_api_id is None:
            return {"error": f"Player not found: {player_name}"}

        # Use balldontlie metadata if available, else minimal stub
        player_id: int = player["id"] if player else 0
        player_team = (player or {}).get("team", {}) or {}
        player_team_id: Optional[int] = player_team.get("id") if player_team else None
        player_position: Optional[str] = (player or {}).get("position")
        team_abbreviation: Optional[str] = (
            player_team.get("abbreviation") if player_team else None
        )

        # Fetch season averages + game logs — nba_api primary, balldontlie fallback
        season_avg = await self.get_season_averages(player_id, nba_api_id=nba_api_id)
        game_logs = await self.get_game_logs(player_id, nba_api_id=nba_api_id)

        # Rolling averages
        rolling = self.compute_rolling_averages(game_logs, stat_keys)

        # Hit rates
        hit_rates = self.compute_hit_rates(game_logs, stat_keys, line)

        # Home/away splits
        splits = self.compute_home_away_splits(game_logs, stat_keys, player_team_id)

        # Vs-team history
        vs_team: Optional[Dict[str, Any]] = None
        if opponent_team_id is not None:
            vs_team = self.compute_vs_team_history(
                game_logs, stat_keys, opponent_team_id
            )

        # Matchup data
        matchup: Optional[Dict[str, Any]] = None
        if opponent_team_id is not None:
            matchup = await self.get_matchup_data(opponent_team_id, player_position)

        # Injuries for player's team
        injuries = await self.get_injury_report(team_abbreviation)

        return {
            "player": {
                "id": player_id,
                "name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                "team": player_team.get("full_name") if player_team else None,
                "team_abbreviation": team_abbreviation,
                "position": player_position,
            },
            "prop_type": prop_type,
            "stat_keys": stat_keys,
            "line": line,
            "season_averages": season_avg,
            "game_logs": game_logs,  # Raw per-game stats for EVCalculator
            "rolling_averages": rolling,
            "hit_rates": hit_rates,
            "home_away_splits": splits,
            "vs_team_history": vs_team,
            "matchup_data": matchup,
            "team_injuries": injuries,
            "games_played": len(game_logs),
            "season": self._current_season,
        }

    # ------------------------------------------------------------------
    # Private stat-extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_stat_values(game_logs: List[Dict[str, Any]], key: str) -> List[float]:
        """Extract a list of numeric values for *key* from a list of game logs."""
        values: List[float] = []
        for log in game_logs:
            val = log.get(key)
            if val is None:
                continue
            # Minutes field may be returned as "32:15" string
            if isinstance(val, str):
                try:
                    if ":" in val:
                        parts = val.split(":")
                        val = float(parts[0]) + float(parts[1]) / 60.0
                    else:
                        val = float(val)
                except (ValueError, IndexError):
                    continue
            values.append(float(val))
        return values

    @staticmethod
    def _extract_single_stat(log: Dict[str, Any], key: str) -> float:
        """Extract a single numeric stat value from one game log entry."""
        val = log.get(key, 0)
        if val is None:
            return 0.0
        if isinstance(val, str):
            try:
                if ":" in val:
                    parts = val.split(":")
                    return float(parts[0]) + float(parts[1]) / 60.0
                return float(val)
            except (ValueError, IndexError):
                return 0.0
        return float(val)
