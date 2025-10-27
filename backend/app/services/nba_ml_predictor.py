"""
NBA Machine Learning Predictor Service
Integrated with kyleskom/NBA-Machine-Learning-Sports-Betting approach
"""
import os
import pickle
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
import pandas as pd
from loguru import logger
from app.services.bayesian import BayesianAnalyzer

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not installed, ML predictions disabled")


class NBAMLPredictor:
    """NBA betting predictions using machine learning"""
    
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.data_cache: Dict[str, Any] = {}
        self.bayesian = BayesianAnalyzer()
        self._load_models()
    
    def _load_models(self):
        """Load trained ML models"""
        try:
            model_path = os.getenv('NBA_MODEL_PATH', './models/nba_ml')
            
            # Load XGBoost models if available
            if XGBOOST_AVAILABLE and os.path.exists(model_path):
                try:
                    with open(f'{model_path}/moneyline_model.pkl', 'rb') as f:
                        self.models['moneyline'] = pickle.load(f)
                    
                    with open(f'{model_path}/underover_model.pkl', 'rb') as f:
                        self.models['underover'] = pickle.load(f)
                    
                    logger.info("NBA ML models loaded successfully")
                except Exception as e:
                    logger.warning(f"Could not load NBA models: {e}")
                    self._initialize_placeholder_models()
            else:
                logger.warning("Model files not found, using placeholder models")
                self._initialize_placeholder_models()
                
        except Exception as e:
            logger.error(f"Error loading NBA models: {e}")
            self._initialize_placeholder_models()
    
    def _initialize_placeholder_models(self):
        """Initialize placeholder models for testing"""
        logger.info("Initializing placeholder models")
        # These would be replaced with actual trained models
    
    async def predict_game(
        self,
        home_team: str,
        away_team: str,
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predict game outcome using ML models
        
        Args:
            home_team: Home team name
            away_team: Away team name
            features: Team features and statistics
            
        Returns:
            Prediction with probabilities and expected value
        """
        logger.info(f"Predicting {away_team} @ {home_team}")
        
        try:
            # Prepare features for model
            model_features = self._prepare_features(features)
            
            # Get predictions
            moneyline_pred = self._predict_moneyline(model_features)
            underover_pred = self._predict_underover(model_features)
            
            # Calculate expected value
            ev = self._calculate_expected_value(moneyline_pred, features.get('odds', {}))

            # Kelly Criterion for the best side using probability and odds
            best_side = ev.get('best_bet', 'home')
            side_prob = moneyline_pred['home_win_prob'] if best_side == 'home' else moneyline_pred['away_win_prob']
            american_odds = ev['home_odds'] if best_side == 'home' else ev['away_odds']

            def american_to_decimal(odds: float) -> float:
                return (odds / 100 + 1) if odds > 0 else (100 / abs(odds) + 1)

            kelly = self.bayesian.calculate_kelly_criterion(side_prob, american_to_decimal(american_odds))
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'moneyline_prediction': moneyline_pred,
                'underover_prediction': underover_pred,
                'expected_value': ev,
                'kelly_criterion': kelly,
                'confidence': moneyline_pred.get('confidence', 0.5),
                'method': 'ml_xgboost'
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                'error': str(e),
                'home_team': home_team,
                'away_team': away_team
            }
    
    def _prepare_features(self, features: Dict[str, Any]) -> pd.DataFrame:
        """Prepare features for ML model input.

        Ensure all features are numeric and fixed-width for model input.
        """
        home_recent = features.get('home_recent_form', [1, 1, 1, 0, 1])
        away_recent = features.get('away_recent_form', [1, 1, 0, 1, 0])

        def win_rate(seq: List[int]) -> float:
            if not seq:
                return 0.5
            return float(sum(int(x) for x in seq)) / float(len(seq))

        feature_dict: Dict[str, Any] = {
            'home_off_rating': float(features.get('home_off_rating', 110.0)),
            'home_def_rating': float(features.get('home_def_rating', 110.0)),
            'away_off_rating': float(features.get('away_off_rating', 110.0)),
            'away_def_rating': float(features.get('away_def_rating', 110.0)),
            'home_win_pct': float(features.get('home_win_pct', 0.5)),
            'away_win_pct': float(features.get('away_win_pct', 0.5)),
            'home_recent_win_rate': win_rate(home_recent),
            'away_recent_win_rate': win_rate(away_recent),
        }

        return pd.DataFrame([feature_dict])
    
    def _predict_moneyline(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Predict moneyline winner"""
        if 'moneyline' in self.models:
            model = self.models['moneyline']
            try:
                # Get prediction
                pred = model.predict_proba(features)[0]
                winner_prob = pred[1]  # Assuming 1 is home win
                
                return {
                    'winner': 'home' if winner_prob > 0.5 else 'away',
                    'home_win_prob': winner_prob,
                    'away_win_prob': 1 - winner_prob,
                    'confidence': abs(winner_prob - 0.5) * 2  # 0 to 1 scale
                }
            except Exception as e:
                logger.error(f"Moneyline prediction error: {e}")
        
        # Fallback to placeholder
        return {
            'winner': 'home',
            'home_win_prob': 0.55,
            'away_win_prob': 0.45,
            'confidence': 0.5
        }
    
    def _predict_underover(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Predict over/under"""
        if 'underover' in self.models:
            model = self.models['underover']
            try:
                pred = model.predict(features)[0]
                prob = model.predict_proba(features)[0]
                
                return {
                    'total_points': pred,
                    'over_prob': prob[1] if len(prob) > 1 else 0.5,
                    'under_prob': prob[0] if len(prob) > 1 else 0.5,
                    'recommendation': 'over' if prob[1] > 0.5 else 'under'
                }
            except Exception as e:
                logger.error(f"Under/over prediction error: {e}")
        
        # Fallback
        return {
            'total_points': 220,
            'over_prob': 0.52,
            'under_prob': 0.48,
            'recommendation': 'over'
        }
    
    def _calculate_expected_value(
        self,
        moneyline_pred: Dict[str, Any],
        odds: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate expected value for bets"""
        
        home_odds = odds.get('home', -110)
        away_odds = odds.get('away', 110)
        
        # Convert American odds to decimal
        def american_to_decimal(odds):
            if odds > 0:
                return odds / 100 + 1
            else:
                return 100 / abs(odds) + 1
        
        home_decimal = american_to_decimal(home_odds)
        away_decimal = american_to_decimal(away_odds)
        
        # Calculate EV
        home_ev = (moneyline_pred['home_win_prob'] * (home_decimal - 1)) - (1 - moneyline_pred['home_win_prob'])
        away_ev = (moneyline_pred['away_win_prob'] * (away_decimal - 1)) - (1 - moneyline_pred['away_win_prob'])
        
        return {
            'home_ev': home_ev,
            'away_ev': away_ev,
            'best_bet': 'home' if home_ev > away_ev else 'away',
            'home_odds': home_odds,
            'away_odds': away_odds
        }
    
    # Deprecated: prefer BayesianAnalyzer.calculate_kelly_criterion
    def _calculate_kelly(self, edge: float, probability: float) -> float:
        """Backward-compatible Kelly; prefer probability+odds based calculation."""
        if edge <= 0 or probability <= 0:
            return 0.0
        kelly = edge / (1 - probability)
        return min(kelly, 0.25)
    
    async def predict_today_games(self, sport: str = 'nba') -> List[Dict[str, Any]]:
        """
        Get predictions for today's games
        
        Args:
            sport: Sport to predict (currently NBA only)
            
        Returns:
            List of game predictions
        """
        logger.info(f"Getting predictions for today's {sport.upper()} games")
        
        # This would fetch today's games from an API
        # For now, return placeholder
        games = [
            {
                'home_team': 'Lakers',
                'away_team': 'Warriors',
                'features': {
                    'home_off_rating': 115.2,
                    'home_def_rating': 112.5,
                    'away_off_rating': 118.0,
                    'away_def_rating': 113.8,
                    'home_win_pct': 0.55,
                    'away_win_pct': 0.62,
                    'home_recent_form': [1, 1, 0, 1, 1],
                    'away_recent_form': [1, 0, 1, 1, 1],
                    'odds': {'home': -110, 'away': -110},
                    'over_under': 230.5
                }
            }
        ]
        
        predictions = []
        for game in games:
            pred = await self.predict_game(
                game['home_team'],
                game['away_team'],
                game['features']
            )
            predictions.append(pred)
        
        return predictions

