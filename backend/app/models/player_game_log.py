"""
Player Game Log model
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime, timezone


class PlayerGameLog(Base):
    __tablename__ = "player_game_logs"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    game_id = Column(Integer, ForeignKey("games.id"))
    
    external_log_id = Column(String, unique=True)
    
    team_id = Column(Integer, ForeignKey("teams.id"))
    opponent_id = Column(Integer, ForeignKey("teams.id"))
    
    game_date = Column(DateTime, index=True)
    
    # Core Stats
    min = Column(Float)
    pts = Column(Integer)
    reb = Column(Integer)
    ast = Column(Integer)
    stl = Column(Integer)
    blk = Column(Integer)
    tov = Column(Integer)
    fg3m = Column(Integer)
    
    # Composite Stats
    pra = Column(Integer)
    
    # Scenario / Situational Data
    scenario = Column(JSON)  # Store qualitative context (e.g., rest days, pace)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    player = relationship("Player", back_populates="game_logs")
    game = relationship("Game", back_populates="player_game_logs")
    team = relationship("Team", foreign_keys=[team_id], back_populates="home_game_logs")
    opponent = relationship("Team", foreign_keys=[opponent_id], back_populates="away_game_logs")
