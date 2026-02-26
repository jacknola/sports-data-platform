"""
Historical betting lines model
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from app.database import Base
from datetime import datetime, timezone


class HistoricalGameLine(Base):
    __tablename__ = "historical_game_lines"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Game identifiers
    game_date = Column(DateTime, index=True)
    season = Column(Integer, index=True)

    home_team = Column(String, index=True)
    away_team = Column(String, index=True)

    # Results
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    total_score = Column(Integer, nullable=True)
    margin = Column(Integer, nullable=True)

    # Pre-game lines (closing)
    home_ml = Column(Integer, nullable=True)
    away_ml = Column(Integer, nullable=True)
    home_spread = Column(Float, nullable=True)
    away_spread = Column(Float, nullable=True)
    spread_odds = Column(Integer, nullable=True)
    over_under = Column(Float, nullable=True)
    over_odds = Column(Integer, nullable=True)
    under_odds = Column(Integer, nullable=True)

    # Opening lines (if available)
    open_home_ml = Column(Integer, nullable=True)
    open_away_ml = Column(Integer, nullable=True)
    open_home_spread = Column(Float, nullable=True)
    open_away_spread = Column(Float, nullable=True)
    open_over_under = Column(Float, nullable=True)

    # CLV (Closing Line Value)
    clv_spread = Column(Float, nullable=True)
    clv_total = Column(Float, nullable=True)
    clv_ml = Column(Integer, nullable=True)

    # Source metadata
    source = Column(String)  # 'balldontlie', 'kaggle', 'covers', 'sportsgamesodds'
    external_game_id = Column(String, index=True)
    external_line_id = Column(String, unique=True)

    # Raw data storage
    raw_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
