"""
Unit tests for reporting utility.
"""
import pytest
from app.services.comparison_runner import ComparisonRunner

def test_format_report():
    results = {
        "sport": "nba",
        "days": 30,
        "sample_size": 100,
        "bayesian": {
            "brier_score": 0.15,
            "roi": 0.05,
            "win_rate": 0.55
        },
        "random_forest": {
            "brier_score": 0.18,
            "roi": 0.02,
            "win_rate": 0.52
        },
        "feature_importance": {"implied_prob": 0.8, "is_home": 0.2}
    }
    
    report = ComparisonRunner.format_report(results)
    
    assert "NBA MODEL COMPARISON REPORT" in report
    assert "Bayesian Model" in report
    assert "Random Forest Model" in report
    assert "0.15" in report
    assert "5.00%" in report
