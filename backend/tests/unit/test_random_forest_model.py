"""
Unit tests for Random Forest model implementation.
"""
import numpy as np
import pandas as pd
from app.services.random_forest_model import RandomForestModel

def test_train_and_predict():
    # Setup: Create dummy training data
    X_train = pd.DataFrame({
        "implied_prob": [0.6, 0.4, 0.7, 0.3, 0.55],
        "is_home": [1, 0, 1, 0, 1],
        "edge": [0.05, -0.02, 0.08, -0.05, 0.03]
    })
    y_train = np.array([1, 0, 1, 0, 1])
    
    model = RandomForestModel()
    
    # Execute
    model.train(X_train, y_train)
    
    # Test prediction
    X_test = pd.DataFrame({
        "implied_prob": [0.65, 0.35],
        "is_home": [1, 0],
        "edge": [0.06, -0.03]
    })
    
    probs = model.predict_proba(X_test)
    
    # Verify
    assert len(probs) == 2
    assert 0 <= probs[0] <= 1
    assert 0 <= probs[1] <= 1
    # Higher implied_prob should generally lead to higher predicted prob
    assert probs[0] > probs[1]
