# NBA Machine Learning Integration

## Overview

Integrated NBA betting predictions using machine learning based on [kyleskom/NBA-Machine-Learning-Sports-Betting](https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting).

The system uses **XGBoost** models to predict NBA game outcomes with:
- **~69% accuracy** on moneyline predictions
- **~55% accuracy** on over/under predictions
- Expected value calculations
- Kelly Criterion for bet sizing

## Features

### 1. ML-Based Predictions
- XGBoost models for moneyline and over/under
- Training on data from 2007-08 season to present
- Real-time predictions for today's games

### 2. Expected Value Calculation
- Calculates EV for each side
- Identifies best bet automatically
- Considers current odds

### 3. Kelly Criterion
- Recommended bet size based on edge
- Caps at 25% of bankroll for safety
- Conservative: bet 50% of Kelly

## Usage

### API Endpoints

#### Get Today's NBA Predictions
```bash
GET /api/v1/predictions/nba/today
```

Returns:
```json
{
  "date": "2024-01-15",
  "sport": "NBA",
  "total_games": 3,
  "predictions": [
    {
      "home_team": "Lakers",
      "away_team": "Warriors",
      "moneyline_prediction": {
        "winner": "home",
        "home_win_prob": 0.58,
        "away_win_prob": 0.42,
        "confidence": 0.62
      },
      "underover_prediction": {
        "total_points": 220,
        "over_prob": 0.55,
        "under_prob": 0.45,
        "recommendation": "over"
      },
      "expected_value": {
        "home_ev": 0.08,
        "away_ev": -0.05,
        "best_bet": "home",
        "home_odds": -110,
        "away_odds": 110
      },
      "kelly_criterion": 0.12,
      "confidence": 0.62,
      "method": "ml_xgboost"
    }
  ],
  "method": "xgboost"
}
```

#### Get Best Bets with ML
```bash
GET /api/v1/bets?sport=nba&min_edge=0.05&limit=10
```

## Training Models

To train your own models:

```bash
# Get latest NBA data
cd backend/app/services/nba_data
python get_nba_data.py

# Train moneyline model
python train_moneyline_model.py

# Train over/under model
python train_overunder_model.py
```

Models will be saved to `./models/nba_ml/`

## Integration with Agent System

The NBA ML predictor integrates with our multi-agent system:

1. **OddsAgent** - Fetches current odds
2. **NBA ML Predictor** - Makes ML predictions
3. **AnalysisAgent** - Runs Bayesian analysis on predictions
4. **ExpertAgent** - Uses sequential thinking for final recommendation

## Prediction Model Details

### Moneyline Model
- **Input Features**: Offensive rating, defensive rating, recent form, win percentages
- **Output**: Win probability for each team
- **Accuracy**: ~69%
- **Training Data**: 2007-08 to present season

### Over/Under Model
- **Input Features**: Team pace, offensive/defensive efficiency, recent totals
- **Output**: Total points prediction and over/under recommendation
- **Accuracy**: ~55%
- **Training Data**: Historical game totals

## Expected Value Calculation

For each game, the system calculates:
```
EV = (Win Probability × Payout) - (Loss Probability × Stake)
```

Positive EV means profitable bet.

## Kelly Criterion

Calculates optimal bet size:
```
Kelly = Edge / (1 - Win Probability)
```

The system:
- Caps at 25% of bankroll
- Conservative users should bet 50% of Kelly
- Only bets when edge > 5%

## Data Sources

The original repo uses:
- NBA statistics from Basketball-Reference
- Odds data from sbrodds API
- Team ratings (ORTG, DRTG)
- Recent form and performance metrics

## Performance

Based on original repo performance:
- **Moneyline**: 69% accuracy
- **Over/Under**: 55% accuracy
- **Bankroll Growth**: Positive long-term with proper bankroll management
- **Best Edge**: 5-15% typically

## Usage in Frontend

The React frontend automatically displays:
- ML predictions for today's games
- Expected value for each bet
- Kelly Criterion recommendations
- Confidence scores

## Next Steps

1. Train models with latest data
2. Integrate with live odds feeds
3. Add NFL/MLB prediction models
4. Implement bankroll tracking
5. Add historical performance metrics

## References

- [NBA-Machine-Learning-Sports-Betting](https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting)
- XGBoost Documentation
- Kelly Criterion Paper

