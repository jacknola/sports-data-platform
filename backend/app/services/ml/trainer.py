"""
Model Trainer for XGBoost and Random Forest models.

Provides training, calibration, and evaluation for sports betting models.
Supports walk-forward validation and model persistence.
"""

import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not installed")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.isotonic import IsotonicRegression
    from sklearn.metrics import (
        accuracy_score,
        brier_score_loss,
        log_loss,
        roc_auc_score,
    )

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not installed")


# Default model paths
DEFAULT_MODEL_DIR = Path("./models")
NBA_ML_DIR = DEFAULT_MODEL_DIR / "nba_ml"
RF_DIR = DEFAULT_MODEL_DIR / "rf"


class _CalibratedModel:
    """
    Lightweight wrapper that applies Platt or isotonic calibration on top of
    a pre-fitted base classifier.

    Designed to work across all sklearn versions as a version-agnostic
    replacement for ``CalibratedClassifierCV(cv="prefit")``, which was
    removed in sklearn 1.2+.
    """

    def __init__(self, base_model, calibrator, method: str = "sigmoid"):
        self._base_model = base_model
        self._calibrator = calibrator
        self._method = method

    def predict_proba(self, X) -> np.ndarray:
        """Return calibrated probabilities for both classes."""
        raw_probs = self._base_model.predict_proba(X)[:, 1]
        if self._method == "sigmoid":
            cal_probs = self._calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]
        else:  # isotonic
            cal_probs = np.clip(self._calibrator.predict(raw_probs), 0.0, 1.0)
        return np.column_stack([1.0 - cal_probs, cal_probs])

    def predict(self, X) -> np.ndarray:
        """Return class predictions using a 0.5 probability threshold."""
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)



