"""
Comparison runner for evaluating multiple betting models.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
import numpy as np
from app.services.data_extraction import DataExtractor
from app.services.feature_engineering import FeatureEngineer
from app.services.stats_feature_engineering import StatsFeatureEngineer
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
        self.stats_engineer = StatsFeatureEngineer(sport="nba")
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

        X, y = self.stats_engineer.prepare_training_features(data)
        if len(X) == 0:
            logger.warning(
                "Stats-only feature prep returned empty. Falling back to legacy features."
            )
            X, y = self.engineer.prepare_features(data)

        if len(X) < 2:
            logger.warning("Insufficient data for training and evaluation")
            return {}

        # 3. Split data (for simplicity, we train and evaluate on the same for baseline)
        # In a real scenario, we'd use walk-forward validation

        # 4. Bayesian Evaluation (predictions already in data)
        if "posterior_prob" in X.columns:
            bayesian_probs = X["posterior_prob"].values
        else:
            bayesian_probs = np.full(len(X), 0.5)

        # Filter rows where Bayesian prob exists
        valid_idx = ~np.isnan(bayesian_probs)

        # We need the odds for ROI calculation
        odds = (
            X["current_odds"].values
            if "current_odds" in X.columns
            else np.ones(len(X)) * 2.0
        )

        # Flat bets of $10 for comparison
        bets = np.ones(len(X)) * 10.0

        bayesian_results = self.evaluator.evaluate_model(
            probs=bayesian_probs[valid_idx],
            odds=odds[valid_idx],
            outcomes=y[valid_idx],
            bets=bets[valid_idx],
        )

        rf_model = RandomForestModel(n_estimators=100)
        rf_train_X = X.drop(
            columns=["posterior_prob", "edge", "game_id", "season"], errors="ignore"
        )
        rf_model.train(rf_train_X, y)
        rf_probs = rf_model.predict_proba(rf_train_X)

        rf_results = self.evaluator.evaluate_model(
            probs=rf_probs, odds=odds, outcomes=y, bets=bets
        )

        results = {
            "sport": sport,
            "days": days,
            "sample_size": len(X),
            "bayesian_feature_set": "posterior_prob from historical bets (or neutral 0.5 fallback)",
            "rf_feature_set": "stats-only (elo, ratings, rolling four factors, context)",
            "bayesian": bayesian_results,
            "random_forest": rf_results,
            "feature_importance": rf_model.get_feature_importance().to_dict(),
        }

        logger.info("Comparison complete")
        return results

    @staticmethod
    def format_report(results: Dict[str, Any]) -> str:
        """
        Format comparison results into a human-readable report.
        """
        if not results:
            return "No results to report."

        sport = results["sport"].upper()
        days = results["days"]
        n = results["sample_size"]

        bayesian = results["bayesian"]
        rf = results["random_forest"]

        report = [
            f"{'=' * 40}",
            f" {sport} MODEL COMPARISON REPORT ({days} DAYS)",
            f" Sample Size: {n} bets",
            f"{'=' * 40}",
            "",
            "Bayesian Model:",
            f"  Brier Score: {bayesian['brier_score']:.4f}",
            f"  ROI:         {bayesian['roi'] * 100:.2f}%",
            f"  Win Rate:    {bayesian['win_rate'] * 100:.2f}%",
            "",
            "Random Forest Model:",
            f"  Brier Score: {rf['brier_score']:.4f}",
            f"  ROI:         {rf['roi'] * 100:.2f}%",
            f"  Win Rate:    {rf['win_rate'] * 100:.2f}%",
            f"  Feature Set: {results.get('rf_feature_set', 'N/A')}",
            "",
            "Feature Importances (RF):",
        ]

        for feat, imp in list(results.get("feature_importance", {}).items())[:5]:
            report.append(f"  {feat:15}: {imp:.4f}")

        report.append(f"{'=' * 40}")

        return "\n".join(report)
