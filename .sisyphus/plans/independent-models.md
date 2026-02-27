# Independent Model Operation — Full Work Plan

**Goal**: Refactor the sports betting platform so Bayesian and XGBoost/Random Forest models produce predictions independently of odds data. Sharp money becomes an optional enhancement. Build the missing ML training pipeline from scratch.

**Scope**: Backend Python services only. No frontend changes. No infrastructure changes.

**Constraints**:
- Odds API: 20K calls/month ($30/month) — be efficient, cache aggressively
- Never Full Kelly — Quarter or Half Kelly only, 5% cap per bet, 25% total
- Loguru only (no print in services)
- All functions need type hints + docstrings
- Existing tests must continue passing (262/262)

**Dependencies**: nba_api (free, no key), scipy, scikit-learn, xgboost, pandas, numpy — all already in requirements.txt

---

## Wave 1: Foundation — Data & Feature Infrastructure (No Model Changes)

These tasks have ZERO dependencies on each other within the wave. Execute in parallel.

### Task 1.1: Create Elo Rating System

**File**: `backend/app/services/elo_service.py` (NEW)

**What**: Implement a persistent Elo rating tracker for NBA and NCAAB teams.

**Requirements**:
- `EloService` class with:
  - `__init__(self, k_factor=20, home_advantage=100, initial_rating=1500)`
  - `update(self, home_team, away_team, home_score, away_score) -> Tuple[float, float]` — returns new ratings
  - `get_rating(self, team_name) -> float`
  - `get_differential(self, home_team, away_team) -> float` — returns home_elo - away_elo
  - `predict_win_prob(self, home_team, away_team) -> float` — `1 / (1 + 10^((away_elo - home_elo - home_advantage) / 400))`
  - `save(self, path)` / `load(self, path)` — pickle persistence to `./models/elo/`
  - `backfill_season(self, games: List[Dict]) -> None` — process historical games in order
- MOV-adjusted Elo: `K * (1 + ln(1 + MOV)) * (actual - expected)` — margin of victory multiplier
- Thread-safe dict storage: `{team_name: float}`
- Persistence: save/load from `./models/elo/{sport}_elo.pkl`

**Pattern to follow**: Same structure as `random_forest_model.py` — clean class, loguru logging, type hints.

**Acceptance Criteria**:
- `elo.predict_win_prob("Lakers", "Celtics")` returns float 0-1
- Elo differential is a single feature value (great for XGBoost input)
- Can backfill from nba_api historical data
- Persists across runs

**QA**: Unit test `test_elo_service.py` — test update, predict, save/load, backfill.

---

### Task 1.2: Create Rolling Advanced Stats Calculator

**File**: `backend/app/services/rolling_stats.py` (NEW)

**What**: Compute rolling window advanced stats (Four Factors + efficiency) for teams.

**Requirements**:
- `RollingStatsCalculator` class with:
  - `compute_rolling(self, game_logs: pd.DataFrame, window=10) -> pd.DataFrame`
  - Output columns per team: `eFG_pct`, `TOV_pct`, `OREB_pct`, `FTr`, `net_rating`, `pace`, `ts_pct`
  - Both 5-game and 10-game rolling windows
  - `get_team_rolling_stats(self, team_name, window=10) -> Dict[str, float]`
- Data source: `nba_api.stats.endpoints.teamgamelog` — free, no API key
- For NCAAB: `NCAABStatsService.fetch_all_team_stats()` already provides AdjOE/AdjDE — wrap with rolling window
- Cache results in memory with TTL (reuse `TTLCache` pattern from `nba_stats_service.py`)

**Four Factors formulas**:
```python
eFG_pct = (FGM + 0.5 * FG3M) / FGA
TOV_pct = TOV / (FGA + 0.44 * FTA + TOV)
OREB_pct = OREB / (OREB + OPP_DREB)
FTr = FTA / FGA
```

**Pattern to follow**: `nba_stats_service.py` — TTLCache, async httpx, loguru.

**Acceptance Criteria**:
- Returns rolling Four Factors for any NBA team
- 5-game and 10-game windows
- Cached to avoid redundant API calls

**QA**: Unit test with mock game log data → verify rolling calculations.

---

### Task 1.3: Create Stats-Only Feature Engineering Pipeline

**File**: `backend/app/services/stats_feature_engineering.py` (NEW)

