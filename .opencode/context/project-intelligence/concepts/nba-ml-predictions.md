<!-- Context: project-intelligence/concepts/nba-ml-predictions | Priority: high | Version: 1.0 | Updated: 2026-02-27 -->

# NBA ML Predictions — XGBoost Pipeline

**Purpose**: XGBoost-based NBA game outcome predictions integrated into the betting pipeline.
**Last Updated**: 2026-02-27

## Core Concept

Two XGBoost models predict NBA outcomes: Moneyline (~69% accuracy) and Over/Under (~55%). Training data spans 2007-08 to present. Predictions feed into the EV calculation and Kelly sizing pipeline via the AnalysisAgent.

## Features

| Feature | Description |
|---------|-------------|
| ORTG / DRTG | Offensive/Defensive rating |
| Recent form | Last 10 game performance |
| Win % | Season win percentage |
| Pace | Possessions per game |
| Efficiency | Net rating differential |

## EV & Kelly Formulas

```python
# Expected Value
EV = (win_prob * payout) - (loss_prob * stake)

# Kelly Criterion
kelly_fraction = edge / (1 - win_prob)
# Cap: 25% of bankroll max
# Conservative: 50% of Kelly (Half Kelly)
# Min edge: 5% to place bet
```

## Pipeline Integration

```
OddsAgent → ML Predictor → AnalysisAgent → ExpertAgent
              ↓
         XGBoost Models
         (moneyline + O/U)
```

## Training

```bash
python3 backend/app/services/ml/get_nba_data.py
python3 backend/app/services/ml/train_moneyline_model.py
python3 backend/app/services/ml/train_overunder_model.py
# Models saved to ./models/nba_ml/
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /predictions/nba/today` | Today's predictions |
| `GET /bets?sport=nba&min_edge=0.05` | Filtered +EV bets |

## 📂 Codebase References

- **Predictor**: `backend/app/services/nba_ml_predictor.py`
- **Training**: `backend/app/services/ml/`
- **Models**: `./models/nba_ml/`
- **Full docs**: `NBA_ML_INTEGRATION.md` (root)
