"""
Game model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime, timezone


class Game(Base):
    __tablename__ = "games"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    external_game_id = Column(String, unique=True)
    sport = Column(String)
    
    home_team = Column(String)
    away_team = Column(String)
    
    game_date = Column(DateTime)
    
    # Results
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    bets = relationship("Bet", back_populates="game")
    player_game_logs = relationship("PlayerGameLog", back_populates="game")

