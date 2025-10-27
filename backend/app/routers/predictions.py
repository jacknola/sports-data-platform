"""
ML predictions endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from loguru import logger

from app.services.ml_service import MLService
from app.services.backtest import BacktestService

router = APIRouter()
ml_service = MLService()
backtester = BacktestService()


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


@router.post("/predictions/backtest")
async def run_backtest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run backtest metrics on a list of predictions.

    Expected payload:
    {
      "predictions": [
         {"y_true": 1, "p": 0.62, "bet": true, "american_odds": -110, "stake": 1.0, "edge": 0.03},
         ...
      ],
      "bins": 10
    }
    """
    try:
        preds: List[Dict[str, Any]] = payload.get("predictions", [])
        bins: int = int(payload.get("bins", 10))
        metrics = backtester.evaluate(preds, bins=bins)
        return {"metrics": metrics}
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

