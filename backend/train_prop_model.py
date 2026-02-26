"""
Train Player Props XGBoost Model

Uses historical player game logs from the database to train a binary XGBoost
classifier that predicts whether a player will go OVER a given prop line.

Features 1-3 and 9-10 are computed via PostgreSQL window functions (same SQL
as sync_qdrant.py), ensuring point-in-time correctness (no data leakage).
Features 4-8 are read from PlayerGameLog.scenario, populated by
backfill_scenario.py. When scenario is NULL those features default to
league-average values identical to what sync_qdrant.py / inference_service.py
use at inference time — so the training distribution matches.

Usage:
    cd backend
    python train_prop_model.py                        # NBA points props, 365 days
    python train_prop_model.py --stat pts --days 730  # expand to 2 seasons
    python train_prop_model.py --stat reb             # rebounds model
    python train_prop_model.py --dry-run              # show data shape only

Run backfill_scenario.py first to populate opp_pace/opp_def_rtg in scenario
so that features 4-8 reflect real matchup context instead of league averages.

Outputs:
    backend/models/prop_ml/<stat>_model.pkl
    backend/models/prop_scaler.joblib   (updated StandardScaler)
"""

import argparse
import os
import pickle
import sys

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("logs", exist_ok=True)
logger.add("logs/train_prop.log", rotation="7 days", level="INFO")

from app.config import settings  # noqa: E402

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

# Maps stat name -> column name on player_game_logs
STAT_COLS = {
    "pts":  "pts",
    "reb":  "reb",
    "ast":  "ast",
    "fg3m": "fg3m",
    "stl":  "stl",
    "blk":  "blk",
    "pra":  "pra",
}

# Must match FEATURE_NAMES in sync_qdrant.py and inference_service.py exactly
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

# Defaults must stay in sync with sync_qdrant.py COALESCE fallbacks so that
# the training distribution matches what the model sees at inference time.
_SCENARIO_DEFAULTS = {
    "opp_pace":           100.0,
    "opp_def_rtg":        112.0,
    "def_vs_position":      0.0,
    "implied_team_total": 112.5,
    "spread":               0.0,
}


# ── SQL ────────────────────────────────────────────────────────────────────────
# Mirrors sync_qdrant.py's point-in-time window-function SQL.
# Parameters:
#   :stat_col — the target stat column (pts / reb / ast / etc.)
#   :cutoff   — earliest game_date to include
#
# Features 1-3 and 9-10 are computed from real data using window functions.
# Features 4-8 are read from scenario JSON (backfill_scenario.py populates
# them; COALESCE fallbacks match sync_qdrant.py defaults exactly).
_SQL_TEMPLATE = """
WITH pit AS (
    SELECT
        pgl.id                                                                  AS log_id,
        pgl.player_id,
        pgl.game_id,
        pgl.game_date,
        pgl.{stat_col}                                                          AS actual_value,

        -- Feature 1: Usage Rate (Season) — pts/min * 36, prior games only
        COALESCE(
            AVG(pgl.pts)  OVER w_season
            / NULLIF(AVG(pgl.min) OVER w_season, 0)
            * 36.0,
            18.0
        )                                                                       AS usage_rate_season,

        -- Feature 2: L5 Form Variance — variance of TARGET stat over last 5 games
        COALESCE(VAR_SAMP(pgl.{stat_col}) OVER w_l5, 25.0)                     AS l5_form_variance,

        -- Feature 3: Expected Minutes
        COALESCE(AVG(pgl.min) OVER w_season, 24.0)                             AS expected_mins,

        -- Feature 9: Rest Advantage (days since previous game)
        COALESCE(
            EXTRACT(EPOCH FROM (
                pgl.game_date
                - LAG(pgl.game_date) OVER (
                    PARTITION BY pgl.player_id ORDER BY pgl.game_date
                )
            )) / 86400.0,
            2.0
        )                                                                       AS rest_advantage,

        -- Feature 10: Home/Away (1 = home)
        CASE WHEN t.name = g.home_team THEN 1 ELSE 0 END                       AS is_home,

        -- Features 4-8: from scenario JSON (populated by backfill_scenario.py)
        -- Defaults match sync_qdrant.py COALESCE values so training ≈ inference
        COALESCE((pgl.scenario->>'opp_pace')::float,          100.0)            AS opp_pace,
        COALESCE((pgl.scenario->>'opp_def_rtg')::float,       112.0)            AS opp_def_rtg,
        COALESCE((pgl.scenario->>'def_vs_position')::float,     0.0)            AS def_vs_position,
        COALESCE((pgl.scenario->>'implied_team_total')::float, 112.5)           AS implied_team_total,
        COALESCE((pgl.scenario->>'spread')::float,               0.0)           AS spread

    FROM  player_game_logs  pgl
    JOIN  games             g   ON g.id  = pgl.game_id
    JOIN  teams             t   ON t.id  = pgl.team_id

    WHERE pgl.{stat_col} IS NOT NULL
      AND pgl.min IS NOT NULL
      AND pgl.min > 0
      AND pgl.game_date >= :cutoff

    WINDOW
        w_season AS (
            PARTITION BY pgl.player_id
            ORDER BY pgl.game_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ),
        w_l5 AS (
            PARTITION BY pgl.player_id
            ORDER BY pgl.game_date
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        )
)
SELECT *
FROM   pit
WHERE  usage_rate_season > 0
ORDER  BY game_date ASC
"""

