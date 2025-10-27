"""
Best bets endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.services.bayesian import BayesianAnalyzer
from app.services.nba_ml_predictor import NBAMLPredictor
from app.services.bet_storage import bet_storage
from app.services.data_cleaner import data_cleaner
from app.database import get_db

router = APIRouter()
bayesian_analyzer = BayesianAnalyzer()
nba_predictor = NBAMLPredictor()


@router.get("/bets")
async def get_best_bets(
    sport: str = Query(default="nba", description="Sport to analyze"),
    min_edge: float = Query(default=0.05, description="Minimum edge threshold"),
    limit: int = Query(default=10, description="Maximum number of bets to return"),
    store_data: bool = Query(default=True, description="Store cleaned data in database"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get best betting opportunities with ML predictions and store them in database
    
    Args:
        sport: Sport to analyze (nba, nfl, etc.)
        min_edge: Minimum edge required
        limit: Maximum bets to return
        store_data: Whether to store cleaned data in database
        db: Database session
        
    Returns:
        Dict with best bet opportunities and storage results
    """
    logger.info(f"Getting best bets for {sport} with min edge {min_edge}")
    
    try:
        if sport.lower() == 'nba':
            # Use NBA ML predictor
            game_predictions = await nba_predictor.predict_today_games('nba')
            
            best_bets = []
            for pred in game_predictions:
                # Prepare game context
                game_context = {
                    'external_game_id': f"nba_{pred['away_team']}_{pred['home_team']}_{datetime.now().strftime('%Y%m%d')}",
                    'sport': 'NBA',
                    'home_team': pred['home_team'],
                    'away_team': pred['away_team'],
                    'game_date': datetime.now()
                }
                
                # Check if prediction has positive EV
                if pred.get('expected_value', {}).get('home_ev', 0) > min_edge:
                    bet = {
                        'sport': 'NBA',
                        'game': game_context,
                        'team': pred['expected_value']['best_bet'],
                        'market': 'moneyline',
                        'selection': pred['expected_value']['best_bet'],
                        'edge': pred['expected_value'][f"{pred['expected_value']['best_bet']}_ev"],
                        'probability': pred['moneyline_prediction'].get('home_win_prob', 0),
                        'confidence': pred.get('confidence', 0),
                        'current_odds': pred['expected_value'].get(f"{pred['expected_value']['best_bet']}_odds"),
                        'kelly_fraction': pred.get('kelly_criterion', 0),
                        'method': 'ml_xgboost',
                        'ml_prediction': pred
                    }
                    best_bets.append(bet)
                
                # Check under/over if available
                if pred.get('underover_prediction'):
                    uo_pred = pred['underover_prediction']
                    if abs(uo_pred['over_prob'] - 0.5) > 0.1:  # Strong prediction
                        bet = {
                            'sport': 'NBA',
                            'game': game_context,
                            'team': pred['home_team'],  # Associate with home team
                            'market': 'total',
                            'selection': uo_pred['recommendation'],
                            'edge': abs(uo_pred['over_prob'] - 0.5),
                            'probability': uo_pred['over_prob'] if uo_pred['recommendation'] == 'over' else uo_pred['under_prob'],
                            'confidence': abs(uo_pred['over_prob'] - 0.5) * 2,
                            'current_odds': uo_pred.get('total_points'),
                            'method': 'ml_xgboost',
                            'ml_prediction': pred
                        }
                        best_bets.append(bet)
            
            # Sort by edge and limit
            best_bets = sorted(best_bets, key=lambda x: x['edge'], reverse=True)[:limit]
            
            # Store data in database if requested
            storage_results = None
            if store_data and best_bets:
                logger.info(f"Storing {len(best_bets)} best bets in database")
                storage_results = bet_storage.store_best_bets(db, best_bets)
            
            return {
                'sport': sport.upper(),
                'timestamp': datetime.now().isoformat(),
                'total_bets': len(best_bets),
                'min_edge': min_edge,
                'bets': best_bets,
                'storage': storage_results
            }
        
        else:
            # Fallback for other sports
            fallback_bets = [
                {
                    "sport": sport,
                    "selection_id": "bet_1",
                    "description": "Example bet",
                    "edge": 0.05,
                    "probability": 0.55,
                    "current_odds": -110
                }
            ]
            
            return {
                'sport': sport.upper(),
                'timestamp': datetime.now().isoformat(),
                'total_bets': len(fallback_bets),
                'min_edge': min_edge,
                'bets': fallback_bets,
                'storage': None
            }
            
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


