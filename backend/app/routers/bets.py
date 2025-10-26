"""
Best bets endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from loguru import logger

from app.services.bayesian import BayesianAnalyzer

router = APIRouter()
bayesian_analyzer = BayesianAnalyzer()


@router.get("/bets")
async def get_best_bets(sport: str = "nfl", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get best betting opportunities
    
    Args:
        sport: Sport to analyze
        limit: Maximum number of bets to return
        
    Returns:
        List of best bet opportunities
    """
    # This is a placeholder - would integrate with odds APIs
    logger.info(f"Getting best bets for {sport}")
    
    return [
        {
            "sport": sport,
            "selection_id": "bet_1",
            "description": "Example bet",
            "edge": 0.05,
            "probability": 0.55,
            "current_odds": -110
        }
    ]


@router.post("/bayesian")
async def run_bayesian_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Bayesian analysis on a betting selection
    
    Args:
        data: Selection data with devig_prob, implied_prob, features
        
    Returns:
        Bayesian analysis results
    """
    try:
        result = bayesian_analyzer.compute_posterior(data)
        return result
    except Exception as e:
        logger.error(f"Bayesian analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