**What**: A feature engineering pipeline that produces model-ready features using ONLY stats data (no odds).

**Requirements**:
- `StatsFeatureEngineer` class with:
  - `prepare_features(self, home_team, away_team, sport="nba") -> pd.DataFrame`
  - Returns single-row DataFrame with columns:
    ```
    home_off_rating, home_def_rating, away_off_rating, away_def_rating,
    home_win_pct, away_win_pct, home_pace, away_pace,
    home_elo, away_elo, elo_differential,
    home_eFG_5g, home_TOV_5g, home_OREB_5g, home_FTr_5g,
    away_eFG_5g, away_TOV_5g, away_OREB_5g, away_FTr_5g,
    home_eFG_10g, home_TOV_10g, home_OREB_10g, home_FTr_10g,
    away_eFG_10g, away_TOV_10g, away_OREB_10g, away_FTr_10g,
    home_net_rating_5g, away_net_rating_5g,
    is_home, rest_days_home, rest_days_away, is_back_to_back_home, is_back_to_back_away
    ```
  - `prepare_training_features(self, historical_games: List[Dict]) -> Tuple[pd.DataFrame, np.ndarray]`
    - Batch mode for training — takes list of historical games with outcomes
    - Returns (X, y) ready for model.fit()
- Integrates: `EloService`, `RollingStatsCalculator`, `NBAStatsService`/`NCAABStatsService`
- Fills missing values with league averages, NOT zeros
- Logs feature completeness: "Features: 28/30 available for LAL vs BOS"

**DO NOT touch** `feature_engineering.py` (existing) — this is a NEW parallel pipeline. The old one stays for backward compat.

**Acceptance Criteria**:
- `prepare_features("Lakers", "Celtics")` returns 30-column DataFrame with zero odds data
- Training mode returns (X, y) for historical data
- Missing data filled with league averages

**QA**: Unit test with mock stats → verify all 30 features populated, no NaN.

---

### Task 1.4: Create Model Training Pipeline

**Files**:
- `backend/app/services/ml/data_fetcher.py` (NEW)
- `backend/app/services/ml/trainer.py` (NEW)
- `backend/scripts/train_models.py` (NEW entry point)

**What**: End-to-end pipeline to fetch historical data, compute features, train XGBoost + RF models, and save to disk.

**Requirements**:

**data_fetcher.py**:
- `HistoricalDataFetcher` class:
  - `fetch_nba_seasons(self, start_year=2018, end_year=2025) -> pd.DataFrame`
    - Uses `nba_api.stats.endpoints.leaguegamefinder` — free, no API key
    - Returns: game_id, date, home_team, away_team, home_score, away_score, home_win (bool)
  - `fetch_ncaab_seasons(self, ...)` — from NCAABStatsService or stored data
  - Rate limiting: 0.6s delay between nba_api calls (their rate limit)

**trainer.py**:
- `ModelTrainer` class:
  - `train_xgboost(self, X, y, model_type="moneyline") -> xgb.XGBClassifier`
    - Hyperparams: `n_estimators=500, learning_rate=0.05, max_depth=6, eval_metric="logloss"`
    - Walk-forward validation: train on seasons N-1, validate on season N
    - Save to `./models/nba_ml/{model_type}_model.pkl`
  - `train_random_forest(self, X, y) -> RandomForestClassifier`
    - `n_estimators=200, max_depth=12, random_state=42`
    - Save to `./models/rf/{sport}_model.pkl`
  - `calibrate_model(self, model, X_val, y_val) -> CalibratedClassifierCV`
    - Platt scaling via `sklearn.calibration.CalibratedClassifierCV(method='sigmoid')`
    - Save calibrated model alongside raw model
  - `evaluate(self, model, X_test, y_test) -> Dict` — accuracy, Brier score, calibration plot data

**scripts/train_models.py** (entry point):
```python
# Usage: python backend/scripts/train_models.py --sport nba --seasons 2018-2025
```
- Fetches data → computes features via StatsFeatureEngineer → trains → calibrates → saves → reports

**Directory structure created**:
```
models/
├── nba_ml/
│   ├── moneyline_model.pkl
│   ├── moneyline_calibrated.pkl
│   └── overunder_model.pkl
├── rf/
│   └── nba_model.pkl
└── elo/
    ├── nba_elo.pkl
    └── ncaab_elo.pkl
```

