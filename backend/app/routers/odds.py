"""
Odds data endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from loguru import logger

router = APIRouter()


@router.get("/odds/{sport}")
async def get_current_odds(sport: str) -> Dict[str, Any]:
    """
    Get current odds for a sport
    
    Args:
        sport: Sport name (nfl, nba, mlb, etc.)
        
    Returns:
        Current odds data
    """
    logger.info(f"Fetching odds for {sport}")
    
    # Placeholder - would integrate with odds APIs
    return {
        "sport": sport,
        "last_updated": "2024-01-15T10:00:00Z",
        "games": []
    }