@router.post("/bets/store")
async def store_bets_manually(
    bets_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Manually store best bets data from any sports platform
    Cleans and validates data before storage
    
    Args:
        bets_data: List of raw bet data from sports platform
        db: Database session
        
    Returns:
        Storage results with counts and any errors
    """
    logger.info(f"Manually storing {len(bets_data)} bets")
    
    try:
        results = bet_storage.store_best_bets(db, bets_data)
        
        return {
            'success': True,
            'message': f"Processed {results['total_bets']} bets",
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error storing bets manually: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/odds/store")
async def store_odds_data(
    odds_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Store odds data from Odds API or similar platforms
    Cleans and validates data before storage
    
    Args:
        odds_data: Raw odds data from API (Odds API format)
        db: Database session
        
    Returns:
        Storage results with games and bets saved
    """
    logger.info(f"Storing odds data for {len(odds_data)} games")
    
    try:
        results = bet_storage.store_odds_api_data(db, odds_data)
        
        return {
            'success': True,
            'message': f"Processed {results['total_games']} games",
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error storing odds data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bets/stored")
async def get_stored_bets(
    sport: Optional[str] = Query(default=None, description="Filter by sport"),
    min_edge: Optional[float] = Query(default=None, description="Minimum edge filter"),
    limit: int = Query(default=50, description="Maximum bets to return"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get stored bets from database
    
    Args:
        sport: Filter by sport
        min_edge: Minimum edge threshold
        limit: Maximum bets to return
        db: Database session
        
    Returns:
        List of stored bets with metadata
    """
    logger.info(f"Retrieving stored bets: sport={sport}, min_edge={min_edge}")
    
    try:
        bets = bet_storage.get_recent_bets(db, sport, min_edge, limit)
        
        # Convert to dict format
        bets_data = []
        for bet in bets:
            bet_dict = {
                'id': bet.id,
                'selection_id': bet.selection_id,
                'sport': bet.sport,
                'team': bet.team,
                'market': bet.market,
                'current_odds': bet.current_odds,
                'implied_prob': bet.implied_prob,
                'devig_prob': bet.devig_prob,
                'posterior_prob': bet.posterior_prob,
                'edge': bet.edge,
                'kelly_fraction': bet.kelly_fraction,
                'fair_american_odds': bet.fair_american_odds,
                'features': bet.features,
                'confidence_interval': bet.confidence_interval,
                'created_at': bet.created_at.isoformat() if bet.created_at else None,
                'updated_at': bet.updated_at.isoformat() if bet.updated_at else None
            }
            
            # Include game info if available
            if bet.game:
                bet_dict['game'] = {
                    'id': bet.game.id,
                    'external_game_id': bet.game.external_game_id,
                    'home_team': bet.game.home_team,
                    'away_team': bet.game.away_team,
                    'game_date': bet.game.game_date.isoformat() if bet.game.game_date else None,
                    'home_score': bet.game.home_score,
                    'away_score': bet.game.away_score
                }
            
            bets_data.append(bet_dict)
        
        return {
            'success': True,
            'total': len(bets_data),
            'sport': sport,
            'min_edge': min_edge,
            'bets': bets_data,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error retrieving stored bets: {e}")
        raise HTTPException(status_code=500, detail=str(e))