_RESULT_COLUMNS = [
    "log_id", "player_id", "game_id", "game_date", "actual_value",
    *FEATURE_NAMES,
]


# ── Data loading ──────────────────────────────────────────────────────────────

def fetch_prop_logs(engine, stat: str, days: int) -> pd.DataFrame:
    """
    Pull historical player game logs with point-in-time computed features.

    Features 1-3 and 9-10 are derived from window functions over real game
    data (no leakage). Features 4-8 come from PlayerGameLog.scenario,
    defaulting to league averages when scenario is unpopulated.
    """
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    stat_col = STAT_COLS[stat]
    sql = text(_SQL_TEMPLATE.format(stat_col=stat_col))

    with engine.connect() as conn:
        rows = conn.execute(sql, {"cutoff": cutoff}).fetchall()

    logger.info(f"Fetched {len(rows)} player-game rows for stat={stat}")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=_RESULT_COLUMNS)
    return df


def estimate_prop_lines(df: pd.DataFrame) -> pd.Series:
    """
    When no historical prop lines are stored, use each player's rolling
    season mean as a synthetic line (tests model's ability to predict
    above/below expectation).
    """
    return df["actual_value"].expanding().mean().shift(1).fillna(df["actual_value"].mean())


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


def evaluate(model, X: pd.DataFrame, y: np.ndarray, stat: str) -> None:
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

    # Warn if scenario-dependent features are suspiciously flat (all defaults)
    scenario_feats = ["opp_pace", "opp_def_rtg", "def_vs_position", "implied_team_total", "spread"]
    for feat in scenario_feats:
        col_std = X[feat].std()
        if col_std < 0.01:
            print(
                f"\n  WARNING: {feat} has near-zero variance (std={col_std:.4f})."
                " Run backfill_scenario.py to populate real matchup context."
            )


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
    df = fetch_prop_logs(engine, stat, days)

    if df.empty:
        print(f"\nNo player game logs found for stat={stat} in last {days} days.")
        print("Populate player data first (nba_backfill.py), then run backfill_scenario.py.")
        return

    # Use rolling season mean as synthetic prop line
    prop_lines = estimate_prop_lines(df)
    y = (df["actual_value"] > prop_lines).astype(int).values

    X = df[FEATURE_NAMES].astype(float).fillna(0.0)

    print(f"\n  Training samples : {len(X)}")
    print(f"  Over rate        : {y.mean():.1%}")
    print(f"  Mean actual {stat:4s} : {df['actual_value'].mean():.1f}")
    print(f"  Mean prop line   : {prop_lines.mean():.1f}")

    # Show feature variance so you can see which features have real signal
    print("\n  Feature std devs (0 = all defaults, no real signal):")
    for feat in FEATURE_NAMES:
        print(f"    {feat:<25} {X[feat].std():.3f}")

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
    evaluate(model, X_scaled, y, stat)

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
