"""
Train Player Props XGBoost Model

Uses historical player game logs from the database (pts, reb, ast, etc.) to
train a binary XGBoost classifier that predicts whether a player will go OVER
a given prop line.

Features mirror the 10-feature vector used by inference_service.py so that
the global XGBoost model and the localized Qdrant-RF model are comparable.

Usage:
    cd backend
    python train_prop_model.py                        # NBA points props, 365 days
    python train_prop_model.py --stat pts --days 730  # expand to 2 seasons
    python train_prop_model.py --stat reb             # rebounds model
    python train_prop_model.py --dry-run              # show data shape only

Outputs:
    backend/models/prop_ml/<stat>_model.pkl
    backend/models/prop_scaler.joblib   (updated StandardScaler)
"""

import argparse
import asyncio
import os
import pickle
import sys

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("logs", exist_ok=True)
logger.add("logs/train_prop.log", rotation="7 days", level="INFO")

from app.config import settings  # noqa: E402
from app.models.player_game_log import PlayerGameLog  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.team import Team  # noqa: E402
from app.models.game import Game  # noqa: E402

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ── Constants ─────────────────────────────────────────────────────────────────

STAT_COLS = {
    "pts":  "pts",
    "reb":  "reb",
    "ast":  "ast",
    "fg3m": "fg3m",
    "stl":  "stl",
    "blk":  "blk",
    "pra":  "pra",
}

# Maps to inference_service.py FEATURE_NAMES
FEATURE_NAMES = [
    "usage_rate_season",
    "l5_form_variance",
    "expected_mins",
    "opp_pace",
    "opp_def_rtg",
    "def_vs_position",
    "implied_team_total",
    "spread",
    "rest_advantage",
    "is_home",
]

MIN_SAMPLES = 50
MODEL_BASE_DIR = "./models/prop_ml"
SCALER_PATH = "./models/prop_scaler.joblib"


# ── Data loading ──────────────────────────────────────────────────────────────

def fetch_prop_logs(db: Session, stat: str, days: int) -> pd.DataFrame:
    """
    Pull historical player game logs with contextual features.

    We use the `scenario` JSON field (populated by sync_qdrant / backfill)
    which stores features like opp_pace, opp_def_rtg, expected_mins, etc.
    Falls back to sensible defaults for missing fields.
    """
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    logs = (
        db.query(PlayerGameLog)
        .join(Game, PlayerGameLog.game_id == Game.id)
        .filter(
            PlayerGameLog.game_date >= cutoff,
            getattr(PlayerGameLog, stat).isnot(None),
            PlayerGameLog.min.isnot(None),
        )
        .all()
    )

    logger.info(f"Fetched {len(logs)} player-game logs for stat={stat}")
    rows = []

    for log in logs:
        actual = getattr(log, stat, None)
        if actual is None:
            continue

        sc = log.scenario or {}
        rows.append({
            # Target stat
            "actual": float(actual),
            # Feature: minutes (proxy for usage / expected output)
            "expected_mins":       float(log.min or sc.get("expected_mins", 28.0)),
            # From scenario JSON (populated by backfill/sync)
            "usage_rate_season":   float(sc.get("usage_rate_season", 20.0)),
            "l5_form_variance":    float(sc.get("l5_form_variance", 5.0)),
            "opp_pace":            float(sc.get("opp_pace", 68.0)),
            "opp_def_rtg":         float(sc.get("opp_def_rtg", 106.0)),
            "def_vs_position":     float(sc.get("def_vs_position", 0.0)),
            "implied_team_total":  float(sc.get("implied_team_total", 110.0)),
            "spread":              float(sc.get("spread", 0.0)),
            "rest_advantage":      float(sc.get("rest_advantage", 0.0)),
            "is_home":             float(sc.get("is_home", 0.0)),
        })

    return pd.DataFrame(rows)


def build_label(df: pd.DataFrame, prop_line: float) -> np.ndarray:
    """Binary label: 1 = player went OVER prop_line, 0 = under."""
    return (df["actual"] > prop_line).astype(int).values


