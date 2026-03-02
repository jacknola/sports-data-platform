"""
Team Schedule Context model.

Stores per-game scheduling and travel context for each team so that
rest/fatigue features are always read from the database — never mocked.

Populated by the schedule_context_service which derives these values
from the Game table using the nba_api schedule feed.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from app.database import Base
from datetime import datetime, timezone


class TeamScheduleContext(Base):
    """
    One row per (team, game) pair.

    REST / FATIGUE
    ──────────────
    rest_days            Days since the team's previous game (0 = back-to-back).
    is_back_to_back      True when rest_days == 0.
    games_in_last_7      Number of games in the 7-day window ending today.
    games_in_last_14     Number of games in the 14-day window ending today.

    TRAVEL
    ──────
    travel_distance_km   Great-circle distance from the previous game's arena.
    time_zone_shift      Hours of time-zone change vs. previous game (signed).
    is_road_game         True when this is an away game.
    road_game_streak     Consecutive road games ending at this one.

    PROVENANCE
    ──────────
    source               'nba_api_schedule' | 'derived' | 'manual'
    """

    __tablename__ = "team_schedule_context"
    __table_args__ = (
        UniqueConstraint("team_id", "game_id", name="uq_team_game_schedule"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)

    # Foreign keys
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)

    # Game date (denormalised for fast range queries without join)
    game_date = Column(DateTime, nullable=False, index=True)
    sport = Column(String, nullable=False, default="nba", index=True)

    # Rest / fatigue
    rest_days = Column(Integer, nullable=True)
    is_back_to_back = Column(Boolean, nullable=False, default=False)
    games_in_last_7 = Column(Integer, nullable=True)
    games_in_last_14 = Column(Integer, nullable=True)

    # Travel
    travel_distance_km = Column(Float, nullable=True)
    time_zone_shift = Column(Float, nullable=True)   # hours, signed (+/-UTC)
    is_road_game = Column(Boolean, nullable=False, default=False)
    road_game_streak = Column(Integer, nullable=True, default=0)

    # Provenance
    source = Column(String, nullable=False, default="derived")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
