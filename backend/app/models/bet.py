"""
Bet model
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base
import datetime


class Bet(Base):
    __tablename__ = "bets"
    
    id = Column(Integer, primary_key=True, index=True)
    selection_id = Column(String, unique=True, index=True)
    sport = Column(String, index=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    team = Column(String)
    market = Column(String)  # e.g., "moneyline", "spread", "total"
    
    # Odds data
    current_odds = Column(Float)
    implied_prob = Column(Float)
    devig_prob = Column(Float)
    
    # Model results
    posterior_prob = Column(Float)
    fair_american_odds = Column(Float)
    edge = Column(Float)
    kelly_fraction = Column(Float)
    
    # Metadata
    features = Column(JSON)  # Store feature dict
    confidence_interval = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    game = relationship("Game", back_populates="bets")