def estimate_prop_lines(df: pd.DataFrame) -> pd.Series:
    """
    When no historical prop lines are stored, use each player's rolling
    season mean as a synthetic line (tests model's ability to predict
    above/below expectation).
    """
    return df["actual"].expanding().mean().shift(1).fillna(df["actual"].mean())


# ── Training ──────────────────────────────────────────────────────────────────

def fit_scaler(X: pd.DataFrame) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(X)
    return scaler


def train_model(X: pd.DataFrame, y: np.ndarray) -> object:
    model = xgb.XGBClassifier(
        n_estimators=300,
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
    proba = model.predict_proba(X)[:, 1]
    preds = (proba >= 0.5).astype(int)
    print(f"\n  Accuracy : {accuracy_score(y, preds):.3f}")
    print(f"  Log-loss : {log_loss(y, proba):.4f}")
    print(f"  ROC-AUC  : {roc_auc_score(y, proba):.3f}")
    print(f"  Over rate: {y.mean():.1%}  (baseline to beat)")

    fi = pd.Series(model.feature_importances_, index=FEATURE_NAMES).sort_values(ascending=False)
    print("\n  Feature importance:")
    for feat, imp in fi.items():
        print(f"    {feat:<25} {imp:.4f}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(stat: str, days: int, dry_run: bool) -> None:
    if not XGBOOST_AVAILABLE:
        print("ERROR: xgboost not installed. Run: pip install xgboost")
        sys.exit(1)
    if not SKLEARN_AVAILABLE:
        print("ERROR: scikit-learn not installed. Run: pip install scikit-learn")
        sys.exit(1)

    print(f"Training props model: stat={stat}, days={days}")

    engine = create_engine(str(settings.DATABASE_URL))
    with Session(engine) as db:
        df = fetch_prop_logs(db, stat, days)

    if df.empty:
        print(f"\nNo player game logs found for stat={stat} in last {days} days.")
        print("Run backend/run_backfill_pipeline.py to populate player data first.")
        return

    # Use rolling season mean as synthetic prop line
    prop_lines = estimate_prop_lines(df)
    y = (df["actual"] > prop_lines).astype(int).values

    X = df[FEATURE_NAMES]

    print(f"\n  Training samples : {len(X)}")
    print(f"  Over rate        : {y.mean():.1%}")
    print(f"  Mean actual {stat:4s} : {df['actual'].mean():.1f}")
    print(f"  Mean prop line   : {prop_lines.mean():.1f}")

    if dry_run:
        print("\n--dry-run: skipping training.")
        return

    if len(X) < MIN_SAMPLES:
        print(f"\nNot enough data ({len(X)} < {MIN_SAMPLES} required). Collect more game logs.")
        return

    # Fit / update scaler
    scaler = fit_scaler(X)
    X_scaled = pd.DataFrame(scaler.transform(X), columns=FEATURE_NAMES)

    # Train
    print(f"\nTraining XGBoost props model for {stat}…")
    model = train_model(X_scaled, y)

    # Evaluate
    print("\nIn-sample evaluation:")
    evaluate(model, X_scaled, y)

    # Save model
    os.makedirs(MODEL_BASE_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_BASE_DIR, f"{stat}_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nModel saved → {model_path}")

    # Save updated scaler
    os.makedirs(os.path.dirname(SCALER_PATH) if os.path.dirname(SCALER_PATH) else ".", exist_ok=True)
    joblib.dump(scaler, SCALER_PATH)
    print(f"Scaler saved → {SCALER_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train player props XGBoost model")
    parser.add_argument(
        "--stat",
        choices=list(STAT_COLS.keys()),
        default="pts",
        help="Stat type to train on (default: pts)",
    )
    parser.add_argument("--days", type=int, default=365, help="Days of history")
    parser.add_argument("--dry-run", action="store_true", help="Show data shape, skip training")
    args = parser.parse_args()

    main(stat=args.stat, days=args.days, dry_run=args.dry_run)
