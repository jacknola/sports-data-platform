import asyncio
import sys
import os
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, SessionLocal
from app.models.team import Team
from app.models.player import Player
from app.services.nba_backfill import NBABackfillService
from app.services.player_backfill import NBAPlayerBackfillService
from app.services.player_vector_backfill import PlayerVectorBackfillService

# NBA API imports
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.static import players as nba_players

async def seed_teams(db: Session):
    """Seed NBA teams from nba_api."""
    logger.info("Seeding NBA teams...")
    teams = nba_teams.get_teams()
    count = 0
    for t in teams:
        tid = str(t['id'])
        stmt = select(Team).where(Team.external_team_id == tid)
        existing = db.execute(stmt).scalars().first()
        if not existing:
            new_team = Team(
                external_team_id=tid,
                name=t['full_name'],
                sport='nba'
            )
            db.add(new_team)
            count += 1
    db.commit()
    logger.info(f"Seeded {count} new teams.")

async def seed_players(db: Session):
    """Seed active NBA players from nba_api."""
    logger.info("Seeding active NBA players...")
    # Using static active players list first (fast)
    active_players = nba_players.get_active_players()
    count = 0

    for p in active_players:
        pid = str(p['id'])
        stmt = select(Player).where(Player.external_player_id == pid)
        existing = db.execute(stmt).scalars().first()
        if not existing:
            new_player = Player(
                external_player_id=pid,
                name=p['full_name'],
                sport='nba',
                # We don't have current team_id easily from static list, 
                # could fetch from commonallplayers but this is enough for backfill
            )
            db.add(new_player)
            count += 1
    db.commit()
    logger.info(f"Seeded {count} new players.")

async def main():
    logger.info("Starting Backfill Pipeline")
    
    # 1. Init DB
    await init_db()
    
    db = SessionLocal()
    try:
        # 2. Seed Metadata
        await seed_teams(db)
        await seed_players(db)
        
        # 3. Backfill Games (2023-24 Season)
        logger.info("Backfilling Games for 2023-24...")
        game_service = NBABackfillService(db)
        game_service.backfill_season("2023-24")
        
        # 4. Backfill Player Logs
        logger.info("Backfilling Player Logs for 2023-24...")
        player_service = NBAPlayerBackfillService(db)
        players = db.query(Player).all()
        
        # Limit to first 50 players for quick test, or remove slice for full
        # For user request, we should do a decent chunk. Let's do all.
        for i, p in enumerate(players):
            logger.info(f"[{i+1}/{len(players)}] Processing {p.name}...")
            player_service.backfill_player(p.id, "2023-24") # type: ignore
            
        # 5. Backfill Vectors (Qdrant)
        logger.info("Backfilling Qdrant Vectors...")
        vector_service = PlayerVectorBackfillService(db)
        vector_service.backfill_all_logs()
        
        logger.info("✅ Backfill Pipeline Complete!")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
