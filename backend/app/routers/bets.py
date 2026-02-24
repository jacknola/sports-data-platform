"""
Best bets endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from app.services.bayesian import BayesianAnalyzer
from app.services.nba_ml_predictor import NBAMLPredictor

router = APIRouter()
bayesian_analyzer = BayesianAnalyzer()
nba_predictor = NBAMLPredictor()


@router.get("/bets")
async def get_best_bets(
    sport: str = Query(default="nba", description="Sport to analyze"),
    min_edge: float = Query(default=0.05, description="Minimum edge threshold"),
    limit: int = Query(default=10, description="Maximum number of bets to return"),
) -> List[Dict[str, Any]]:
    """
    Get best betting opportunities with ML predictions

    Args:
        sport: Sport to analyze (nba, nfl, etc.)
        min_edge: Minimum edge required
        limit: Maximum bets to return

    Returns:
        List of best bet opportunities with EV and Kelly Criterion
    """
    logger.info(f"Getting best bets for {sport} with min edge {min_edge}")

    try:
        if sport.lower() == "nba":
            return await _get_nba_best_bets(min_edge, limit)
        else:
            # Fallback for other sports
            return [
                {
                    "sport": sport,
                    "selection_id": "bet_1",
                    "description": "Example bet",
                    "edge": 0.05,
                    "probability": 0.55,
                    "current_odds": -110,
                }
            ]

    except Exception as e:
        logger.error(f"Error getting best bets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/predictions/nba/today")
async def get_nba_predictions_today() -> Dict[str, Any]:
    """
    Get NBA predictions for today's games using ML models

    Returns:
        Predictions with probabilities and recommendations
    """
    try:
        predictions = await nba_predictor.predict_today_games("nba")

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sport": "NBA",
            "total_games": len(predictions),
            "predictions": predictions,
            "method": "xgboost",
        }
    except Exception as e:
        logger.error(f"NBA prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_nba_best_bets(min_edge: float, limit: int) -> List[Dict[str, Any]]:
    """
    Process NBA predictions and return best bets sorted by edge.
    """
    game_predictions = await nba_predictor.predict_today_games("nba")
    best_bets = []

    for pred in game_predictions:
        # Process Moneyline
        ml_bet = _process_nba_moneyline(pred, min_edge)
        if ml_bet:
            best_bets.append(ml_bet)

        # Process Total (Over/Under)
        total_bet = _process_nba_total(pred)
        if total_bet:
            best_bets.append(total_bet)

    # Sort by edge and limit
    return sorted(best_bets, key=lambda x: x["edge"], reverse=True)[:limit]


def _process_nba_moneyline(
    pred: Dict[str, Any], min_edge: float
) -> Optional[Dict[str, Any]]:
    """Extract moneyline bet from prediction if it meets the edge criteria."""
    ev_data = pred.get("expected_value", {})
    home_ev = ev_data.get("home_ev", 0)

    if home_ev <= min_edge:
        return None

    best_bet_selection = ev_data.get("best_bet")
    if not best_bet_selection:
        return None

    return {
        "sport": "NBA",
        "game": f"{pred['away_team']} @ {pred['home_team']}",
        "market": "Moneyline",
        "selection": best_bet_selection,
        "edge": ev_data.get(f"{best_bet_selection}_ev"),
        "probability": pred.get("moneyline_prediction", {}).get("home_win_prob", 0),
        "confidence": pred.get("confidence", 0),
        "current_odds": ev_data.get(f"{best_bet_selection}_odds"),
        "kelly_fraction": pred.get("kelly_criterion", 0),
        "method": "ml_xgboost",
        "ml_prediction": pred,
    }


def _process_nba_total(pred: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract total (over/under) bet from prediction if available."""
    uo_pred = pred.get("underover_prediction")
    if not uo_pred:
        return None

    over_prob = uo_pred.get("over_prob", 0.5)
    # Strong prediction threshold check (hardcoded 0.1 delta from 0.5 as per original code)
    if abs(over_prob - 0.5) <= 0.1:
        return None

    recommendation = uo_pred.get("recommendation")
    probability = over_prob if recommendation == "over" else uo_pred.get("under_prob")

    return {
        "sport": "NBA",
        "game": f"{pred['away_team']} @ {pred['home_team']}",
        "market": f"Total {uo_pred.get('total_points')}",
        "selection": recommendation,
        "edge": abs(over_prob - 0.5),
        "probability": probability,
        "confidence": abs(over_prob - 0.5) * 2,
        "method": "ml_xgboost",
        "ml_prediction": pred,
    }
