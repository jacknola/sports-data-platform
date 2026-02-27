# Plan: Enhanced Exports — Model Predictions, Advanced Metrics, Win/Loss Tracking

## Goal
Surface all model predictions (XGBoost, Elo, Random Forest, Bayesian) and advanced metrics in the Google Sheets NBA export. Automate win/loss tracking with a dedicated Results tab. Verify player props pipeline.

## Scope
- **In scope**: NBA Sheets export enhancement, prediction pipeline wiring, settlement bug fix, Results tab, props verification
- **Out of scope**: Frontend dashboard, Telegram changes, RF model retraining, new API integrations, rest/B2B schedule lookups

## Key Decisions
- Bankroll: $100 (updated from $25 in all scripts)
- Per-model columns: Each model gets Win Prob % AND Predicted Margin columns
- Advanced metrics: Core Four (ORtg, DRtg, Net Rating, Pace) + eFG% per team
- Rest/B2B: OMIT from Sheets (currently stubbed as hardcoded values)
- Bayesian for NBA: Use XGBoost model_prob + Pinnacle implied_prob (blended)
- RF: Use existing trained model, skip gracefully if feature alignment fails
- Results tab: Append-only (accumulates over time, never overwrites)

## Critical Bugs to Fix (from Metis Gap Analysis)
1. **BetSettlementEngine sport mapping** (`bet_settlement.py:25`): `"nba"` passes through as-is instead of mapping to `"basketball_nba"`. NBA settlement is broken.
2. **Rest/B2B stubbed**: `_get_rest_days()` returns 1, `_is_back_to_back()` returns False always. Do NOT surface these.
3. **RF feature mismatch risk**: Model trained with 34 features. Must verify alignment via `model.feature_names_in_` before prediction.

## Corrected Assumptions (from Metis)
- Elo is currently used only as INPUT feature to XGBoost, not as standalone prediction → must ADD standalone call
- Bayesian works for NBA as-is (conference tier defaults to zero penalty) → NO adaptation needed
- Settlement already runs 3x daily in `telegram_cron.py:110-111` → only need to add Sheets export after settlement

---

## Wave 1: Settlement Bug Fix (Unblocks Win/Loss Tracking)

### Task 1.1: Fix BetSettlementEngine Sport Mapping
- **File**: `backend/app/services/bet_settlement.py`
- **Change**: At line ~25, fix sport mapping:
  ```python
  SPORT_MAP = {"ncaab": "basketball_ncaab", "nba": "basketball_nba"}
  api_sport = SPORT_MAP.get(sport, sport)
  ```
- **Verify**: `assert 'basketball_nba' in inspect.getsource(settle_pending_bets)`
- **Risk**: LOW — one-line fix, no side effects

---

## Wave 2: Wire Models into Prediction Pipeline

### Task 2.1: Add Elo Standalone Prediction to predict_game()
- **File**: `backend/app/services/nba_ml_predictor.py`
- **Change**: In `predict_game()`, call `self.elo_service.predict_win_prob(home_team, away_team)` and store result
- **Output**: `elo_win_prob: float` (0-1), `elo_margin: (prob - 0.5) * -26`
- **Note**: EloService already initialized in `__init__`. Just need to call it.

### Task 2.2: Add Random Forest Prediction to predict_game()
- **File**: `backend/app/services/nba_ml_predictor.py`
- **Change**: Load `models/rf/nba_model.pkl` via sklearn pickle, call `predict_proba(features)` using same StatsFeatureEngineer features
- **Guard**: Verify feature alignment with `model.feature_names_in_`. If mismatch, log warning, set RF values to None
- **Guard**: If model file missing, log warning, set RF values to None
- **Output**: `rf_win_prob: float|None`, `rf_margin: float|None`

### Task 2.3: Add Bayesian Prediction to predict_game()
- **File**: `backend/app/services/nba_ml_predictor.py`
- **Change**: Call `BayesianAnalyzer().compute_posterior()` with:
  - `model_prob`: XGBoost win probability
  - `implied_prob`: From Pinnacle/sharp odds (already extracted in predict_today_games)
- **Output**: `bayesian_posterior: float`, `bayesian_margin: (posterior - 0.5) * -26`
- **Note**: Bayesian works for NBA as-is. No adaptation needed.

### Task 2.4: Structure model_predictions in Return Dict
- **File**: `backend/app/services/nba_ml_predictor.py`
- **Change**: Add to predict_game() return dict:
  ```python
  "model_predictions": {
      "xgboost": {"win_prob": xgb_prob, "margin": (xgb_prob - 0.5) * -26},
      "elo": {"win_prob": elo_prob, "margin": (elo_prob - 0.5) * -26},
      "random_forest": {"win_prob": rf_prob, "margin": rf_margin},  # None if unavailable
      "bayesian": {"win_prob": bayes_post, "margin": (bayes_post - 0.5) * -26}
  }
  ```
- **MUST**: Keep existing `home_win_probability` key unchanged for backward compatibility
- **MUST NOT**: Change `method` field semantics

### Task 2.5: Propagate Advanced Metrics from Features to Return Dict
- **File**: `backend/app/services/nba_ml_predictor.py`
- **Change**: Extract from already-computed `features` DataFrame and add to return dict:
  ```python
  "advanced_metrics": {
      "home": {"off_rating": float, "def_rating": float, "net_rating": float, "pace": float, "eFG_pct": float},
      "away": {"off_rating": float, "def_rating": float, "net_rating": float, "pace": float, "eFG_pct": float}
  }
  ```
- **Source**: `features["home_off_rating"]`, `features["home_def_rating"]`, etc. — already computed in `_prepare_features()`
- **MUST NOT**: Add new API calls. All data already fetched.

---

## Wave 3: Expand Google Sheets NBA Tab

