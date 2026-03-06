"""
Defense vs Position (DvP) model
Stores defensive rankings by position from sources like HashtagBasketball and FantasyPros
"""

from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base


class DefenseVsPosition(Base):
    """Defense vs Position rankings - identifies weak defenses per position"""

    __tablename__ = "defense_vs_position"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)  # 'hashtag' or 'fantasypros'
    position = Column(String(2), nullable=False, index=True)  # PG, SG, SF, PF, C
    team = Column(String(3), nullable=False, index=True)  # Team abbreviation (NY, LAL, etc.)
    rank = Column(Integer, nullable=True)  # Overall rank (1=best defense, 150=worst)
    
    # Stats allowed to this position (per 48 minutes or game)
    pts = Column(Float, nullable=True)
    fg_pct = Column(Float, nullable=True)
    ft_pct = Column(Float, nullable=True)
    threes = Column(Float, nullable=True)  # 3-pointers made
    reb = Column(Float, nullable=True)
    ast = Column(Float, nullable=True)
    stl = Column(Float, nullable=True)
    blk = Column(Float, nullable=True)
    to = Column(Float, nullable=True)  # Turnovers
    fd_pts = Column(Float, nullable=True)  # FanDuel points (FantasyPros only)
    
    # Metadata
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<DvP {self.source} {self.position} vs {self.team} rank={self.rank}>"

    def is_weak_defense(self, threshold_rank=100):
        """Returns True if this is a weak defense (high rank = bad defense = good for fantasy)"""
        return self.rank and self.rank >= threshold_rank
