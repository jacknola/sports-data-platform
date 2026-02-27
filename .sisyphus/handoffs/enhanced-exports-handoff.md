# Handoff: Enhanced Exports — Model Predictions, Advanced Metrics, Win/Loss Tracking

**Created**: Feb 27, 2026
**Plan**: `.sisyphus/plans/enhanced-exports.md`
**Status**: Plan complete, ready for `/start-work`

---

## What Was Done This Session

1. **Explored 4 areas** via parallel agents: Sheets export pipeline, model prediction outputs, player props status, advanced metrics availability
2. **Ran Metis gap analysis** — found 3 critical bugs and corrected 3 wrong assumptions
3. **Updated bankroll** from $25 → $100 in 4 files (export_to_sheets.py, send_slack_report.py, run_ncaab_analysis.py, props.py router)
4. **Wrote comprehensive plan** at `.sisyphus/plans/enhanced-exports.md` with 5 waves, 11 tasks

## Uncommitted Changes

Bankroll update ($25 → $100) in:
- `backend/export_to_sheets.py:36`
- `backend/send_slack_report.py:37`
- `backend/run_ncaab_analysis.py:51`
- `backend/app/routers/props.py:44`

Plus many other uncommitted changes from prior sessions (see `git status`).

---

## The Plan (Summary)

**Goal**: Surface all model predictions + advanced metrics in Google Sheets NBA export. Automate win/loss tracking. Verify props.

### Wave 1: Settlement Bug Fix (5 min)
- Fix `bet_settlement.py:25` — "nba" must map to "basketball_nba" for Odds API scores
- Currently broken: NBA bet settlement silently fails

### Wave 2: Wire Models into Prediction Pipeline (45-60 min)
- **Elo**: Call `self.elo_service.predict_win_prob()` standalone in `predict_game()` (currently only used as XGBoost input feature)
- **Random Forest**: Load `models/rf/nba_model.pkl`, call `predict_proba()` with StatsFeatureEngineer features. Guard: verify feature alignment via `model.feature_names_in_`
- **Bayesian**: Call `BayesianAnalyzer().compute_posterior()` with XGBoost model_prob + Pinnacle implied_prob. Works for NBA as-is (no adaptation needed)
- **Advanced Metrics**: Extract ORtg/DRtg/NetRtg/Pace/eFG% from already-computed features DataFrame
- Add `model_predictions` + `advanced_metrics` dicts to predict_game() return

### Wave 3: Expand Sheets NBA Tab (30 min)
- Append 18 new columns: 8 model columns (4 models × Win% + Margin) + 10 metric columns (5 per team)
- Read from new `model_predictions` and `advanced_metrics` keys

### Wave 4: Win/Loss Results Tab (30 min)
- Add `export_results()` to GoogleSheetsService — append-only Results tab
- Wire into `telegram_cron.py` after existing settlement (lines 110-111)
- Columns: Date, Sport, Game, Side, Market, Odds, Line, Edge%, Bet Size, Status, P/L, CLV, Settled At

### Wave 5: Props Verification (10 min)
- Run `python backend/export_to_sheets.py --props-only`
- Observation only, no code changes

---

## Critical Context for Next Session

### Bugs That MUST Be Fixed First
1. **BetSettlementEngine sport mapping** (`bet_settlement.py:25`): `"nba"` doesn't get mapped to `"basketball_nba"`. Settlement fails for NBA bets.

### Wrong Assumptions (Corrected by Metis)
1. Elo predictions are NOT currently computed standalone — only used as XGBoost input feature via StatsFeatureEngineer
2. Bayesian works for NBA as-is — conference tier defaults to `power_5` (zero penalty). No adaptation needed.
3. Settlement ALREADY runs 3x daily in `telegram_cron.py:110-111` — just need Sheets export after it

### Risk Items
- **RF Feature Mismatch**: Model expects 34 features. Must verify alignment. If fails, skip RF (3 models still sufficient)
- **Rest/B2B Stubbed**: `_get_rest_days()` returns 1, `_is_back_to_back()` returns False always. OMIT from Sheets.
- **Scope Creep**: Do NOT build RF training pipeline. Use existing `.pkl` only.

### Key File Map
| File | Purpose |
|------|---------|
| `backend/app/services/nba_ml_predictor.py` | Main prediction pipeline — Wire Elo/RF/Bayesian here |
| `backend/app/services/google_sheets.py` | Sheets export — Add columns + Results tab here |
| `backend/app/services/bet_settlement.py` | Settlement — Fix sport mapping bug |
| `backend/telegram_cron.py` | Cron — Wire results export after settlement |
| `backend/app/services/elo_service.py` | Elo predictions (already implemented) |
| `backend/app/services/random_forest_model.py` | RF model wrapper (already implemented) |
| `backend/app/services/bayesian.py` | Bayesian analyzer (already implemented) |
| `backend/app/services/stats_feature_engineering.py` | 30 features including all advanced metrics |
| `backend/app/services/rolling_stats.py` | Rolling team stats (ORtg/DRtg/Pace/eFG%) |
| `backend/export_to_sheets.py` | CLI entry point for Sheets export |

### QA
- Verification scripts in plan for each task
- `pytest backend/` must pass (262+ tests)
- Use `lsp_diagnostics` on all changed files

---

## How to Start

```
/start-work
```

Then reference plan: `.sisyphus/plans/enhanced-exports.md`

Execute waves in order: 1 → 2 → 3 → 4 → 5. Wave 1 is a 1-line bug fix that unblocks everything.