### Task 3.1: Add Per-Model Prediction Columns to NBA Tab
- **File**: `backend/app/services/google_sheets.py`
- **Change**: In `export_nba()`, append new columns AFTER existing 20:
  ```
  XGB Win% | XGB Margin | Elo Win% | Elo Margin | RF Win% | RF Margin | Bayes Win% | Bayes Margin
  ```
- **Source**: `p.get("model_predictions", {})`
- **Format**: Percentages to 1 decimal (e.g., "62.3%"), margins to 1 decimal (e.g., "-3.2")
- **Guard**: If model_predictions missing or model value is None → empty string

### Task 3.2: Add Advanced Metrics Columns to NBA Tab
- **File**: `backend/app/services/google_sheets.py`
- **Change**: Append after model columns:
  ```
  Home ORtg | Home DRtg | Home NetRtg | Home Pace | Home eFG% | Away ORtg | Away DRtg | Away NetRtg | Away Pace | Away eFG%
  ```
- **Source**: `p.get("advanced_metrics", {})`
- **Format**: Ratings to 1 decimal, pace to 1 decimal, eFG% to 1 decimal with %
- **Guard**: If advanced_metrics missing → empty strings

### Task 3.3: Update Headers
- **File**: `backend/app/services/google_sheets.py`
- **Change**: Update NBA tab header row to include all 38 columns (20 existing + 8 model + 10 metrics)
- **Pattern**: Follow existing `_get_or_create_worksheet()` + header write pattern

---

## Wave 4: Win/Loss Results Tab

### Task 4.1: Add export_results() Method to GoogleSheetsService
- **File**: `backend/app/services/google_sheets.py`
- **Change**: New method `export_results(spreadsheet_id, results)` that:
  1. Gets or creates "Results" worksheet
  2. On first run: writes headers
  3. Appends rows (NEVER clears — accumulates over time)
  ```
  Headers: Date | Sport | Game | Side | Market | Odds | Line | Edge% | Bet Size | Status | P/L | CLV | Settled At
  ```
- **Pattern**: Use `ws.append_rows()` not `ws.update()`
- **Source**: `BetTracker.get_settled_bets()` or similar query for resolved bets

### Task 4.2: Wire Results Export into telegram_cron.py
- **File**: `backend/telegram_cron.py`
- **Change**: After settlement at lines 110-111, call `sheets_service.export_results()` with newly settled bets
- **MUST NOT**: Create new cron or scheduler — piggyback on existing 3x daily runs
- **Guard**: If Sheets not configured, skip silently

---

## Wave 5: Props Verification

### Task 5.1: Run Props Export Live Test
- **Command**: `python backend/export_to_sheets.py --props-only`
- **Verify**: 
  - Exit code 0 (or graceful "no data" message)
  - No Python tracebacks
  - Props tab populates in Google Sheets (if games available)
  - Report: number of props found, number +EV, any errors
- **MUST NOT**: Modify any props pipeline code — observation only

---

## QA / Acceptance Criteria

### Automated Verification Scripts

**Task 2 (model predictions + metrics):**
```bash
cd backend && python3 -c "
import asyncio, json
from app.services.nba_ml_predictor import NBAMLPredictor
p = NBAMLPredictor()
preds = asyncio.run(p.predict_today_games('nba', prediction_only=True))
if preds:
    pred = preds[0]
    assert 'model_predictions' in pred, 'Missing model_predictions key'
    mp = pred['model_predictions']
    for model in ['xgboost', 'elo', 'bayesian']:
        assert model in mp, f'Missing {model}'
        assert 'win_prob' in mp[model], f'Missing win_prob in {model}'
        assert 'margin' in mp[model], f'Missing margin in {model}'
    assert 'advanced_metrics' in pred, 'Missing advanced_metrics key'
    am = pred['advanced_metrics']
    for side in ['home', 'away']:
        for m in ['off_rating', 'def_rating', 'net_rating', 'pace', 'eFG_pct']:
            assert m in am[side], f'Missing {m} in {side}'
    print('PASS: All model predictions and advanced metrics present')
else:
    print('SKIP: No games today')
"
```

**Task 1 (settlement fix):**
```bash
cd backend && python3 -c "
from app.services.bet_settlement import BetSettlementEngine
import inspect
source = inspect.getsource(BetSettlementEngine.settle_pending_bets)
assert 'basketball_nba' in source, 'NBA sport mapping not fixed'
print('PASS: NBA sport mapping fixed')
"
```

**Full regression:**
```bash
cd backend && PYTHONPATH=$(pwd) pytest tests/ -x -q
# Expect: 262+ tests pass
```

---

## File Change Map

| File | Change Type | Wave |
|------|-------------|------|
| `backend/app/services/bet_settlement.py` | Bug fix (sport mapping) | 1 |
| `backend/app/services/nba_ml_predictor.py` | Wire Elo/RF/Bayesian + metrics | 2 |
| `backend/app/services/google_sheets.py` | Add 18 new columns + Results tab | 3, 4 |
| `backend/telegram_cron.py` | Wire results export after settlement | 4 |
| `backend/export_to_sheets.py` | Bankroll $100 (already done) | — |
| `backend/send_slack_report.py` | Bankroll $100 (already done) | — |
| `backend/run_ncaab_analysis.py` | Bankroll $100 (already done) | — |
| `backend/app/routers/props.py` | Bankroll $100 (already done) | — |

## Estimated Effort
- Wave 1: 5 minutes (one-line fix)
- Wave 2: 45-60 minutes (core model wiring)
- Wave 3: 30 minutes (Sheets columns)
- Wave 4: 30 minutes (Results tab + cron)
- Wave 5: 10 minutes (props test)
- **Total: ~2-2.5 hours**
