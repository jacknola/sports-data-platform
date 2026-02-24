"""
Player model
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import datetime


class Player(Base):
    __tablename__ = "players"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True, index=True)
    external_player_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    sport = Column(String, index=True)
    
    # Stats and features
    stats = Column(JSON)
    injury_status = Column(String)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    team = relationship("Team")

