"""
Comparison runner for evaluating multiple betting models.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
import numpy as np
from app.services.data_extraction import DataExtractor
from app.services.feature_engineering import FeatureEngineer
from app.services.random_forest_model import RandomForestModel
from app.services.evaluation_metrics import Evaluator
from loguru import logger

class ComparisonRunner:
    """
    Service for running end-to-end model comparisons.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.extractor = DataExtractor(db)
        self.engineer = FeatureEngineer()
        self.evaluator = Evaluator()

    def run_comparison(self, sport: str = "nba", days: int = 30) -> Dict[str, Any]:
        """
        Run comparison between Bayesian and Random Forest models.
        """
        logger.info(f"Starting model comparison for {sport} ({days} days)")
        
        # 1. Fetch data
        data = self.extractor.fetch_historical_data(sport=sport, days=days)
        if not data:
            logger.warning("No data found for comparison")
            return {}
            
        # 2. Prepare features and labels
        X, y = self.engineer.prepare_features(data)
        if len(X) < 2:
            logger.warning("Insufficient data for training and evaluation")
            return {}
            
        # 3. Split data (for simplicity, we train and evaluate on the same for baseline)
        # In a real scenario, we'd use walk-forward validation
        
        # 4. Bayesian Evaluation (predictions already in data)
        bayesian_probs = X["posterior_prob"].values
        # Filter rows where Bayesian prob exists
        valid_idx = ~np.isnan(bayesian_probs)
        
        # We need the odds for ROI calculation
        odds = X["current_odds"].values if "current_odds" in X.columns else np.ones(len(X)) * 2.0
        
        # Flat bets of $10 for comparison
        bets = np.ones(len(X)) * 10.0
        
        bayesian_results = self.evaluator.evaluate_model(
            probs=bayesian_probs[valid_idx],
            odds=odds[valid_idx],
            outcomes=y[valid_idx],
            bets=bets[valid_idx]
        )
        
        # 5. Random Forest Evaluation
        rf_model = RandomForestModel(n_estimators=100)
        # Again, for baseline comparison, we train on the same data
        rf_model.train(X.drop(columns=["posterior_prob", "edge"], errors="ignore"), y)
        rf_probs = rf_model.predict_proba(X.drop(columns=["posterior_prob", "edge"], errors="ignore"))
        
        rf_results = self.evaluator.evaluate_model(
            probs=rf_probs,
            odds=odds,
            outcomes=y,
            bets=bets
        )
        
        results = {
            "sport": sport,
            "days": days,
            "sample_size": len(X),
            "bayesian": bayesian_results,
            "random_forest": rf_results,
            "feature_importance": rf_model.get_feature_importance().to_dict()
        }
        
        logger.info("Comparison complete")
        return results