**Acceptance Criteria**:
- `python backend/scripts/train_models.py --sport nba` runs end-to-end
- Models saved to disk and loadable by `nba_ml_predictor.py`
- Walk-forward validation accuracy logged
- Calibrated model outputs well-calibrated probabilities

**QA**: Integration test — train on small dataset → verify model loads → predict returns probabilities.

---

## Wave 2: Model Decoupling — Predict Without Odds

Depends on: Wave 1 complete. These tasks are sequential within groups but parallel across groups.

### Task 2.1: Wire XGBoost to Stats-Only Features

**File**: `backend/app/services/nba_ml_predictor.py` (MODIFY)

**What**: Update `NBAMLPredictor` to use the new `StatsFeatureEngineer` instead of inline feature prep, and load the trained models from Wave 1.

**Changes**:
1. Import `StatsFeatureEngineer` and `EloService`
2. In `__init__`: instantiate `StatsFeatureEngineer` and `EloService` (load from disk)
3. Replace `_prepare_features()` body (lines 169-184):
   - Call `self.stats_engineer.prepare_features(home_team, away_team)`
   - Returns the 30-column DataFrame instead of 10-column
4. **Keep** existing `_predict_moneyline()` and `_predict_underover()` — they work with any DataFrame
5. **Keep** Pythagorean Expectation fallback — it's a good safety net
6. In `_load_models()`: also try loading calibrated models (`moneyline_calibrated.pkl`)
7. **Do NOT change** `_calculate_expected_value()` — that's valuation, not prediction

**Acceptance Criteria**:
- `predict_game(home, away, features)` works with ONLY stats features (no odds in features dict)
- Falls back to Pythagorean if models not on disk
- Existing callers don't break (features dict can still contain odds — they're just ignored by model)

**QA**: Test predict_game with empty `features.odds` → verify returns valid probabilities.

---

### Task 2.2: Wire Random Forest to Stats-Only Features

**File**: `backend/app/services/comparison_runner.py` (MODIFY)

**What**: Update the comparison runner to use `StatsFeatureEngineer` for RF training/evaluation.

**Changes**:
1. Import `StatsFeatureEngineer`
2. In `run_comparison()`:
   - Replace `self.engineer.prepare_features(data)` with `StatsFeatureEngineer.prepare_training_features(data)`
   - RF now trains on stats-only features (Elo, Four Factors, ratings)
   - Bayesian evaluation stays the same (uses posterior_prob from its own pipeline)
