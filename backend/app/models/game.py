"""
Game model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import datetime


class Game(Base):
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    external_game_id = Column(String, unique=True, index=True)
    sport = Column(String, index=True)
    
    home_team = Column(String)
    away_team = Column(String)
    
    game_date = Column(DateTime)
    
    # Results
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    bets = relationship("Bet", back_populates="game")

