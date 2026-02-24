# Prediction Models Research

## Integrated Models

### 1. NBA XGBoost Predictor
Based on research from [kyleskom/NBA-Machine-Learning-Sports-Betting](https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting).

#### Moneyline Model
- **Algorithm**: XGBoost (Gradient Boosted Trees)
- **Primary Features**: 
  - Team Offensive Rating (ORTG)
  - Team Defensive Rating (DRTG)
  - Win Percentage (W_PCT)
  - Recent Form (Last 5/10 games)
- **Historical Accuracy**: ~69%
- **Edge Identification**: Comparing model-derived probability against market-implied probability (devigged).

#### Over/Under Model
- **Algorithm**: XGBoost
- **Primary Features**: 
  - Team Pace (possessions per 48 min)
  - Blended Offensive/Defensive efficiency
  - Historical O/U performance
- **Historical Accuracy**: ~55%

### 2. Bayesian Posterior Model
Located in `backend/app/services/bayesian.py`.

#### Methodology
- **Prior**: Market-implied probability from sharp books (Pinnacle/Circa).
- **Likelihood**: Model-derived projections (ML or DvP).
- **Update**: Beta distribution update using pseudo-observations.
- **Monte Carlo**: 20,000 iterations to determine 95% confidence intervals.

---

## Future Model Research

### 1. Player Prop Hit-Rate Models
- Using Normal CDF distributions based on player season mean and standard deviation.
- Adjusting for opponent defensive rank vs. specific position (DvP).

### 2. Correlation Models for Parlays
- Analyzing how specific player performances correlate within a game (e.g., QB yards and WR yards).
- Implementation using multivariate distributions for correlated risk assessment.

### 3. Market Sentiment Models
- Integrating Twitter/X sentiment analysis as a feature for potential line movement (Steam detection).
- Using Roberta-base-sentiment for real-time social signal processing.
