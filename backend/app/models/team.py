"""
Team model
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime, timezone


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    external_team_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    sport = Column(String, index=True)

    # Metadata
    stats = Column(JSON)  # Store team statistics
    sentiment_data = Column(JSON)  # Store Twitter sentiment

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    players = relationship("Player", back_populates="team")
    home_game_logs = relationship("PlayerGameLog", foreign_keys="PlayerGameLog.team_id", back_populates="team")
    away_game_logs = relationship("PlayerGameLog", foreign_keys="PlayerGameLog.opponent_id", back_populates="opponent")
