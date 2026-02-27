"""
Parlay model - Dan's AI Sports Picks style
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime, timezone


class Parlay(Base):
    __tablename__ = "parlays"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    parlay_id = Column(String, unique=True)
    
    # Parlay metadata
    title = Column(String, index=True)  # e.g., "NBA Sunday Special"
    sport = Column(String, index=True)  # NBA, NFL, MLB, etc.
    confidence_level = Column(String)  # HIGH, MEDIUM, LOW
    confidence_score = Column(Float)  # 0-100
    
    # Parlay structure (Dan's style)
    legs = Column(JSON)  # Array of leg objects
    """
    Example legs format:
    [
        {
            "game": "Lakers vs Warriors",
            "pick": "Lakers ML",
            "odds": -150,
            "reasoning": "LeBron dominates in revenge games",
            "team": "Lakers",
            "market": "moneyline",
            "game_time": "2025-10-27T19:00:00"
        },
        {
            "game": "Celtics vs Heat", 
            "pick": "Over 215.5",
            "odds": -110,
            "reasoning": "Both teams rank top 5 in pace",
            "market": "total",
            "game_time": "2025-10-27T19:30:00"
        }
    ]
    """
    
    # Odds and payout
    total_odds = Column(Float)  # Combined parlay odds (e.g., +450)
    potential_payout_multiplier = Column(Float)  # e.g., 5.5x
    suggested_unit_size = Column(Float)  # Kelly criterion suggested size
    
    # Analysis and reasoning
    analysis = Column(Text)  # Overall parlay reasoning
    key_factors = Column(JSON)  # Array of key factors
    risks = Column(JSON)  # Array of potential risks
    
    # Performance tracking
    status = Column(String, default="pending")  # pending, won, lost, partial
    result = Column(JSON)  # Results for each leg
    actual_return = Column(Float, nullable=True)
    
    # Twitter integration
    twitter_post_id = Column(String, nullable=True)
    twitter_posted_at = Column(DateTime, nullable=True)
    tweet_text = Column(Text, nullable=True)
    
    # RAG embeddings
    embedding_vector = Column(JSON, nullable=True)  # Store embedding for semantic search
    similar_parlays = Column(JSON, nullable=True)  # IDs of similar historical parlays
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    event_date = Column(DateTime)  # Date of the events in parlay
    
    # Additional metadata
    tags = Column(JSON)  # ["revenge-game", "pace-up", "home-favorite"]
    source_data = Column(JSON)  # Original data sources used
    sentiment_scores = Column(JSON)  # Twitter sentiment for each team
    
    # Performance metrics (filled after result)
    profit_loss = Column(Float, nullable=True)
    roi = Column(Float, nullable=True)


class ParlayLeg(Base):
    """Individual leg of a parlay for detailed tracking"""
    __tablename__ = "parlay_legs"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    parlay_id = Column(String, index=True)
    
    # Leg details
    game_id = Column(String)
    team = Column(String)
    opponent = Column(String)
    pick = Column(String)  # Human readable pick
    market = Column(String)  # moneyline, spread, total, player_prop
    line = Column(Float, nullable=True)  # Spread or total line
    odds = Column(Float)
    
    # Analysis
    reasoning = Column(Text)
    supporting_factors = Column(JSON)
    confidence = Column(Float)
    
    # Result
    result = Column(String, nullable=True)  # won, lost, push
    actual_outcome = Column(String, nullable=True)
    
    # Timestamps
    game_time = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
