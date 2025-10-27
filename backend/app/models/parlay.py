"""
Parlay models
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
import datetime

from app.database import Base


class Parlay(Base):
    __tablename__ = "parlays"

    id = Column(Integer, primary_key=True, index=True)

    # Source metadata
    source = Column(String, default="twitter", index=True)
    tweet_id = Column(String, index=True, nullable=True)
    author_username = Column(String, index=True, nullable=True)
    author_user_id = Column(String, index=True, nullable=True)
    posted_at = Column(DateTime, nullable=True)

    # Content
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    sportsbook = Column(String, nullable=True)
    num_legs = Column(Integer, default=0)
    total_odds_american = Column(Integer, nullable=True)  # e.g. +450 -> 450, -110 -> -110
    stake_units = Column(Float, nullable=True)
    status = Column(String, default="open")  # open | won | lost | push | void
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    legs = relationship(
        "ParlayLeg", back_populates="parlay", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source", "tweet_id", name="uq_parlay_source_tweet_id"),
    )


class ParlayLeg(Base):
    __tablename__ = "parlay_legs"

    id = Column(Integer, primary_key=True, index=True)
    parlay_id = Column(Integer, ForeignKey("parlays.id"), index=True, nullable=False)

    # Ordering
    order_index = Column(Integer, default=0)

    # Leg details
    sport = Column(String, nullable=True)
    league = Column(String, nullable=True)  # e.g., NBA, NFL
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True)

    team = Column(String, nullable=True)
    player = Column(String, nullable=True)
    market = Column(String, nullable=True)  # moneyline | spread | total | player_* etc.
    selection = Column(String, nullable=True)  # ML | Over | Under | +X.5 | -X.5 etc.
    line = Column(Float, nullable=True)  # e.g., 220.5
    odds_american = Column(Integer, nullable=True)
    result = Column(String, default="pending")  # pending | won | lost | push | void
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    parlay = relationship("Parlay", back_populates="legs")
