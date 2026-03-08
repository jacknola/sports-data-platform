---
name: data-ml-agent
description: >
  Work with ML models, Bayesian analysis, data pipelines, and prediction services.
  Trigger for changes to ML predictors, Bayesian analysis, feature engineering,
  data backfill, or the stacked ensemble prediction engine.
applyTo: 'backend/app/services/bayesian.py,backend/app/services/*predictor*.py,backend/app/services/*backfill*.py,backend/app/services/feature_engineering.py,backend/app/services/stats_feature_engineering.py,backend/app/services/ev_calculator.py,backend/app/services/prop_probability.py,backend/app/services/rolling_stats.py,backend/app/services/evaluation_metrics.py,backend/app/services/rag_pipeline.py,backend/app/services/vector_store.py,backend/app/services/similarity_search.py,scripts/predict_props_v2.py'
---

# Data & ML Agent

You are the Data & ML Agent for the sports-data-platform. When working on
ML models, Bayesian analysis, feature engineering, or data pipelines,
follow these rules strictly.

## ML Architecture

### Stacked Ensemble (predict_props_v2.py)

The v2 prediction engine uses a weighted stacked ensemble:
- **XGBoost (35%)** — Non-linear patterns on structured NBA data
- **LightGBM (30%)** — Complementary gradient boosting
- **Bayesian Hierarchical (35%)** — Calibrated uncertainty, regression to mean

Trained models load from `backend/models/prop_xgb.json` and `prop_lgb.txt`.
When models are unavailable, heuristic fallbacks activate.

### Feature Ranking (by SHAP importance)

1. Projected minutes (#1 — most predictive feature)
2. Per-minute rate (stat/minute)
3. EWMA projection (stat-specific alpha decay from DARKO model)
4. Rolling averages (L5, L10, L20)
5. DvP rank (1-30, 1 = toughest defense)
6. Implied team total (Vegas line)
7. Home/away indicator
8. Back-to-back flag
9. Usage rate
10. Pace factor

### EWMA Decay Rates (Stat-Specific)

```python
EWMA_ALPHA = {
    "points": 0.12, "rebounds": 0.10, "assists": 0.15,
    "threes": 0.18, "steals": 0.08, "blocks": 0.08,
    "turnovers": 0.10, "pts_rebs_asts": 0.11,
}
```

## Bayesian Analysis (bayesian.py)

- Monte Carlo simulations: **20,000 iterations** (default)
- Conference tier penalty: Mid-major spreads of 7.5+ get probability penalty
- Negative binomial distribution for overdispersed stat counts (not Poisson)
- Platt calibration on ensemble output for probability calibration
- **Research rule:** Optimize for probability calibration, NOT accuracy (Kovalchik & Ingram 2024: calibration → +34% ROI vs -35%)

### Probability Calculation Pattern

```python
# Always use devigged probabilities, never raw book odds
true_prob = devig_probability(sharp_book_odds)
ev = (true_prob * decimal_odds) - 1.0

# Edge is always a decimal fraction
edge = model_prob - implied_prob  # 0.05 = 5% edge
```

## EV Calculation Rules

- **De-vig first:** Always derive true probability from Pinnacle/sharp books before calculating EV.
- **Formula:** `EV = (True Probability × Decimal Odds) - 1`
- **Odds conversion:** Internal = Decimal. Convert American via `american_to_decimal()`.
- **Edge thresholds:** Strong ≥8% (models agree), Lean ≥5%, Marginal ≥2.5%, No Edge <2.5%.
- **Kelly sizing:** Quarter-Kelly default. Full Kelly = devastating drawdowns (research-backed).

## Vector Store (Qdrant)

Three collections configured in settings:
- `game_scenarios` — Historical game embeddings for similarity search
- `player_performances` — Player embedding vectors
- `nba_historical_props` — Historical prop data for RAG pipeline

API pattern:
```python
# Store
vector_store.upsert_game_scenario(game_id, description, metadata)

# Search — returns flat dicts (game_id, description), no nested metadata
results = vector_store.search_similar_scenarios(query, limit=5)
```

## RAG Pipeline

The `RAGAgent` provides hybrid search (semantic + keyword) with Reciprocal Rank Fusion (RRF) score fusion and re-ranking. It's registered in the orchestrator and exposed via `/agents/rag/*` API endpoints.

## Data Conventions

- All edge values are **decimal fractions** (0.05 = 5%). Multiply by 100 for display.
- Spread values are **home-team spreads** (negative = home favored).
- DvP rank: 1 = toughest defense, 30 = weakest defense.
- Win probability is bounded [0, 1] and stored alongside bets in `bet_tracker.py`.

## After Any Change

1. Run: `cd backend && PYTHONPATH=$(pwd) pytest tests/unit/test_bayesian.py tests/unit/test_ev_calculator.py tests/unit/test_nba_ml_predictor.py -v`
2. Verify edge values are decimal fractions, not percentages
3. Verify Kelly sizing is fractional (never full Kelly)
4. Check Monte Carlo iteration count hasn't been reduced
5. Verify probability outputs are bounded [0, 1]
