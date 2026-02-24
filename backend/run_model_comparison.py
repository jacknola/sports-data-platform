"""
Model Comparison Analysis — Baseline Performance

Runs a side-by-side comparison between the Bayesian Multi-Agent 
and the Random Forest ML model using historical project data.
"""

import sys
import os
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.database import SessionLocal
from app.services.comparison_runner import ComparisonRunner

def run_predictions_comparison(sport: str = "nba", days: int = 30):
    """
    Run the model comparison and print the report.
    """
    print("\n" + "=" * 76)
    print(f"  MODEL COMPARISON PREDICTIONS — {datetime.now().strftime('%A, %B %d, %Y')}")
    print(f"  Target: {sport.upper()} | Range: Last {days} days")
    print("=" * 76)

    db = SessionLocal()
    try:
        runner = ComparisonRunner(db)
        results = runner.run_comparison(sport=sport, days=days)
        
        if results:
            report = runner.format_report(results)
            print("\n" + report)
            
            # Recommendation logic
            bayesian_roi = results["bayesian"]["roi"]
            rf_roi = results["random_forest"]["roi"]
            
            print("\n" + "─" * 76)
            print("  STRATEGIC RECOMMENDATION")
            print("─" * 76)
            
            if bayesian_roi > rf_roi:
                print(f"\n  ★ Current Champion: BAYESIAN MODEL (+{(bayesian_roi - rf_roi)*100:.2f}% ROI edge)")
                print("  The Bayesian Multi-Agent system remains superior for this dataset.")
            else:
                print(f"\n  ★ Current Champion: RANDOM FOREST (+{(rf_roi - bayesian_roi)*100:.2f}% ROI edge)")
                print("  The Random Forest ML model is outperforming the Bayesian baseline.")
                
            print("\n  Note: This comparison uses walk-forward 'backtesting' logic on your local DB.")
            print("=" * 76 + "\n")
            
        else:
            print("\n  No historical data found in your database to run comparison.")
            print("  Please ensure you have games with results and bets saved.")
            print("=" * 76 + "\n")
            
    finally:
        db.close()

if __name__ == "__main__":
    # You can customize these parameters
    sport_to_check = os.getenv("SPORT", "nba")
    days_to_check = int(os.getenv("DAYS", "30"))
    
    run_predictions_comparison(sport=sport_to_check, days=days_to_check)
