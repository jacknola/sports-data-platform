# Scripts — Code Issues & Suggested Fixes

> Generated from review of `backend/predict_props.py` and root `scripts/` directory.

---

## predict_props.py (Backend Root)

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | **CRITICAL** | Hardcoded database password: `"postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"` | Replace with `os.getenv("DATABASE_URL")` |
| 2 | HIGH | Web selectors (`.prop-bet-row`, `.player-name-link`) don't match actual BettingPros HTML | Verify actual selectors via browser DevTools; update accordingly |
| 3 | HIGH | `float(await line.inner_text())` assumes text is numeric — actual text could be "$45.5 Over" | Parse with regex: `float(re.search(r'\d+\.?\d*', text).group())` |
| 4 | HIGH | Model file `prop_model.json` loaded without checking existence | Add `Path(model_path).exists()` check with fallback |
| 5 | MEDIUM | Feature columns may not match training set — no validation | Validate features against `model.feature_names` before prediction |
| 6 | MEDIUM | `iloc[0]` assumes stats DataFrame is non-empty | Add `if df.empty: raise ValueError("No stats found")` |
| 7 | MEDIUM | SQL query uses raw SQL without parameterization (line 51) | Use `pd.read_sql(query, engine, params={"player": player_name})` |
| 8 | MEDIUM | 60-second Playwright timeout — could be too long | Reduce to 15-30 seconds with retry logic |
| 9 | LOW | Error recovery non-existent — logs warning but no retry or fallback | Add retry decorator with 3 attempts |
| 10 | LOW | No logging of prediction results | Add `logger.info(f"Predicted {player}: {prediction}")` |

---

## predict_props_v2.py — CREATED

The v2 script has been implemented at `scripts/predict_props_v2.py`. It includes:

- XGBoost + LightGBM + Bayesian Hierarchical stacked ensemble (35/30/35 weights)
- Platt calibration (via logistic transform in heuristic fallbacks)
- Monte Carlo simulation (20K iterations, Negative Binomial distribution)
- EWMA decay with stat-specific alpha values (from DARKO model research)
- Edge detection with de-vigging at 4.5% standard overround
- Quarter-Kelly sizing with 5% max bet cap
- Walk-forward TimeSeriesSplit validation (when trained models available)
- Single-prop and batch prediction modes via CLI

### Remaining TODO for v2:
| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Models use heuristic fallbacks when no trained `.json`/`.txt` files exist | Train models with `backend/app/services/ml/trainer.py` and save to `backend/models/` |
| 2 | MEDIUM | SHAP feature importance not yet integrated | Add `shap.TreeExplainer` after model training |
| 3 | LOW | No walk-forward cross-validation in script itself | Add `--validate` flag for TimeSeriesSplit evaluation |

---

## scripts/clean_model.gs

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | LOW | Google Sheets script — no documentation of what it cleans | Add header comment explaining purpose |
| 2 | LOW | Not integrated with backend pipeline | Document how/when to run this script |

---

## Run Scripts (backend/run_*.py)

### Common Issues Across All Run Scripts

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No consistent argument parsing | Use `argparse` or `click` for all run scripts |
| 2 | MEDIUM | Error handling varies — some scripts crash on API failures, others silently continue | Standardize with try/except at top level |
| 3 | LOW | No `--dry-run` option for testing without side effects | Add `--dry-run` flag that logs actions without executing |
| 4 | LOW | No `--verbose` flag for debugging | Add `--verbose` / `-v` flag to increase log level |

---

## Summary

| File | Issues | Highest Severity |
|------|--------|-----------------|
| predict_props.py | 10 | CRITICAL |
| predict_props_v2.py | N/A | MISSING — needs creation |
| clean_model.gs | 2 | LOW |
| Run scripts (general) | 4 | MEDIUM |

**Total: 16 issues + 1 missing file**
