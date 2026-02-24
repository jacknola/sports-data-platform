# EV Calculation & Kelly Sizing Reference

## Devigging Market Maker Odds
Derive true probability by removing vig from Pinnacle/sharp book odds.

```python
def devig(odds_a: int, odds_b: int) -> tuple[float, float]:
    """Devig American odds pair. Returns (true_prob_a, true_prob_b)."""
    def implied(odds):
        return abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)
    imp_a, imp_b = implied(odds_a), implied(odds_b)
    total = imp_a + imp_b  # total > 1.0 = vig
    return imp_a / total, imp_b / total
```

Example: Pinnacle -110/-110 → implied 52.38% each → total 104.76% → devigged 50.00% each.

## Model Blend
When KenPom/model probability is available:
```
blended_prob = 0.60 * devigged_prob + 0.40 * model_prob
```

## Expected Value
```
EV = (true_prob × decimal_odds) - 1
```
Example: 50% true prob, retail +105 (decimal 2.05) → EV = (0.50 × 2.05) - 1 = +2.5%

Trigger bets on EV percentage, not just implied probability difference.

## Kelly Criterion

### Single Bet
```
f* = (p × b - q) / b
```
where p = prob winning, q = prob losing, b = decimal odds - 1

**Always use fractional Kelly:**

### Minimum Edge Thresholds
- Low confidence (model only): ≥3% edge → Quarter-Kelly (12.5% max)
- Medium (+RLM confirmation): ≥5% edge → Half-Kelly (25% max)
- High (+steam/RLM + model): ≥7% edge → Half-Kelly boosted (37.5% max)
- Maximum conviction: ≥10% edge → Half-Kelly max (50% max)

### Verdicts
- **PASS**: edge < 2.5%
- **PLAY**: edge 2.5%–5.0%
- **STRONG PLAY**: edge > 5.0% + sharp signal confirmed

### Multivariate Portfolio Kelly
For correlated simultaneous bets, use `backend/app/services/multivariate_kelly.py`:
```python
from scipy.optimize import minimize
# Solve constrained convex optimization of log-growth function
# max_single default = 5% of bankroll per bet
```

## Bankroll Management
- If Expected Maximum Drawdown (EMDD) > 30%, reduce Kelly fractions until EMDD < 20%
- Round stakes to human-like amounts: $412.37 → $400 or $425

## Performance Benchmarks
- Model calibration (Brier): < 0.25 min, < 0.22 target
- CLV weekly avg: > 0 min, > +1.5% target
- Win rate at -110: > 52.4% min, > 55% target
- Monthly ROI: > 3% min, > 8% target
- Max drawdown: < 30% min, < 20% target