class ModelTrainer:
    """
    Trainer for XGBoost and Random Forest models.

    Supports:
    - XGBoost with configurable hyperparameters
    - Random Forest with calibration
    - Walk-forward validation
    - Model persistence
    """

    def __init__(self, model_dir: str = "./models"):
        """
        Initialize trainer.

        Args:
            model_dir: Base directory for model storage.
        """
        self.model_dir = Path(model_dir)
        self.nba_ml_dir = self.model_dir / "nba_ml"
        self.rf_dir = self.model_dir / "rf"

        # Create directories
        self.nba_ml_dir.mkdir(parents=True, exist_ok=True)
        self.rf_dir.mkdir(parents=True, exist_ok=True)

    def train_xgboost(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        model_type: str = "moneyline",
        n_estimators: int = 500,
        learning_rate: float = 0.05,
        max_depth: int = 6,
        eval_metric: str = "logloss",
        **kwargs,
    ):
        """
        Train an XGBoost classifier.

        Args:
            X: Feature DataFrame.
            y: Labels (1 = home win).
            model_type: Type of model ('moneyline' or 'overunder').
            n_estimators: Number of boosting rounds.
            learning_rate: Learning rate.
            max_depth: Maximum tree depth.
            eval_metric: Evaluation metric.
            **kwargs: Additional XGBoost parameters.

        Returns:
            Trained XGBoost model.
        """
        if not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost not available")

        logger.info(
            f"Training XGBoost {model_type} model: "
            f"{len(X)} samples, {X.shape[1]} features"
        )

        model = xgb.XGBClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            eval_metric=eval_metric,
            random_state=42,
            use_label_encoder=False,
            **kwargs,
        )

        model.fit(X, y)

        logger.info("XGBoost training complete")

        # Save model
        model_path = self.nba_ml_dir / f"{model_type}_model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        logger.info(f"Model saved to {model_path}")

        return model

    def train_random_forest(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        sport: str = "nba",
        n_estimators: int = 200,
        max_depth: Optional[int] = 12,
        **kwargs,
    ):
        """
        Train a Random Forest classifier.

        Args:
            X: Feature DataFrame.
            y: Labels.
            sport: Sport type ('nba' or 'ncaab').
            n_estimators: Number of trees.
            max_depth: Maximum tree depth.
            **kwargs: Additional sklearn parameters.

        Returns:
            Trained Random Forest model.
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("sklearn not available")

        logger.info(
            f"Training Random Forest for {sport}: "
            f"{len(X)} samples, {X.shape[1]} features"
        )

        model = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth, random_state=42, **kwargs
        )

        model.fit(X, y)

        logger.info("Random Forest training complete")

        # Save model
        model_path = self.rf_dir / f"{sport}_model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        logger.info(f"Model saved to {model_path}")

        return model

    def calibrate_model(
        self, model, X: pd.DataFrame, y: np.ndarray, method: str = "sigmoid"
    ):
        """
        Calibrate model probabilities using Platt scaling or isotonic regression.

        Implements calibration by fitting a post-hoc calibrator on top of a
        pre-fitted model's predicted probabilities on the validation set. This
        approach works correctly across all sklearn versions and is more
        transparent than CalibratedClassifierCV with cv="prefit" (which was
        removed in sklearn 1.2+).

        Handles the edge case where all validation outcomes are the same class
        (e.g. all OVER or all UNDER), which would cause the calibrator to fail
        because it cannot distinguish two classes. In that case the original
        uncalibrated model is returned and a warning is logged.

        Args:
            model: Trained classifier with a predict_proba method.
            X: Validation features.
            y: Validation labels (0 or 1).
            method: 'sigmoid' (Platt scaling via logistic regression) or
                    'isotonic' (isotonic regression).

        Returns:
            _CalibratedModel wrapping the original classifier with the fitted
            calibrator, or the original model when calibration cannot be
            performed due to single-class validation data.
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("sklearn not available")

        # Guard: both calibrators require at least two distinct classes in the
        # validation set. When all samples belong to one class — which happens
        # in small player-specific windows where every game went OVER or every
        # game went UNDER — fitting fails with a ValueError.
        unique_classes = np.unique(y)
        if len(unique_classes) < 2:
            logger.warning(
                f"Calibration skipped: validation set contains only class "
                f"{unique_classes.tolist()} ({len(y)} samples). "
                f"Returning uncalibrated model."
            )
            return model

        logger.info(f"Calibrating model using {method}...")

        # Obtain raw probabilities from the pre-fitted model.
        raw_probs = model.predict_proba(X)[:, 1]

        if method == "sigmoid":
            # Platt scaling: fit a logistic regression on the raw probabilities.
            calibrator = LogisticRegression(C=1.0, solver="lbfgs")
            calibrator.fit(raw_probs.reshape(-1, 1), y)
        elif method == "isotonic":
            calibrator = IsotonicRegression(out_of_bounds="clip")
            calibrator.fit(raw_probs, y)
        else:
            raise ValueError(f"Unknown calibration method: {method!r}. Use 'sigmoid' or 'isotonic'.")

        calibrated = _CalibratedModel(base_model=model, calibrator=calibrator, method=method)

        # Save calibrated model
        model_name = getattr(model, "__class__.__name__", "model")
        calib_path = self.nba_ml_dir / f"{model_name.lower()}_calibrated.pkl"

        with open(calib_path, "wb") as f:
            pickle.dump(calibrated, f)

        logger.info(f"Calibrated model saved to {calib_path}")

        return calibrated

    def evaluate(
        self, model, X: pd.DataFrame, y: np.ndarray, model_name: str = "model"
    ) -> Dict[str, float]:
        """
        Evaluate model performance.

        Args:
            model: Trained model.
            X: Test features.
            y: Test labels.
            model_name: Name for logging.

        Returns:
            Dict of evaluation metrics.
        """
        logger.info(f"Evaluating {model_name}...")

        # Predictions
        y_pred = model.predict(X)
        y_pred_proba = model.predict_proba(X)[:, 1]

        # Metrics
        accuracy = accuracy_score(y, y_pred)
        brier = brier_score_loss(y, y_pred_proba)

        # Log loss and AUC (handle edge cases)
        try:
            ll = log_loss(y, y_pred_proba)
        except Exception:
            ll = float("inf")

        try:
            auc = roc_auc_score(y, y_pred_proba)
        except Exception:
            auc = 0.5

        metrics = {
            "accuracy": accuracy,
            "brier_score": brier,
            "log_loss": ll,
            "auc": auc,
            "n_samples": len(y),
            "n_positive": int(y.sum()),
            "positive_rate": float(y.mean()),
        }

        logger.info(
            f"{model_name} metrics: "
            f"Accuracy={accuracy:.3f}, "
            f"Brier={brier:.3f}, "
            f"AUC={auc:.3f}"
        )

        return metrics

    def walk_forward_validation(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        train_seasons: List[str],
        test_season: str,
        model_type: str = "xgboost",
        **train_kwargs,
    ) -> Dict[str, float]:
        """
        Perform walk-forward validation (train on N-1 seasons, test on N).

        Args:
            X: Features with 'season' column.
            y: Labels.
            train_seasons: Seasons to train on.
            test_season: Season to test on.
            model_type: 'xgboost' or 'random_forest'.
            **train_kwargs: Training parameters.

        Returns:
            Evaluation metrics on test season.
        """
        # Split by season
        train_mask = X["season"].isin(train_seasons)
        test_mask = X["season"] == test_season

        X_train = X[train_mask].drop(columns=["season"])
        y_train = y[train_mask]
        X_test = X[test_mask].drop(columns=["season"])
        y_test = y[test_mask]

        if len(X_train) == 0 or len(X_test) == 0:
            logger.warning("Insufficient data for walk-forward validation")
            return {}

        logger.info(f"Walk-forward: train on {train_seasons}, test on {test_season}")

        # Train
        if model_type == "xgboost":
            model = self.train_xgboost(X_train, y_train, **train_kwargs)
        else:
            model = self.train_random_forest(X_train, y_train, **train_kwargs)

        # Evaluate
        metrics = self.evaluate(model, X_test, y_test, f"{model_type}_{test_season}")

        return metrics

    def load_model(self, path: str):
        """
        Load a model from disk.

        Args:
            path: Path to model file.

        Returns:
            Loaded model.
        """
        with open(path, "rb") as f:
            model = pickle.load(f)

        logger.info(f"Loaded model from {path}")

        return model

    def load_xgboost(self, model_type: str = "moneyline"):
        """
        Load an XGBoost model.

        Args:
            model_type: Type of model.

        Returns:
            Loaded model or None.
        """
        model_path = self.nba_ml_dir / f"{model_type}_model.pkl"

        if not model_path.exists():
            logger.warning(f"Model not found: {model_path}")
            return None

        return self.load_model(str(model_path))

    def load_random_forest(self, sport: str = "nba"):
        """
        Load a Random Forest model.

        Args:
            sport: Sport type.

        Returns:
            Loaded model or None.
        """
        model_path = self.rf_dir / f"{sport}_model.pkl"

        if not model_path.exists():
            logger.warning(f"Model not found: {model_path}")
            return None

        return self.load_model(str(model_path))


def train_nba_models(
    X: pd.DataFrame, y: np.ndarray, model_dir: str = "./models"
) -> Dict[str, object]:
    """
    Train all NBA models (XGBoost + RF).

    Args:
        X: Features DataFrame.
        y: Labels.
        model_dir: Model directory.

    Returns:
        Dict of trained models.
    """
    trainer = ModelTrainer(model_dir)

    models = {}

    # Train XGBoost moneyline
    models["xgb_moneyline"] = trainer.train_xgboost(X, y, model_type="moneyline")

    # Train Random Forest
    models["rf"] = trainer.train_random_forest(X, y, sport="nba")

    return models
