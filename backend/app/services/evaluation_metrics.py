"""
Evaluation metrics for betting model performance.
"""
from typing import Dict, Any
import numpy as np

class Evaluator:
    """
    Service for calculating performance metrics for betting models.
    """
    
    def calculate_brier_score(self, probs: np.ndarray, outcomes: np.ndarray) -> float:
        """
        Calculate the Brier Score (mean squared error of probabilities).
        
        Args:
            probs: Array of predicted probabilities.
            outcomes: Array of binary outcomes (0 or 1).
            
        Returns:
            Brier score (lower is better).
        """
        return float(np.mean((probs - outcomes) ** 2))

    def calculate_roi(self, probs: np.ndarray, odds: np.ndarray, outcomes: np.ndarray, bets: np.ndarray) -> float:
        """
        Calculate the Return on Investment (ROI).
        
        Args:
            probs: Array of predicted probabilities (unused for ROI directly, but useful for filtering).
            odds: Array of decimal odds.
            outcomes: Array of binary outcomes (0 or 1).
            bets: Array of bet amounts.
            
        Returns:
            ROI as a decimal (e.g., 0.05 for 5% ROI).
        """
        total_investment = np.sum(bets)
        if total_investment == 0:
            return 0.0
            
        # Payout = bet * odds if win, 0 if loss
        payouts = bets * odds * outcomes
        total_profit = np.sum(payouts) - total_investment
        
        return float(total_profit / total_investment)

    def evaluate_model(self, probs: np.ndarray, odds: np.ndarray, outcomes: np.ndarray, bets: np.ndarray) -> Dict[str, Any]:
        """
        Calculate all metrics for a model.
        """
        return {
            "brier_score": self.calculate_brier_score(probs, outcomes),
            "roi": self.calculate_roi(probs, odds, outcomes, bets),
            "total_bets": len(bets),
            "win_rate": float(np.mean(outcomes)) if len(outcomes) > 0 else 0.0
        }
