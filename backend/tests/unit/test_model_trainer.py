"""
Unit tests for ModelTrainer — specifically the Platt scaling / calibration
edge case where all validation labels are the same class.
"""

import numpy as np
import pandas as pd
import pytest

try:
    from sklearn.ensemble import RandomForestClassifier
    from app.services.ml.trainer import ModelTrainer, _CalibratedModel
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="sklearn not installed")
class TestCalibrateModelSingleClass:
    """Tests for ModelTrainer.calibrate_model with degenerate validation sets."""

    def _make_trainer(self, tmp_path) -> "ModelTrainer":
        trainer = ModelTrainer(model_dir=str(tmp_path))
        return trainer

    def _fitted_rf(self, X: pd.DataFrame, y: np.ndarray) -> "RandomForestClassifier":
        """Return a minimal RandomForest already fitted on two-class data.

        Uses n_estimators=5 to keep tests fast; production models use 200+.
        """
        clf = RandomForestClassifier(n_estimators=5, random_state=42)
        clf.fit(X, y)
        return clf

    def test_calibrate_normal_case(self, tmp_path):
        """Calibration succeeds when validation set has both classes."""
        trainer = self._make_trainer(tmp_path)
        X = pd.DataFrame({"a": [0.1, 0.9, 0.2, 0.8, 0.3, 0.7]})
        y_train = np.array([0, 1, 0, 1, 0, 1])
        y_val = np.array([0, 1, 0, 1, 0, 1])

        clf = self._fitted_rf(X, y_train)
        calibrated = trainer.calibrate_model(clf, X, y_val, method="sigmoid")

        # Should be a _CalibratedModel wrapper, not the raw RF
        assert isinstance(calibrated, _CalibratedModel)
        # predict_proba must return valid probabilities for both classes
        proba = calibrated.predict_proba(X)
        assert proba.shape == (len(X), 2)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)

    def test_calibrate_all_over_returns_original_model(self, tmp_path):
        """
        Edge case: when all validation labels are 1 (all OVER), Platt scaling
        cannot fit a sigmoid with only one class. The trainer must gracefully
        return the uncalibrated model instead of raising ValueError.
        """
        trainer = self._make_trainer(tmp_path)
        X_train = pd.DataFrame({"a": [0.1, 0.9, 0.2, 0.8]})
        y_train = np.array([0, 1, 0, 1])
        X_val = pd.DataFrame({"a": [0.6, 0.7, 0.8]})
        y_val_all_over = np.array([1, 1, 1])  # all OVER — single class

        clf = self._fitted_rf(X_train, y_train)
        result = trainer.calibrate_model(clf, X_val, y_val_all_over, method="sigmoid")

        # Must not raise; must return the original model unchanged
        assert result is clf

    def test_calibrate_all_under_returns_original_model(self, tmp_path):
        """
        Edge case: when all validation labels are 0 (all UNDER), the same
        guard should kick in and return the uncalibrated model.
        """
        trainer = self._make_trainer(tmp_path)
        X_train = pd.DataFrame({"a": [0.1, 0.9, 0.2, 0.8]})
        y_train = np.array([0, 1, 0, 1])
        X_val = pd.DataFrame({"a": [0.1, 0.2, 0.3]})
        y_val_all_under = np.array([0, 0, 0])  # all UNDER — single class

        clf = self._fitted_rf(X_train, y_train)
        result = trainer.calibrate_model(clf, X_val, y_val_all_under, method="sigmoid")

        assert result is clf

    def test_calibrate_single_sample_returns_original_model(self, tmp_path):
        """
        Edge case: only one validation sample (trivially single-class).
        """
        trainer = self._make_trainer(tmp_path)
        X_train = pd.DataFrame({"a": [0.1, 0.9, 0.2, 0.8]})
        y_train = np.array([0, 1, 0, 1])
        X_val = pd.DataFrame({"a": [0.5]})
        y_val_single = np.array([1])

        clf = self._fitted_rf(X_train, y_train)
        result = trainer.calibrate_model(clf, X_val, y_val_single)

        assert result is clf

    def test_calibrate_isotonic_single_class_returns_original_model(self, tmp_path):
        """
        The same guard applies to isotonic regression (not only Platt/sigmoid).
        """
        trainer = self._make_trainer(tmp_path)
        X_train = pd.DataFrame({"a": [0.1, 0.9, 0.2, 0.8]})
        y_train = np.array([0, 1, 0, 1])
        X_val = pd.DataFrame({"a": [0.6, 0.7]})
        y_val = np.array([1, 1])

        clf = self._fitted_rf(X_train, y_train)
        result = trainer.calibrate_model(clf, X_val, y_val, method="isotonic")

        assert result is clf
