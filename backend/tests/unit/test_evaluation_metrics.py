"""
Unit tests for evaluation metrics utility.
"""
import pytest
import numpy as np
from app.services.evaluation_metrics import Evaluator

def test_calculate_brier_score():
    probs = np.array([0.8, 0.4, 0.2])
    outcomes = np.array([1, 0, 0])
    
    # (0.8-1)^2 = 0.04
    # (0.4-0)^2 = 0.16
    # (0.2-0)^2 = 0.04
    # Mean = (0.04 + 0.16 + 0.04) / 3 = 0.08
    
    evaluator = Evaluator()
    score = evaluator.calculate_brier_score(probs, outcomes)
    
    assert score == pytest.approx(0.08)

def test_calculate_roi():
    probs = np.array([0.6, 0.7, 0.4])
    odds = np.array([2.0, 1.5, 3.0])  # Decimal odds
    outcomes = np.array([1, 1, 0])
    bets = np.array([10, 10, 10])  # $10 flat bets
    
    # Bet 1: Win, Payout = 10 * 2.0 = 20, Profit = 10
    # Bet 2: Win, Payout = 10 * 1.5 = 15, Profit = 5
    # Bet 3: Loss, Payout = 0, Profit = -10
    # Total Profit = 10 + 5 - 10 = 5
    # Total Investment = 30
    # ROI = 5 / 30 = 0.1666...
    
    evaluator = Evaluator()
    roi = evaluator.calculate_roi(probs, odds, outcomes, bets)
    
    assert roi == pytest.approx(5/30)
