"""
Historical player prop lines model
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON
from app.database import Base
from datetime import datetime, timezone


class HistoricalPlayerProp(Base):
    __tablename__ = "historical_player_props"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)


    # Player/Game identifiers
    player_name = Column(String, index=True)
    player_id = Column(Integer, index=True, nullable=True)
    team = Column(String, index=True)
    opponent = Column(String)
    game_date = Column(DateTime, index=True)
    season = Column(Integer, index=True)

    # Prop type
    prop_type = Column(String, index=True)  # points, rebounds, assists, etc.
    stat_type = Column(String)  # 'over' or 'under'

    # Line and odds
    line = Column(Float)
    over_odds = Column(Integer, nullable=True)
    under_odds = Column(Integer, nullable=True)
    over_price = Column(Integer, nullable=True)
    under_price = Column(Integer, nullable=True)

    # Result (settled)
    actual = Column(Float, nullable=True)
    result = Column(String, nullable=True)  # 'over', 'under', 'push'

    # CLV (Closing Line Value)
    clv = Column(Float, nullable=True)  # Difference between opening and closing line
    clv_pct = Column(Float, nullable=True)  # Percentage edge

    # Model predictions (if available)
    predicted = Column(Float, nullable=True)
    model_edge = Column(Float, nullable=True)

    # Opening line (if available)
    open_line = Column(Float, nullable=True)
    open_over_odds = Column(Integer, nullable=True)
    open_under_odds = Column(Integer, nullable=True)

    # Source metadata
    sportsbook = Column(String, index=True)  # 'draftkings', 'fanduel', 'pinnacle', etc.
    source = Column(String)  # 'sportsgamesodds', 'scraper'
    external_prop_id = Column(String, unique=True)

    # Raw data storage
    raw_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
