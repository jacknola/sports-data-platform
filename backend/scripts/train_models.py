#!/usr/bin/env python3
"""ML Model Training Script.

Trains XGBoost and Random Forest models on NBA/NCAAB game data.
Uses caching to speed up repeated runs.
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from loguru import logger

from app.services.ml.data_fetcher import fetch_nba_games_paired
from app.services.ml.trainer import ModelTrainer
from app.services.stats_feature_engineering import StatsFeatureEngineer


def prepare_training_data(games_df: pd.DataFrame, sport: str = "nba") -> tuple:
    """Prepare features and labels for training."""
    if games_df.empty:
        logger.warning("No games data available")
        return pd.DataFrame(), pd.Series()

    engineer = StatsFeatureEngineer(sport=sport)

    try:
        records = games_df.to_dict(orient="records")
        X, y = engineer.prepare_training_features(records)
        return X, y
    except Exception as e:
        logger.error(f"Error preparing features: {e}")
        return pd.DataFrame(), pd.Series()


def train_models(sport: str, seasons: tuple, model_type: str = "all"):
    """Train ML models for the given sport and season range."""
    logger.info(
        f"Starting model training: sport={sport}, seasons={seasons}, model={model_type}"
    )

    model_dir = Path("./models")
    model_dir.mkdir(parents=True, exist_ok=True)

    # Fetch historical data
    logger.info("Fetching historical data...")

    try:
        if sport == "nba":
            games_df = fetch_nba_games_paired(
                start_year=seasons[0], end_year=seasons[1]
            )
        else:
            logger.error(f"Unsupported sport: {sport}")
            return None
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None

    if games_df.empty:
        logger.error("No data fetched")
        return None

    # Drop season column if present (string type causes training errors)
    if "season" in games_df.columns:
        games_df = games_df.drop(columns=["season"])

    logger.info(f"Loaded {len(games_df)} games")

    # Prepare features
    logger.info("Preparing training features...")
    X, y = prepare_training_data(games_df, sport)

    if X.empty:
        logger.error("No features extracted")
        return None

    logger.info(f"Prepared {len(X)} training samples")

    # Initialize trainer
    trainer = ModelTrainer(model_dir=str(model_dir))

    results = {}

    # Train XGBoost
    if model_type in ["all", "xgboost"]:
        logger.info("Training XGBoost model...")

        try:
            xgb_model = trainer.train_xgboost(
                X,
                y,
                model_type="moneyline",
                n_estimators=200,
                learning_rate=0.1,
                max_depth=5,
            )
            metrics = trainer.evaluate(xgb_model, X, y, "xgboost_moneyline")
            results["xgboost"] = {"model": xgb_model, "metrics": metrics}
            logger.info(f"XGBoost metrics: {metrics}")
        except Exception as e:
            logger.error(f"XGBoost training failed: {e}")

    # Train Random Forest
    if model_type in ["all", "rf", "random_forest"]:
        logger.info("Training Random Forest model...")

        try:
            rf_model = trainer.train_random_forest(
                X,
                y,
                sport=sport,
                n_estimators=200,
                max_depth=10,
            )
            metrics = trainer.evaluate(rf_model, X, y, "rf_moneyline")
            results["random_forest"] = {"model": rf_model, "metrics": metrics}
            logger.info(f"Random Forest metrics: {metrics}")
        except Exception as e:
            logger.error(f"Random Forest training failed: {e}")

    logger.info("=" * 50)
    logger.info("Training Complete!")
    logger.info("=" * 50)

    return results


def main():
    parser = argparse.ArgumentParser(description="Train ML models")
    parser.add_argument("--sport", type=str, default="nba", help="Sport (nba, ncaab)")
    parser.add_argument(
        "--seasons",
        type=str,
        default="2024-2025",
        help="Season range (e.g., 2024-2025)",
    )
    parser.add_argument(
        "--model", type=str, default="all", help="Model type (all, xgboost, rf)"
    )

    args = parser.parse_args()

    # Parse seasons
    try:
        start_year, end_year = map(int, args.seasons.split("-"))
    except ValueError:
        logger.error("Invalid season format. Use: YYYY-YYYY")
        sys.exit(1)

    logger.info(f"Training {args.sport} models for seasons {start_year}-{end_year}")

    results = train_models(
        sport=args.sport, seasons=(start_year, end_year), model_type=args.model
    )

    if results:
        logger.info("Models trained successfully!")
    else:
        logger.error("Training failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