3. RF training: use ALL stats features (no `drop(columns=["posterior_prob", "edge"])` needed — those columns won't exist)
4. Update `format_report()` to show both model feature sets clearly

**Acceptance Criteria**:
- RF trains on 30 stats-only features
- Comparison still works for Bayesian vs RF
- Feature importance shows meaningful stats features (not odds-derived)

**QA**: Test comparison with mock data — verify RF trains without odds columns.

---

### Task 2.3: Wire Bayesian Prior to Model Probability

**File**: `backend/app/services/bayesian.py` (MODIFY)

**What**: When `devig_prob` is not available, use XGBoost model probability as the Bayesian prior instead of defaulting to 0.5.

**Changes**:
1. Add new parameter to `compute_posterior()`: `model_prob: Optional[float] = None`
2. Prior selection logic (line 56 area):
   ```python
   if devig_prob and devig_prob != 0.5:
       prior_prob = devig_prob  # Market-informed prior (best)
   elif model_prob and model_prob != 0.5:
       prior_prob = model_prob  # Model-informed prior (good)
   else:
       prior_prob = 0.5  # Uninformed prior (last resort)
   ```
3. Log which prior source was used: `logger.info(f"Bayesian prior: {prior_source} = {prior_prob:.3f}")`
4. Increase prior strength when using model_prob: `alpha = prior_prob * 6, beta = (1-prior_prob) * 6` (strength=6 vs current strength=4) — model-informed priors deserve more weight than uninformed
5. Edge calculation: when no `implied_prob`, compute edge against model's own prior: `edge = posterior_p - prior_prob` (meaningful even without market)

**DO NOT change**: Monte Carlo simulation, adjustment factors, Kelly calculation — those are fine.

**Acceptance Criteria**:
- `compute_posterior(data)` with no devig_prob but with model_prob produces meaningful non-0.5 posterior
- Log output shows "Bayesian prior: model = 0.647"
- Edge is computed against prior, not implied_prob, when implied unavailable

**QA**: Test with devig_prob=None, model_prob=0.65 → verify posterior is ~0.65 adjusted by factors, not ~0.50.

---

### Task 2.4: Make Sharp Money Signals Optional

**Files**:
- `backend/run_ncaab_analysis.py` (MODIFY)
- `backend/app/services/analysis_runner.py` (MODIFY)

**What**: Wrap all SharpMoneyDetector calls in conditional blocks. Pipeline runs without them.

**Changes to run_ncaab_analysis.py**:
1. Add config flag at top: `ENABLE_SHARP_SIGNALS = os.getenv("ENABLE_SHARP_SIGNALS", "false").lower() == "true"`
2. Wrap `SharpMoneyDetector.analyze_game()` call (line 599-610) in:
   ```python
   if ENABLE_SHARP_SIGNALS:
       sharp_analysis = SharpMoneyDetector.analyze_game(...)
       sharp_side = sharp_analysis["sharp_side"]
       signals = sharp_analysis["sharp_signals"]
       signal_confidence = sharp_analysis["signal_confidence"]
   else:
       sharp_side = None
       signals = []
       signal_confidence = 0.0
   ```
3. All downstream code already handles empty signals (line 618-622 checks `if "RLM" in signals`)
4. Sharp boost: already 0.0 when no signals — no change needed
5. Remove `estimate_public_splits()` usage when sharp signals disabled (it's only needed for fake public splits)

**Changes to analysis_runner.py**:
- Same pattern: check `ENABLE_SHARP_SIGNALS` before calling sharp money detector

**DO NOT delete** SharpMoneyDetector or any of its code — just gate the calls.

**Acceptance Criteria**:
- `ENABLE_SHARP_SIGNALS=false python backend/run_ncaab_analysis.py` runs successfully with no sharp signal output
- `ENABLE_SHARP_SIGNALS=true` preserves existing behavior
- Default is `false` (off by default)

**QA**: Run analysis with flag on/off → verify output differs only in signal sections.

---

## Wave 3: Standalone Entry Points — Run Without Odds

Depends on: Wave 2 complete.

### Task 3.1: Create Prediction-Only NBA Entry Point

**File**: `backend/run_nba_predictions.py` (NEW)

**What**: A standalone script that produces NBA game predictions using ONLY stats data — no Odds API calls.

**Requirements**:
```python
"""
NBA Predictions — Stats-Only Mode

Produces win probabilities and projected totals using:
- XGBoost ML models (trained on historical stats)
- Elo ratings
- Rolling advanced stats (Four Factors)
- Bayesian posterior with model-informed prior

NO Odds API calls. NO EV calculation. NO Kelly sizing.
For full analysis with odds: use run_nba_analysis.py

Usage: python backend/run_nba_predictions.py
"""
```

**Flow**:
1. Discover today's games via ESPN (free, no API key) — reuse `sports_api.discover_games()`
2. For each game:
   a. Fetch live stats via `nba_api` (free)
   b. Compute features via `StatsFeatureEngineer`
   c. XGBoost predict → win probability
   d. Bayesian posterior with model_prob as prior
   e. Elo prediction as sanity check
3. Output: table of games with win probabilities from each model
4. Return structured dict (same format as `run_nba_analysis.py` but without EV/Kelly fields)

**Output format**:
```
  NBA PREDICTIONS — Stats Only — Monday, February 27, 2026
  Models: XGBoost + Bayesian + Elo

  LAL vs BOS
    XGBoost:    LAL 42.3% / BOS 57.7%
    Bayesian:   LAL 40.1% / BOS 59.9%
    Elo:        LAL 44.8% / BOS 55.2%
    Consensus:  BOS 57.9% (weighted avg)
```

**Acceptance Criteria**:
- Runs with ZERO API key requirements (nba_api + ESPN are free)
- Produces predictions for all today's games
- Works even if Odds API key is not set
- Returns structured data consumable by Telegram/Sheets services

**QA**: Run script → verify output, no network errors, no odds-related code paths hit.

---

### Task 3.2: Create Prediction-Only NCAAB Entry Point

**File**: `backend/run_ncaab_predictions.py` (NEW)

**What**: Same as Task 3.1 but for NCAAB. Uses NCAABStatsService + Elo + Pythagorean.

**Flow**:
1. Discover games via ESPN `discover_games("basketball_ncaab")`
2. Fetch team stats via `NCAABStatsService.fetch_all_team_stats()` (AdjOE/AdjDE)
3. Compute features: Pythagorean Expectation from AdjOE/AdjDE (already in `calculate_model_prob()`)
4. Elo prediction
5. Bayesian posterior with model_prob as prior
6. Output consensus probabilities

**Acceptance Criteria**:
- Runs with zero API keys
- Uses existing `calculate_model_prob()` function (proven working)
- Handles games with missing stats gracefully

**QA**: Run during NCAAB season → verify output for all games on slate.

---

### Task 3.3: Add Prediction Mode to Existing Entry Points

**Files**:
- `backend/run_nba_analysis.py` (MODIFY)
- `backend/run_ncaab_analysis.py` (MODIFY)

**What**: Add `--predict-only` flag that skips odds fetching, EV calc, Kelly sizing, and sharp money — outputs predictions only.

**Changes to run_nba_analysis.py**:
1. Add argparse: `--predict-only` flag
2. When flag set:
   - Skip `self.sports_api.get_odds()` call entirely
   - Use StatsFeatureEngineer for features (no odds in features dict)
   - Skip `_calculate_expected_value()` — set EV to None
   - Skip Kelly sizing
   - Print prediction-only output (probabilities, no bet sizing)
3. When flag NOT set: existing behavior unchanged

**Same pattern for run_ncaab_analysis.py**:
- `--predict-only` → skip odds fetch, sharp money, Kelly portfolio
- Just print: game, model_prob, elo_prob, bayesian_posterior, consensus

**Acceptance Criteria**:
- `python backend/run_nba_analysis.py --predict-only` works with no Odds API key
- `python backend/run_nba_analysis.py` (no flag) behaves exactly as before
- No breaking changes to existing callers

**QA**: Run both modes → verify predict-only skips odds, full mode unchanged.

---

### Task 3.4: Update Bayesian Pipeline for Dual-Mode Operation

**File**: `backend/app/services/bayesian.py` (MODIFY — continuation of Task 2.3)

**What**: Ensure `compute_posterior` works cleanly in both modes.

**Changes**:
1. Add `mode` parameter: `compute_posterior(data, mode="full")` where mode is "full" or "prediction_only"
2. In `prediction_only` mode:
   - Skip edge calculation against implied_prob
   - Skip Kelly sizing (return kelly=0.0)
   - Return: posterior_p, confidence_interval, adjustments applied
3. In `full` mode: existing behavior unchanged
4. Log mode: `logger.info(f"Bayesian mode: {mode}")`

**Acceptance Criteria**:
- `mode="prediction_only"` returns valid posterior without implied_prob
- `mode="full"` is backward compatible

**QA**: Test both modes with same input → verify prediction_only skips EV/Kelly.

---

## Wave 4: Integration & Validation

Depends on: Wave 3 complete.

### Task 4.1: Update Telegram Report for Prediction-Only Mode

**File**: `backend/app/services/telegram_service.py` (MODIFY)

**What**: Support sending prediction-only reports (no bet sizing) alongside full analysis reports.

**Changes**:
1. Add method: `format_predictions_report(predictions: List[Dict]) -> str`
   - Formats consensus probabilities without EV/Kelly
   - HTML parse mode, 4096 char limit
2. Existing `format_analysis_report()` unchanged
3. In `telegram_cron.py`: if Odds API unavailable, send prediction-only report instead of failing silently

**Acceptance Criteria**:
- Telegram bot sends useful report even without odds data
- Full report format unchanged when odds available

**QA**: Test format with mock prediction data → verify HTML output.

---

### Task 4.2: Update Orchestrator for Dual-Mode

**File**: `backend/app/agents/orchestrator.py` (MODIFY)

**What**: OrchestratorAgent should detect if Odds API is available and automatically fall back to prediction-only mode.

**Changes**:
1. At start of orchestration: check if Odds API returns data
2. If no odds: run prediction-only pipeline automatically
3. If odds available: run full analysis pipeline
4. Log: `logger.info(f"Orchestrator mode: {'full' if odds_available else 'prediction_only'}")`

**Acceptance Criteria**:
- Orchestrator never crashes due to missing odds
- Prediction-only mode runs automatically when odds unavailable
- Full mode runs when odds exist

**QA**: Test with Odds API key unset → verify prediction-only pipeline activates.

---

### Task 4.3: Store Odds API Key in Environment Config

**What**: Ensure the Odds API key is properly stored and the system gracefully handles its absence.

**Changes**:
1. Add to `.env`: `ODDS_API_KEY=d798a347c6a179f0ae0d011f66144b3e`
2. In `app/config.py` settings: ensure `ODDS_API_KEY` is Optional (already is)
3. In `sports_api.py`: log when key is missing: `logger.warning("ODDS_API_KEY not set — odds features unavailable")`
4. Add rate limiting awareness: log remaining API credits on each call
5. Add to `.env.example`: `ODDS_API_KEY=  # Optional. 20K calls/month. Get from the-odds-api.com`

**Acceptance Criteria**:
- Platform runs without ODDS_API_KEY set (prediction-only mode)
- When set, rate-limits are logged
- Key never appears in logs or committed files

**QA**: Run without key → verify graceful degradation. Run with key → verify rate limit logging.

---

### Task 4.4: Ensure 60/40 Blend Degrades Gracefully

**File**: `backend/run_ncaab_analysis.py` (MODIFY)

**What**: The hardcoded `0.60 * true_home_prob + 0.40 * model_home_prob` blend (line 595) should dynamically adjust when devig is unavailable.

**Changes**:
```python
if true_home_prob and true_home_prob != 0.5:
    # Market data available — use blend
    blended_home_prob = 0.60 * true_home_prob + 0.40 * game["model_home_prob"]
else:
    # No market data — 100% model
    blended_home_prob = game["model_home_prob"]
```

**Acceptance Criteria**:
- When devig returns meaningful probs → 60/40 blend (existing)
- When devig returns 0.5/0.5 → 100% model prob
- Logged: which blend mode was used

**QA**: Test with mock devig=0.5 → verify 100% model used.

---

## Wave 5: Training Execution & Model Validation

Depends on: Wave 1 + Wave 2 complete (can run in parallel with Wave 3-4).

### Task 5.1: Backfill Elo Ratings

**Script**: `backend/scripts/backfill_elo.py` (NEW)

**What**: Fetch historical NBA game results and compute Elo ratings from 2015-present.

**Requirements**:
- Use `nba_api.stats.endpoints.leaguegamefinder` for historical games
- Process chronologically (oldest first)
- Save to `./models/elo/nba_elo.pkl`
- Log: starting ratings, ending ratings, number of games processed
- Rate limit: 0.6s between nba_api calls

**Acceptance Criteria**:
- `./models/elo/nba_elo.pkl` exists with all 30 NBA team ratings
- Ratings are reasonable (top teams ~1600-1700, bottom ~1300-1400)

**QA**: Verify top 5 teams by Elo match recent standings.

---

### Task 5.2: Train XGBoost Models

**Script**: `backend/scripts/train_models.py` (from Task 1.4)

**What**: Execute the training pipeline to produce actual model files.

**Execution**:
```bash
python backend/scripts/train_models.py --sport nba --seasons 2018-2025
```

**Acceptance Criteria**:
- `./models/nba_ml/moneyline_model.pkl` exists and loads
- `./models/nba_ml/moneyline_calibrated.pkl` exists and loads
- Walk-forward validation: accuracy ≥ 65% (should be ~69-72%)
- Brier score < 0.25
- Calibration: predicted 60% events actually occur ~55-65% of the time

**QA**: Load model → predict on test set → verify accuracy metrics.

---

### Task 5.3: Train Random Forest Model

**What**: Train RF on stats-only features and save.

**Execution**:
```bash
python backend/scripts/train_models.py --sport nba --model rf
```

**Acceptance Criteria**:
- `./models/rf/nba_model.pkl` exists
- Feature importance shows stats features (Elo, net_rating, eFG) not odds features
- Accuracy ≥ 63%

**QA**: Compare RF feature importance with XGBoost — verify stats features dominate.

---

## Wave 6: End-to-End Verification

Depends on: ALL previous waves complete.

### Task 6.1: Run Full Test Suite

```bash
cd backend && pytest
```

**Acceptance Criteria**: 262/262 tests pass (or more — new tests added).

---

### Task 6.2: Run Prediction-Only Mode End-to-End

```bash
# Unset Odds API key
unset ODDS_API_KEY

# NBA predictions
python backend/run_nba_predictions.py
python backend/run_nba_analysis.py --predict-only

# NCAAB predictions
python backend/run_ncaab_predictions.py
python backend/run_ncaab_analysis.py --predict-only
```

**Acceptance Criteria**:
- All 4 commands produce valid output
- Zero odds API calls made
- Probabilities from XGBoost, Bayesian, Elo are all reasonable (not 0.5 everywhere)

---

### Task 6.3: Run Full Analysis Mode End-to-End

```bash
export ODDS_API_KEY=d798a347c6a179f0ae0d011f66144b3e
export ENABLE_SHARP_SIGNALS=false

python backend/run_nba_analysis.py
python backend/run_ncaab_analysis.py
```

**Acceptance Criteria**:
- Full pipeline works with odds
- No sharp money signals in output (disabled)
- Model probabilities come from trained XGBoost (not Pythagorean fallback)
- EV calculation uses model prob vs devigged odds
- Kelly sizing produces reasonable bet sizes

---

### Task 6.4: Verify Odds API Efficiency

**What**: Confirm Odds API calls are minimal.

**Check**:
- Count API calls in a single run: should be ≤ 2 (one for NBA, one for NCAAB)
- Verify caching: second run within 5 min makes 0 API calls
- Log shows: "Odds API: 2 calls used, ~19,998 remaining this month"

**Acceptance Criteria**:
- Single analysis run: ≤ 2 Odds API calls
- Cached runs: 0 calls
- 20K monthly budget supports ~300 full analyses/month (more than enough for 3x daily)

---

## Final Verification Wave

### Run All Acceptance Tests
```bash
cd backend && pytest -v
python backend/run_nba_predictions.py
python backend/run_ncaab_predictions.py
ODDS_API_KEY=d798a347c6a179f0ae0d011f66144b3e python backend/run_nba_analysis.py
ODDS_API_KEY=d798a347c6a179f0ae0d011f66144b3e ENABLE_SHARP_SIGNALS=false python backend/run_ncaab_analysis.py
```

All commands should complete without errors and produce valid output.

---

## Architecture Summary (After Refactoring)

```
PREDICTION PIPELINE (odds-free):
  ESPN/nba_api → Stats → StatsFeatureEngineer → [XGBoost, Elo, Bayesian] → Win Probabilities
                              ↓
                    Rolling Stats, Four Factors,
                    Elo Differential, ORTG/DRTG

VALUATION PIPELINE (needs odds — optional):
  Win Probabilities + Odds API → Devig → EV Calculation → Kelly Sizing → Bet Recommendations
                                            ↓
                               [Sharp Money Signals — optional enhancement]
```

## Files Created/Modified Summary

| File | Action | Wave |
|------|--------|------|
| `backend/app/services/elo_service.py` | NEW | 1.1 |
| `backend/app/services/rolling_stats.py` | NEW | 1.2 |
| `backend/app/services/stats_feature_engineering.py` | NEW | 1.3 |
| `backend/app/services/ml/data_fetcher.py` | NEW | 1.4 |
| `backend/app/services/ml/trainer.py` | NEW | 1.4 |
| `backend/scripts/train_models.py` | NEW | 1.4 |
| `backend/scripts/backfill_elo.py` | NEW | 5.1 |
| `backend/run_nba_predictions.py` | NEW | 3.1 |
| `backend/run_ncaab_predictions.py` | NEW | 3.2 |
| `backend/app/services/nba_ml_predictor.py` | MODIFY | 2.1 |
| `backend/app/services/comparison_runner.py` | MODIFY | 2.2 |
| `backend/app/services/bayesian.py` | MODIFY | 2.3, 3.4 |
| `backend/run_ncaab_analysis.py` | MODIFY | 2.4, 3.3, 4.4 |
| `backend/run_nba_analysis.py` | MODIFY | 3.3 |
| `backend/app/services/analysis_runner.py` | MODIFY | 2.4 |
| `backend/app/services/telegram_service.py` | MODIFY | 4.1 |
| `backend/app/agents/orchestrator.py` | MODIFY | 4.2 |
| `models/` | CREATED | 1.4, 5.x |

**Existing files NOT modified**: sharp_money_detector.py, prop_analyzer.py, multivariate_kelly.py, feature_engineering.py, random_forest_model.py, sports_api.py
