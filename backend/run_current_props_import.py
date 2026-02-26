"""
Current Player Props Import
Fetches current live player props from The Odds API and saves them to the database.
By running this daily/hourly, we build our own historical dataset of opening and closing lines.

Usage:
    python3 run_current_props_import.py --sport basketball_nba
"""

import os
import sys
import argparse
import asyncio
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy import select

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.historical_player_prop import HistoricalPlayerProp
from app.services.sports_api import SportsAPIService

async def run_import(sport: str, dry_run: bool = False):
    logger.info(f"Starting current props import for {sport}")
    
    api = SportsAPIService()
    
    # We only want to fetch if we have enough quota. The get_all_player_props method
    # already respects the quota.
    props = await api.get_all_player_props(sport=sport)
    
    if not props:
        logger.warning(f"No props returned for {sport}. API may be exhausted or no games today.")
        return 0
        
    logger.info(f"Fetched {len(props)} unique player props. Mapping to database...")
    
    db = SessionLocal()
    try:
        saved_count = 0
        updated_count = 0
        now = datetime.now(timezone.utc)
        
        for p in props:
            # We treat the median/canonical line as the primary prop line
            # External ID format: SPORT_EVENTID_PLAYER_PROPTYPE
            ext_prop_id = f"{sport}_{p['event_id']}_{p['player'].replace(' ', '')}_{p['prop_type']}"
            
            # See if we already have this prop for this event
            stmt = select(HistoricalPlayerProp).where(HistoricalPlayerProp.external_prop_id == ext_prop_id)
            existing = db.execute(stmt).scalars().first()
            
            if existing:
                # Update closing lines if it's changing
                # We can treat the first seen as 'open' and subsequent as 'current/closing'
                if existing.open_line is None:
                    existing.open_line = existing.line
                    existing.open_over_odds = existing.over_odds
                    existing.open_under_odds = existing.under_odds
                
                # Update current line/odds
                existing.line = p['line']
                existing.over_odds = p['over_odds']
                existing.under_odds = p['under_odds']
                existing.updated_at = now
                updated_count += 1
            else:
                # Create new record
                new_prop = HistoricalPlayerProp(
                    external_prop_id=ext_prop_id,
                    player_name=p['player'],
                    team="", # Need lookup if we want it perfect, but skip for now
                    opponent=p['away_team'] if p['home_team'] != p['player'] else p['home_team'], # Rough approx
                    game_date=now, # The get_all_player_props doesn't pass game_date down perfectly yet, using now
                    season=now.year if now.month >= 10 else now.year - 1,
                    prop_type=p['prop_type'],
                    stat_type="both", # we store both over and under
                    line=p['line'],
                    over_odds=p['over_odds'],
                    under_odds=p['under_odds'],
                    open_line=p['line'],
                    open_over_odds=p['over_odds'],
                    open_under_odds=p['under_odds'],
                    sportsbook="best_available", # we aggregated across books
                    source="oddsapi",
                    raw_data={"offerings": p.get("offerings", [])}
                )
                db.add(new_prop)
                saved_count += 1
                
        if not dry_run:
            db.commit()
            logger.info(f"✅ Saved {saved_count} new props, updated {updated_count} existing props.")
        else:
            logger.info(f"DRY RUN: Would have saved {saved_count} new props, updated {updated_count} existing props.")
            
        return saved_count + updated_count
        
    except Exception as e:
        logger.error(f"Error saving props to database: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and save current player props")
    parser.add_argument("--sport", type=str, default="basketball_nba", help="Sport key (e.g. basketball_nba)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    
    args = parser.parse_args()
    
    asyncio.run(run_import(sport=args.sport, dry_run=args.dry_run))
