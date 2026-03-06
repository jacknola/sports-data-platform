#!/usr/bin/env python3
"""
Import Defense vs Position data from scraped sources into database
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from loguru import logger
from app.database import SessionLocal, engine, Base
from app.models.defense_vs_position import DefenseVsPosition


def import_hashtag_data(session: Session, json_file: str) -> int:
    """Import HashtagBasketball DvP data from JSON file"""
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Clear existing hashtag data
    session.query(DefenseVsPosition).filter(DefenseVsPosition.source == 'hashtag').delete()
    logger.info(f"Cleared existing HashtagBasketball data")
    
    count = 0
    for row in data:
        dvp = DefenseVsPosition(
            source='hashtag',
            position=row['position'],
            team=row['team'],
            rank=row['rank'],
            pts=row['pts'],
            fg_pct=row['fg_pct'],
            ft_pct=row['ft_pct'],
            threes=row['threes'],
            reb=row['reb'],
            ast=row['ast'],
            stl=row['stl'],
            blk=row['blk'],
            to=row['to'],
        )
        session.add(dvp)
        count += 1
    
    session.commit()
    logger.info(f"Imported {count} rows from HashtagBasketball")
    return count


def get_weak_defenses(session: Session, position: str, threshold_rank: int = 100):
    """Query teams with weak defenses vs a position (high rank = bad defense)"""
    
    weak_defenses = (
        session.query(DefenseVsPosition)
        .filter(
            DefenseVsPosition.source == 'hashtag',
            DefenseVsPosition.position == position,
            DefenseVsPosition.rank >= threshold_rank
        )
        .order_by(DefenseVsPosition.rank.desc())
        .all()
    )
    
    return weak_defenses


if __name__ == "__main__":
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    
    try:
        # Import HashtagBasketball data
        json_file = '/tmp/hashtag_dvp.json'
        if os.path.exists(json_file):
            import_hashtag_data(session, json_file)
        else:
            logger.error(f"JSON file not found: {json_file}")
            sys.exit(1)
        
        # Example: Show worst defenses vs PG
        logger.info("\n=== Top 10 Worst Defenses vs PG (Good matchups for PGs) ===")
        weak_pg_defenses = get_weak_defenses(session, 'PG', threshold_rank=100)[:10]
        for dvp in weak_pg_defenses:
            logger.info(
                f"  {dvp.team:4s} - Rank {dvp.rank:3d} - Allow {dvp.pts:.1f} pts, "
                f"{dvp.ast:.1f} ast, {dvp.threes:.1f} 3pm"
            )
        
        # Show worst defenses by position
        logger.info("\n=== Worst Defense vs Each Position (Rank >= 140) ===")
        for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            worst = get_weak_defenses(session, pos, threshold_rank=140)[:3]
            if worst:
                teams = ", ".join([f"{d.team}({d.rank})" for d in worst])
                logger.info(f"  {pos}: {teams}")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()
