"""
Feature engineering utility for betting models.
"""
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from loguru import logger

class FeatureEngineer:
    """
    Service for transforming raw betting data into model features.
    """
    
    def prepare_features(self, data: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, np.ndarray]:
        """
        Transform historical game and bet data into features and labels.
        
        Args:
            data: List of game dictionaries with nested bet data.
            
        Returns:
            A tuple of (features DataFrame, labels array).
        """
        rows = []
        labels = []
        
        for game in data:
            home_score = game.get("home_score")
            away_score = game.get("away_score")
            
            if home_score is None or away_score is None:
                continue
                
            for bet in game.get("bets", []):
                # Basic features
                row = {
                    "game_id": game.get("id"),
                    "implied_prob": bet.get("implied_prob"),
                    "devig_prob": bet.get("devig_prob"),
                    "posterior_prob": bet.get("posterior_prob"),
                    "edge": bet.get("edge"),
                    "is_home": 1 if bet.get("team") == game.get("home_team") else 0,
                }
                
                # Add optional features from metadata
                features_meta = bet.get("features", {})
                if isinstance(features_meta, dict):
                    row.update(features_meta)
                
                rows.append(row)
                
                # Label: 1 if the bet's team won, 0 otherwise
                is_win = 0
                if bet.get("team") == game.get("home_team"):
                    is_win = 1 if home_score > away_score else 0
                elif bet.get("team") == game.get("away_team"):
                    is_win = 1 if away_score > home_score else 0
                
                labels.append(is_win)
                
        df = pd.DataFrame(rows)
        # Drop non-feature columns
        X = df.drop(columns=["game_id"]) if "game_id" in df.columns else df
        
        # Fill missing values
        X = X.fillna(0)
        
        logger.info(f"Prepared features for {len(X)} bets")
        return X, np.array(labels)
