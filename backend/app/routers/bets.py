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
    limit: int = Query(default=10, description="Maximum number of bets to return")
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
        if sport.lower() == 'nba':
            # Use NBA ML predictor
            game_predictions = await nba_predictor.predict_today_games('nba')
            
            best_bets = []
            for pred in game_predictions:
                # Check if prediction has positive EV
                ev = pred.get('expected_value', {})
                if ev and max(ev.get('home_ev', 0), ev.get('away_ev', 0)) > min_edge:
                    best_side = ev.get('best_bet')
                    side_prob = pred['moneyline_prediction']['home_win_prob'] if best_side == 'home' else pred['moneyline_prediction']['away_win_prob']
                    best_bets.append({
                        'sport': 'NBA',
                        'game': f"{pred['away_team']} @ {pred['home_team']}",
                        'market': 'Moneyline',
                        'selection': best_side,
                        'edge': ev[f"{best_side}_ev"],
                        'probability': side_prob,
                        'confidence': pred.get('confidence', 0),
                        'current_odds': ev.get(f"{best_side}_odds"),
                        'kelly_fraction': pred.get('kelly_criterion', 0),
                        'method': 'ml_xgboost',
                        'ml_prediction': pred
                    })
                
                # Check under/over if available
                if pred.get('underover_prediction'):
                    uo_pred = pred['underover_prediction']
                    if abs(uo_pred['over_prob'] - 0.5) > 0.1:  # Strong prediction
                        best_bets.append({
                            'sport': 'NBA',
                            'game': f"{pred['away_team']} @ {pred['home_team']}",
                            'market': f"Total {uo_pred['total_points']}",
                            'selection': uo_pred['recommendation'],
                            'edge': abs(uo_pred['over_prob'] - 0.5),
                            'probability': uo_pred['over_prob'] if uo_pred['recommendation'] == 'over' else uo_pred['under_prob'],
                            'confidence': abs(uo_pred['over_prob'] - 0.5) * 2,
                            'method': 'ml_xgboost',
                            'ml_prediction': pred
                        })
            
            # Sort by edge and limit
            best_bets = sorted(best_bets, key=lambda x: x['edge'], reverse=True)[:limit]
            
            return best_bets
        
        else:
            # Fallback for other sports
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
        predictions = await nba_predictor.predict_today_games('nba')
        
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'sport': 'NBA',
            'total_games': len(predictions),
            'predictions': predictions,
            'method': 'xgboost'
        }
    except Exception as e:
        logger.error(f"NBA prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
