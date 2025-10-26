"""
Team model
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime
from app.database import Base
import datetime


class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    external_team_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    sport = Column(String, index=True)
    
    # Metadata
    stats = Column(JSON)  # Store team statistics
    sentiment_data = Column(JSON)  # Store Twitter sentiment
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

