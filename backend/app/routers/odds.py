"""
Odds data endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.services.sports_api import SportsAPIService
from app.services.bet_storage import bet_storage
from app.database import get_db

router = APIRouter()
sports_api = SportsAPIService()


@router.get("/odds/{sport}")
async def get_current_odds(
    sport: str,
    store_data: bool = Query(default=False, description="Store cleaned data in database"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current odds for a sport from external API
    Optionally clean and store data in database
    
    Args:
        sport: Sport name (nfl, nba, mlb, etc.)
        store_data: Whether to store cleaned data in database
        db: Database session
        
    Returns:
        Current odds data with optional storage results
    """
    logger.info(f"Fetching odds for {sport}")
    
    try:
        # Fetch odds from external API
        odds_data = await sports_api.get_odds(sport)
        
        storage_results = None
        if store_data and odds_data:
            logger.info(f"Storing odds data for {len(odds_data)} games")
            storage_results = bet_storage.store_odds_api_data(db, odds_data)
        
        return {
            "sport": sport,
            "last_updated": datetime.now().isoformat(),
            "total_games": len(odds_data),
            "games": odds_data,
            "storage": storage_results
        }
    except Exception as e:
        logger.error(f"Error fetching odds for {sport}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

