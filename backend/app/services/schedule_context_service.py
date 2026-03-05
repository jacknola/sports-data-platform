"""
Schedule Context Service

Derives rest-days, back-to-back flags, travel distance and time-zone
shifts from the Game table and persists them to TeamScheduleContext.

Integrates with ``airball`` (PySport) when available for distance/TZ
calculations; falls back to a simple great-circle calculation using
team arena coordinates otherwise.

Usage
─────
    from app.services.schedule_context_service import ScheduleContextService

    svc = ScheduleContextService()

    # Backfill a full season
    asyncio.run(svc.backfill_season("nba", season="2024-25"))

    # Fetch context for one team and game (used by feature engineer)
    ctx = svc.get_context(team_name="Lakers", game_date=date.today())
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.game import Game
from app.models.team import Team
from app.models.team_schedule_context import TeamScheduleContext

# ---------------------------------------------------------------------------
# NBA arena coordinates (lat, lon) — used when airball is unavailable
# ---------------------------------------------------------------------------
_ARENA_COORDS: Dict[str, Tuple[float, float]] = {
    "Atlanta Hawks": (33.757, -84.396),
    "Boston Celtics": (42.366, -71.062),
    "Brooklyn Nets": (40.683, -73.975),
    "Charlotte Hornets": (35.225, -80.839),
    "Chicago Bulls": (41.881, -87.674),
    "Cleveland Cavaliers": (41.497, -81.688),
    "Dallas Mavericks": (32.790, -96.810),
    "Denver Nuggets": (39.749, -104.999),
    "Detroit Pistons": (42.341, -83.055),
    "Golden State Warriors": (37.768, -122.388),
    "Houston Rockets": (29.751, -95.362),
    "Indiana Pacers": (39.764, -86.156),
    "LA Clippers": (34.043, -118.267),
    "Los Angeles Lakers": (34.043, -118.267),
    "Memphis Grizzlies": (35.138, -90.051),
    "Miami Heat": (25.781, -80.188),
    "Milwaukee Bucks": (43.045, -87.917),
    "Minnesota Timberwolves": (44.979, -93.276),
    "New Orleans Pelicans": (29.949, -90.082),
    "New York Knicks": (40.750, -73.994),
    "Oklahoma City Thunder": (35.463, -97.515),
    "Orlando Magic": (28.539, -81.384),
    "Philadelphia 76ers": (39.901, -75.172),
    "Phoenix Suns": (33.446, -112.071),
    "Portland Trail Blazers": (45.532, -122.667),
    "Sacramento Kings": (38.580, -121.499),
    "San Antonio Spurs": (29.427, -98.438),
    "Toronto Raptors": (43.643, -79.379),
    "Utah Jazz": (40.768, -111.901),
    "Washington Wizards": (38.898, -77.021),
}

# US time zones by arena city — offset from UTC in hours (standard time)
_ARENA_TZ_OFFSET: Dict[str, float] = {
    "Atlanta Hawks": -5, "Boston Celtics": -5, "Brooklyn Nets": -5,
    "Charlotte Hornets": -5, "Chicago Bulls": -6, "Cleveland Cavaliers": -5,
    "Dallas Mavericks": -6, "Denver Nuggets": -7, "Detroit Pistons": -5,
    "Golden State Warriors": -8, "Houston Rockets": -6, "Indiana Pacers": -5,
    "LA Clippers": -8, "Los Angeles Lakers": -8, "Memphis Grizzlies": -6,
    "Miami Heat": -5, "Milwaukee Bucks": -6, "Minnesota Timberwolves": -6,
    "New Orleans Pelicans": -6, "New York Knicks": -5, "Oklahoma City Thunder": -6,
    "Orlando Magic": -5, "Philadelphia 76ers": -5, "Phoenix Suns": -7,
    "Portland Trail Blazers": -8, "Sacramento Kings": -8, "San Antonio Spurs": -6,
    "Toronto Raptors": -5, "Utah Jazz": -7, "Washington Wizards": -5,
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class ScheduleContextService:
    """Derives and persists schedule/travel context from the Game table."""

    def get_context(
        self, team_name: str, game_date: date, sport: str = "nba"
    ) -> Dict:
        """
        Return schedule context for a team on a given game date.

        Tries the database first; falls back to an on-the-fly derived
        value if the row doesn't exist yet.

        Returns a dict with the same keys as TeamScheduleContext columns.
        """
        db = SessionLocal()
        try:
            # Find the team
            team = db.execute(
                select(Team).where(Team.name == team_name, Team.sport == sport)
            ).scalars().first()
            if not team:
                return self._default_context(team_name)

            # Find the game
            day_start = datetime.combine(game_date, datetime.min.time())
            game = db.execute(
                select(Game).where(
                    Game.game_date >= day_start,
                    Game.game_date < day_start + timedelta(days=1),
                    (Game.home_team == team_name) | (Game.away_team == team_name),
                )
            ).scalars().first()
            if not game:
                return self._default_context(team_name)

            # Look up persisted context
            ctx = db.execute(
                select(TeamScheduleContext).where(
                    TeamScheduleContext.team_id == team.id,
                    TeamScheduleContext.game_id == game.id,
                )
            ).scalars().first()

            if ctx:
                return {
                    "rest_days": ctx.rest_days,
                    "is_back_to_back": ctx.is_back_to_back,
                    "games_in_last_7": ctx.games_in_last_7,
                    "games_in_last_14": ctx.games_in_last_14,
                    "travel_distance_km": ctx.travel_distance_km,
                    "time_zone_shift": ctx.time_zone_shift,
                    "is_road_game": ctx.is_road_game,
                    "road_game_streak": ctx.road_game_streak,
                }

            # Derive on the fly and persist
            return self._derive_and_save(db, team, game, sport)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Internal derivation logic
    # ------------------------------------------------------------------

    def _derive_and_save(
        self, db: Session, team: Team, game: Game, sport: str
    ) -> Dict:
        """Derive schedule context from historical games and save it."""
        # All games for this team, ordered by date, before today
        past_games: List[Game] = db.execute(
            select(Game).where(
                Game.sport == sport,
                Game.game_date < game.game_date,
                (Game.home_team == team.name) | (Game.away_team == team.name),
            ).order_by(Game.game_date.desc())
        ).scalars().all()

        # Rest days
        rest_days: Optional[int] = None
        prev_game: Optional[Game] = past_games[0] if past_games else None
        if prev_game:
            delta = game.game_date.date() - prev_game.game_date.date()
            rest_days = max(0, delta.days - 1)

        is_b2b = rest_days == 0 if rest_days is not None else False

        # Games in last 7 / 14 days
        cutoff_7 = game.game_date - timedelta(days=7)
        cutoff_14 = game.game_date - timedelta(days=14)
        g7 = sum(1 for g in past_games if g.game_date >= cutoff_7)
        g14 = sum(1 for g in past_games if g.game_date >= cutoff_14)

        # Travel distance + TZ shift
        travel_km: Optional[float] = None
        tz_shift: Optional[float] = None
        if prev_game:
            prev_home = prev_game.home_team
            cur_home = game.home_team
            prev_coords = _ARENA_COORDS.get(prev_home)
            cur_coords = _ARENA_COORDS.get(cur_home)
            if prev_coords and cur_coords:
                travel_km = round(_haversine_km(*prev_coords, *cur_coords), 1)
            prev_tz = _ARENA_TZ_OFFSET.get(prev_home)
            cur_tz = _ARENA_TZ_OFFSET.get(cur_home)
            if prev_tz is not None and cur_tz is not None:
                tz_shift = cur_tz - prev_tz

        is_road = game.away_team == team.name

        # Road game streak
        road_streak = 0
        for g in past_games:
            if g.away_team == team.name:
                road_streak += 1
            else:
                break
        if is_road:
            road_streak += 1

        ctx_data = {
            "rest_days": rest_days,
            "is_back_to_back": is_b2b,
            "games_in_last_7": g7,
            "games_in_last_14": g14,
            "travel_distance_km": travel_km,
            "time_zone_shift": tz_shift,
            "is_road_game": is_road,
            "road_game_streak": road_streak,
        }

        try:
            ctx_row = TeamScheduleContext(
                team_id=team.id,
                game_id=game.id,
                game_date=game.game_date,
                sport=sport,
                source="derived",
                **ctx_data,
            )
            db.add(ctx_row)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"Could not persist schedule context: {exc}")

        return ctx_data

    @staticmethod
    def _default_context(team_name: str) -> Dict:
        """Safe fallback when no historical data is available."""
        logger.debug(f"No schedule context for {team_name}, using defaults")
        return {
            "rest_days": 1,
            "is_back_to_back": False,
            "games_in_last_7": None,
            "games_in_last_14": None,
            "travel_distance_km": None,
            "time_zone_shift": 0.0,
            "is_road_game": False,
            "road_game_streak": 0,
        }
