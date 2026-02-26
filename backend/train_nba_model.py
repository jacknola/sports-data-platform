"""
NBA ML Model Training Script
Fetches historical data from DB and trains XGBoost models.
"""

import os
import sys
import pickle
import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import select
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.game import Game
from app.models.team import Team

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("XGBoost not installed. Run: pip install xgboost")

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "nba_ml")

def fetch_data():
    """Fetch games and team stats from the database."""
    db = SessionLocal()
    try:
        # Fetch all completed games
        stmt = select(Game).where(Game.home_score.isnot(None))
        games = db.execute(stmt).scalars().all()
        
        # Fetch all teams for stats lookup
        stmt_teams = select(Team)
        teams = db.execute(stmt_teams).scalars().all()
        team_stats = {t.name: t.stats for t in teams if t.stats}
        
        return games, team_stats
    finally:
        db.close()

def prepare_dataset(games, team_stats):
    """Transform DB models into training features."""
    # Convert games to a DataFrame for easier rolling stats calculation
    game_list = []
    for g in games:
        game_list.append({
            "date": g.game_date,
            "home": g.home_team,
            "away": g.away_team,
            "h_score": g.home_score,
            "a_score": g.away_score
        })
    
    games_df = pd.DataFrame(game_list).sort_values("date")
    
    # Calculate rolling averages for each team
    team_metrics = {}
    
    # We'll build features for each game based on team performance BEFORE that game
    data = []
    
    for idx, row in games_df.iterrows():
        h = row["home"]
        a = row["away"]
        
        # Get metrics for home team
        h_perf = team_metrics.get(h, {"off": 110.0, "def": 110.0, "wins": 0, "games": 0})
        # Get metrics for away team
        a_perf = team_metrics.get(a, {"off": 110.0, "def": 110.0, "wins": 0, "games": 0})
        
        # Add sample to training set (using stats from BEFORE this game)
        data.append({
            "home_off_rating": h_perf["off"],
            "home_def_rating": h_perf["def"],
            "away_off_rating": a_perf["off"],
            "away_def_rating": a_perf["def"],
            "home_win_pct": h_perf["wins"] / h_perf["games"] if h_perf["games"] > 0 else 0.5,
            "away_win_pct": a_perf["wins"] / a_perf["games"] if a_perf["games"] > 0 else 0.5,
            "home_win": 1 if row["h_score"] > row["a_score"] else 0,
            "total_points": row["h_score"] + row["a_score"]
        })
        
        # Update team metrics with THIS game's results for future games
        def update_team(team, scored, allowed, won):
            curr = team_metrics.get(team, {"off": 110.0, "def": 110.0, "wins": 0, "games": 0})
            # Simple alpha-decay rolling average
            alpha = 0.2
            curr["off"] = (1 - alpha) * curr["off"] + alpha * scored
            curr["def"] = (1 - alpha) * curr["def"] + alpha * allowed
            curr["wins"] += 1 if won else 0
            curr["games"] += 1
            team_metrics[team] = curr
            
        update_team(h, row["h_score"], row["a_score"], row["h_score"] > row["a_score"])
        update_team(a, row["a_score"], row["h_score"], row["a_score"] > row["h_score"])
            
    return pd.DataFrame(data)

def train_models(df):
    """Train ML models using XGBoost."""
    if df.empty:
        logger.error("No data available for training. Run backfill first!")
        return
    
    X = df.drop(columns=["home_win", "total_points"])
    y_ml = df["home_win"]
    y_uo = df["total_points"]
    
    # 1. Moneyline Model (Classification)
    logger.info("Training Moneyline Model...")
    X_train, X_test, y_train, y_test = train_test_split(X, y_ml, test_size=0.2, random_state=42)
    
    ml_model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    )
    ml_model.fit(X_train, y_train)
    
    ml_preds = ml_model.predict(X_test)
    logger.info(f"Moneyline Accuracy: {accuracy_score(y_test, ml_preds):.2%}")
    
    # 2. Over/Under Model (Regression)
    logger.info("Training Over/Under Model...")
    X_train, X_test, y_train, y_test = train_test_split(X, y_uo, test_size=0.2, random_state=42)
    
    uo_model = xgb.XGBRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    )
    uo_model.fit(X_train, y_train)
    
    uo_preds = uo_model.predict(X_test)
    logger.info(f"Total Points MAE: {mean_absolute_error(y_test, uo_preds):.2f}")
    
    # Save models
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "moneyline_model.pkl"), "wb") as f:
        pickle.dump(ml_model, f)
    with open(os.path.join(MODEL_DIR, "underover_model.pkl"), "wb") as f:
        pickle.dump(uo_model, f)
        
    logger.info(f"Models saved to {MODEL_DIR}")

def main():
    if not XGBOOST_AVAILABLE:
        sys.exit(1)
        
    logger.info("Fetching data from DB...")
    games, team_stats = fetch_data()
    
    if not games:
        logger.warning("No historical games found in DB. Searching for backfill script...")
        # If no games, let's suggest running backfill
        return
        
    logger.info(f"Preparing features for {len(games)} games...")
    df = prepare_dataset(games, team_stats)
    
    logger.info(f"Training on {len(df)} samples...")
    train_models(df)

if __name__ == "__main__":
    main()
