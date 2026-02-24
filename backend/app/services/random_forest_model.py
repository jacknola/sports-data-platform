"""
Random Forest model implementation for sports betting.
"""
from typing import Optional
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from loguru import logger

class RandomForestModel:
    """
    Random Forest model for predicting game outcomes.
    """
    
    def __init__(self, n_estimators: int = 100, max_depth: Optional[int] = None):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42
        )
        self.is_trained = False
        self.feature_names = []

    def train(self, X: pd.DataFrame, y: np.ndarray):
        """
        Train the Random Forest model.
        
        Args:
            X: Features DataFrame.
            y: Labels array.
        """
        logger.info(f"Training Random Forest model with {len(X)} samples")
        self.feature_names = X.columns.tolist()
        self.model.fit(X, y)
        self.is_trained = True
        logger.info("Model training complete")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict win probabilities.
        
        Args:
            X: Features DataFrame.
            
        Returns:
            Probability of class 1 (win).
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
            
        # Ensure feature alignment
        X = X[self.feature_names]
        
        # Get probability for class 1
        probs = self.model.predict_proba(X)[:, 1]
        return probs

    def get_feature_importance(self) -> pd.Series:
        """
        Get feature importance.
        """
        if not self.is_trained:
            raise ValueError("Model must be trained")
            
        return pd.Series(
            self.model.feature_importances_,
            index=self.feature_names
        ).sort_values(ascending=False)
