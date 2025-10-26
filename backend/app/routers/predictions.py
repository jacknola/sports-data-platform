"""
ML predictions endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from loguru import logger

from app.services.ml_service import MLService

router = APIRouter()
ml_service = MLService()


@router.get("/predictions")
async def get_predictions(sport: str = "nfl") -> Dict[str, Any]:
    """
    Get ML predictions for upcoming games
    
    Args:
        sport: Sport to predict
        
    Returns:
        Predictions data
    """
    logger.info(f"Getting predictions for {sport}")
    
    # Placeholder
    return {
        "sport": sport,
        "predictions": [],
        "note": "ML predictions not yet implemented"
    }


@router.post("/predictions/generate")
async def generate_prediction(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate ML prediction for a specific bet
    
    Args:
        data: Feature data for prediction
        
    Returns:
        Prediction results
    """
    try:
        result = ml_service.predict_bet_outcome(data.get('features', {}))
        return result
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

