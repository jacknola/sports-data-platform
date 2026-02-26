"""
Train NCAAB Moneyline Model

Pulls completed NCAAB games from the database, enriches each game with current
ESPN BPI efficiency stats, and trains an XGBoost binary classifier to predict
the home team win probability.

Usage:
    cd backend
    python train_ncaab_model.py               # train on last 365 days
    python train_ncaab_model.py --days 730    # expand to 2 seasons
    python train_ncaab_model.py --dry-run     # show data shape, skip training

Outputs:
    backend/models/ncaab_ml/moneyline_model.pkl
"""

import asyncio
import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("logs", exist_ok=True)
logger.add("logs/train_ncaab.log", rotation="7 days", level="INFO")

from app.config import settings  # noqa: E402
from app.models.game import Game  # noqa: E402
from app.services.ncaab_stats_service import NCAABStatsService  # noqa: E402

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

FEATURE_COLS = [
    "home_adj_oe",
    "home_adj_de",
    "away_adj_oe",
    "away_adj_de",
    "home_bpi",
    "away_bpi",
    "spread",
]
MIN_SAMPLES = 30
MODEL_DIR = "./models/ncaab_ml"


# ── Data loading ──────────────────────────────────────────────────────────────

def fetch_ncaab_games(db: Session, days: int) -> pd.DataFrame:
    """Pull completed NCAAB games from the database."""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    games = (
        db.query(Game)
        .filter(
            Game.sport == "ncaab",
            Game.game_date >= cutoff,
            Game.home_score.isnot(None),
            Game.away_score.isnot(None),
        )
        .all()
    )

    rows = []
    for g in games:
        rows.append({
            "home_team": g.home_team,
            "away_team": g.away_team,
            "home_score": g.home_score,
            "away_score": g.away_score,
            "home_win": int(g.home_score > g.away_score),
        })

    logger.info(f"Fetched {len(rows)} completed NCAAB games from DB")
    return pd.DataFrame(rows)


def enrich_with_bpi(df: pd.DataFrame, team_stats: dict) -> pd.DataFrame:
    """Attach ESPN BPI stats to each game row."""
    _LEAGUE_AVG = 106.0

    def get_stat(team_name: str, field: str, default: float) -> float:
        # Substring fuzzy match (mirrors NCAABStatsService.get_team_stats)
        for name, stats in team_stats.items():
            if name.lower() in team_name.lower() or team_name.lower() in name.lower():
                return float(stats.get(field, default))
        return default

    df = df.copy()
    df["home_adj_oe"] = df["home_team"].apply(lambda t: get_stat(t, "AdjOE", _LEAGUE_AVG))
    df["home_adj_de"] = df["home_team"].apply(lambda t: get_stat(t, "AdjDE", _LEAGUE_AVG))
    df["home_bpi"]    = df["home_team"].apply(lambda t: get_stat(t, "BPI", 0.0))
    df["away_adj_oe"] = df["away_team"].apply(lambda t: get_stat(t, "AdjOE", _LEAGUE_AVG))
    df["away_adj_de"] = df["away_team"].apply(lambda t: get_stat(t, "AdjDE", _LEAGUE_AVG))
    df["away_bpi"]    = df["away_team"].apply(lambda t: get_stat(t, "BPI", 0.0))
    df["spread"]      = 0.0  # spread data not stored in DB yet — placeholder

    return df


# ── Training ──────────────────────────────────────────────────────────────────

def train(X: pd.DataFrame, y: np.ndarray) -> object:
    """Train XGBoost binary classifier and return the fitted model."""
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X, y)
    return model


def evaluate(model, X: pd.DataFrame, y: np.ndarray) -> None:
    """Print basic evaluation metrics."""
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
    proba = model.predict_proba(X)[:, 1]
    preds = (proba >= 0.5).astype(int)
    print(f"\n  Accuracy : {accuracy_score(y, preds):.3f}")
    print(f"  Log-loss : {log_loss(y, proba):.4f}")
    print(f"  ROC-AUC  : {roc_auc_score(y, proba):.3f}")

    fi = pd.Series(model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    print("\n  Feature importance:")
    for feat, imp in fi.items():
        print(f"    {feat:<20} {imp:.4f}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(days: int, dry_run: bool) -> None:
    if not XGBOOST_AVAILABLE:
        print("ERROR: xgboost not installed. Run: pip install xgboost")
        sys.exit(1)

    # 1. Fetch BPI stats
    stats_svc = NCAABStatsService()
    print("Fetching ESPN BPI team stats…")
    team_stats = await stats_svc.fetch_all_team_stats()
    print(f"  Got stats for {len(team_stats)} teams")

    # 2. Load game data from DB
    engine = create_engine(str(settings.DATABASE_URL))
    with Session(engine) as db:
        df = fetch_ncaab_games(db, days)

    if df.empty:
        print(f"\nNo completed NCAAB games found in the last {days} days.")
        print("Run run_ncaab_backfill.py to populate the database first.")
        return

    # 3. Enrich with BPI
    df = enrich_with_bpi(df, team_stats)
    X = df[FEATURE_COLS]
    y = df["home_win"].values

    print(f"\n  Training samples : {len(X)}")
    print(f"  Home win rate    : {y.mean():.1%}")
    print(f"  Features         : {FEATURE_COLS}")

    if dry_run:
        print("\n--dry-run: skipping training.")
        return

    if len(X) < MIN_SAMPLES:
        print(f"\nNot enough data ({len(X)} < {MIN_SAMPLES} required).")
        print("The predictor will use the Pythagorean fallback until more games are backfilled.")
        return

    # 4. Train
    print("\nTraining XGBoost moneyline model…")
    model = train(X, y)

    # 5. Evaluate (in-sample; use walk-forward for proper backtest)
    print("\nIn-sample evaluation:")
    evaluate(model, X, y)

    # 6. Save
    os.makedirs(MODEL_DIR, exist_ok=True)
    out_path = os.path.join(MODEL_DIR, "moneyline_model.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nModel saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train NCAAB moneyline model")
    parser.add_argument("--days", type=int, default=365, help="Days of history to use")
    parser.add_argument("--dry-run", action="store_true", help="Show data shape, skip training")
    args = parser.parse_args()

    asyncio.run(main(days=args.days, dry_run=args.dry_run))
