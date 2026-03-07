# Backend Services — Code Issues & Suggested Fixes

> Generated from full codebase review. Organized by file, severity, and suggested fix.

---

## rag_pipeline.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `json.loads(cached)` (≈line 163) has no try/except — corrupted Redis data will crash | Wrap in `try/except json.JSONDecodeError` and invalidate cache on failure |
| 2 | MEDIUM | Generic `except Exception as e:` in multiple places (lines 39, 144, 237) | Replace with specific exception types (`ConnectionError`, `OperationalError`, etc.) |
| 3 | MEDIUM | `SessionLocal()` resource leak risk — if exception before `finally`, session stays open | Use `with contextmanager` or guarantee `finally` block |
| 4 | MEDIUM | `parlay_data` passed directly to Parlay model without validation | Add Pydantic schema validation before DB insert |
| 5 | MEDIUM | Potential division by zero: `won_count / total` assumes `total > 0` | Guard with `if total == 0: return 0.0` before calculation |
| 6 | LOW | `numpy` imported but not used directly | Remove unused import |
| 7 | LOW | 7-day TTL hard-coded (line 131) | Move to `settings.CACHE_TTL_SECONDS` |

---

## bayesian.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `prior_prob` parameter in `_compute_adjustments()` defined but never used | Remove unused parameter or integrate into calculation |
| 2 | MEDIUM | `adjusted_prob` clipped to [0.01, 0.99] without logging when clipping occurs | Add `logger.debug()` when value is clipped |
| 3 | MEDIUM | Beta parameters and `pseudo_obs` are magic numbers (lines 88, 101) | Extract to class constants: `BETA_PSEUDO_OBS = 10` |
| 4 | MEDIUM | `np.random.beta()` could fail with invalid alpha/beta — no validation | Add `assert alpha > 0 and beta > 0` or clamp before call |
| 5 | MEDIUM | `_get_conference_spread_adjustment()` lacks parameter documentation | Add docstring with parameter descriptions |
| 6 | LOW | `kelly_fraction` always set to 0.0 in both branches — dead code? | Verify intent or implement actual Kelly calculation |
| 7 | LOW | Return types mix `float()` calls with direct numpy types | Consistently cast to Python `float()` before returning |

---

## prop_analyzer.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | Identical RLM check logic duplicated (lines 311-316 repeated at 331-352) | Remove duplicate block; extract to helper method |
| 2 | MEDIUM | `self._volatility_history[prop_id]` sliced without bounds checking | Add `len()` check before slicing |
| 3 | MEDIUM | `timestamp` parameter without timezone handling consistency | Normalize to UTC with `datetime.now(timezone.utc)` |
| 4 | MEDIUM | `except Exception:` swallows all errors in `LineMovementAnalyzer().record_clv()` | Catch specific `(ValueError, ConnectionError)` |
| 5 | MEDIUM | `_check_rlm()`, `_check_juice_shift()` lack return type hints | Add `-> Optional[PropSignal]` return type |
| 6 | MEDIUM | `devig_prop()` static method lacks description of devigging algorithm | Add docstring explaining method and formula |
| 7 | LOW | Sharp side logic is inverted/confusing (lines 544-552) | Refactor with clear variable names and comments |

---

## ev_calculator.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | `SessionLocal()` resource leak — if exception occurs before try block closes | Use context manager: `with SessionLocal() as db:` |
| 2 | HIGH | `except Exception: pass` silently swallows timestamp parsing errors (line 494) | Log the error: `except Exception as e: logger.warning(f"Timestamp parse error: {e}")` |
| 3 | MEDIUM | `pinnacle_over_odds` used without None check before calculating devig | Add `if pinnacle_over_odds is None: return None` guard |
| 4 | MEDIUM | MODEL_WEIGHTS hard-coded (lines 57-64) — no validation that they sum to 1.0 | Add `assert abs(sum(MODEL_WEIGHTS.values()) - 1.0) < 0.001` |
| 5 | MEDIUM | `datetime.now(ts.tzinfo)` could fail if `ts.tzinfo is None` | Check `if ts.tzinfo:` before using, default to UTC |
| 6 | MEDIUM | `_estimate_confidence()` uses unexplained bonus values (0.20, 0.15, 0.10) | Document derivation and extract to named constants |
| 7 | LOW | Clipping to [0.05, 0.95] loses information about extreme estimates | Log when clipping occurs, consider wider range |

---

## sharp_money_tracker.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | CRITICAL | RLM detection block duplicated verbatim (lines 311-352) | Remove duplicate; extract to `_detect_rlm()` helper |
| 2 | HIGH | `confidence` attribute referenced but `SharpSignal` class doesn't define it | Add `confidence: float` to `SharpSignal.__init__()` |
| 3 | MEDIUM | `np.mean()` called on possibly empty lists (line 286-289) | Guard with `if values: np.mean(values) else 0.5` |
| 4 | MEDIUM | Conditional logic confusing in strict mode (lines 313-316) | Refactor with clear early returns |
| 5 | MEDIUM | `SignalMetadata` imported but source unclear — could be incompatible schema | Verify import path and add type checking |
| 6 | MEDIUM | Mock data generation hardcoded (lines 700+) | Make injectable for testing via constructor parameter |

---

## multivariate_kelly.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Covariance calculation assumes `std_devs` correct — derivation from Bernoulli unclear | Add docstring with mathematical derivation |
| 2 | MEDIUM | Empty portfolio returns `np.array([[]])` — shape mismatch downstream | Return empty list or raise `ValueError` for empty portfolio |
| 3 | MEDIUM | `if not result.success:` logs warning but continues with potentially invalid solution | Return zero-allocation when optimization fails |
| 4 | MEDIUM | If all bets perfectly correlated, covariance matrix is singular — no check | Add `np.linalg.cond()` check before solving |
| 5 | MEDIUM | Correlation constants lack justification/sources | Add docstring citing research sources |
| 6 | LOW | `_round_fractions()` uses magic number 400 without explanation | Add comment: `# 400 = 1/0.0025, rounds to 0.25% increments` |

---

## nba_dvp_analyzer.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | `json.load(f)` can fail if file is corrupted — no validation (line 216) | Wrap in `try/except json.JSONDecodeError` with fallback |
| 2 | MEDIUM | `spread` and `total` default to 0.0 — if both remain 0, silently skipped | Log warning when defaults are used |
| 3 | MEDIUM | Fallback DvP multipliers are hard-coded estimates without source documentation | Document sources in docstring or constants file |
| 4 | MEDIUM | `min((rank - 141) / 9.0 * 0.05, 0.05)` could exceed bounds if rank > 150 | Add assertion: `assert 0 <= rank <= 150` |
| 5 | MEDIUM | `except Exception as e:` hides CSV parsing failures (line 299-341) | Catch `(FileNotFoundError, csv.Error, KeyError)` specifically |
| 6 | MEDIUM | Assumes team names in TEAM_NAME_TO_ABBREV exactly match Odds API output — fragile | Add fuzzy matching or normalization layer |
| 7 | MEDIUM | `_fallback_player_baselines()` is 400+ lines with minimal comments | Extract to JSON data file or separate module |

---

## sports_api.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `BOOKMAKER_FILTER` defined twice identically (lines 46-47) | Remove duplicate line |
| 2 | MEDIUM | Generic `Exception` catches (line 397, 477, 686) | Replace with specific `(httpx.HTTPError, json.JSONDecodeError)` |
| 3 | MEDIUM | `get_odds()` recursive fallback — no depth limit guard (line 667) | Add `max_retries` parameter with default of 3 |
| 4 | MEDIUM | Module-level `_cache` and `_db_cache` singletons with no locking — not thread-safe | Add `threading.Lock()` around cache operations |
| 5 | MEDIUM | Hard-coded TTLs (300, 3600, 600 seconds) | Move to `settings.CACHE_TTL_*` constants |
| 6 | LOW | Missing JSON parsing error handling in persistent cache retrieval | Add `try/except json.JSONDecodeError` |

---

## bet_tracker.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Silent failures on SQLite ALTER TABLE (lines 75-76, 79-81) | Log `logger.info()` for schema migration success/failure |
| 2 | MEDIUM | `SupabaseService()` initialization not wrapped in try/except | Add `try/except` with fallback to SQLite-only mode |
| 3 | MEDIUM | `datetime.utcnow()` used (deprecated) | Replace with `datetime.now(timezone.utc)` |
| 4 | MEDIUM | `db.close()` called without try/finally block for cleanup | Wrap in `try/finally` or use context manager |
| 5 | LOW | Magic number `-110` appears 4 times without named constant | Extract to `DEFAULT_JUICE = -110` |
| 6 | LOW | No validation on `edge` calculation inputs — could receive non-numeric | Add `isinstance(edge, (int, float))` check |

---

## nba_ml_predictor.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | `pickle.load()` is a security risk — unpickled objects execute arbitrary code | Replace with `joblib.load()` or `xgboost.Booster().load_model()` |
| 2 | MEDIUM | Multiple generic `Exception` catches (lines 105, 114, 152, 262) | Specify `(FileNotFoundError, ValueError, xgboost.core.XGBoostError)` |
| 3 | MEDIUM | `features.iloc[0]` accessed without bounds checking | Add `if features.empty: return fallback` |
| 4 | MEDIUM | `predict_proba()` return shape assumed but not validated | Add `assert probs.shape[1] == 2` after prediction |
| 5 | MEDIUM | `self.team_stats_cache` mutable singleton with no locking — race condition | Add `threading.Lock()` or use `functools.lru_cache` |
| 6 | LOW | League_avg=115.0, home_court bonus=0.03, exponent=14.0 — all magic numbers | Extract to class constants with documentation |

---

## telegram_service.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `%-d` and `%-I:%M` strftime modifiers are platform-specific (may fail on Windows) | Use `%d` and `%I:%M` with `.lstrip('0')` post-processing |
| 2 | LOW | Hard-coded timeouts (15.0 and 20.0 seconds) | Move to `settings.TELEGRAM_TIMEOUT` |
| 3 | LOW | Regex import inside method — should be at module level | Move `import re` to top of file |
| 4 | LOW | No rate limit jitter between retry attempts | Add `random.uniform(0, 1)` jitter to backoff |

---

## google_sheets.py (3123 lines)

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `_WorksheetNotFound` set to generic `Exception` when gspread unavailable | Use custom exception class instead |
| 2 | MEDIUM | `_col_name()` function potential off-by-one error in divmod logic | Add unit tests for column names A-ZZ |
| 3 | MEDIUM | Formatting row-by-row is very inefficient — should batch format requests | Collect all format requests and send in single `batch_update()` |
| 4 | MEDIUM | No validation for `bet_size <= 0` — could produce misleading P/L | Add `if bet_size <= 0: raise ValueError("Bet size must be positive")` |
| 5 | LOW | Hard-coded range queries (`startRowIndex: 1`) assume header is row 1 | Use named constant `HEADER_ROW = 1` |
| 6 | LOW | Silent logging on format errors at debug level | Elevate to `logger.warning()` for formatting failures |

---

## nba_stats_service.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `time.sleep(0.6)` blocks entire thread in sync context (lines 265, 343, 436) | Use `await asyncio.sleep(0.6)` in async methods |
| 2 | MEDIUM | No retry logic on nba_api calls with timeout=30 | Add `tenacity.retry` decorator with exponential backoff |
| 3 | MEDIUM | Generic `Exception` catches (lines 452, 483) | Specify `(requests.Timeout, requests.ConnectionError)` |
| 4 | MEDIUM | Potential division by zero (lines 611, 695) — no guard on `len(logs)` | Add `if not logs: return default` guard |
| 5 | LOW | Negative cache values (-1) used as sentinel without documentation | Add comment explaining sentinel pattern |
| 6 | LOW | Team abbreviation case-sensitivity not validated | Normalize with `.upper().strip()` |

---

## parlay_engine.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `_build_leg()` returns None but no null check in list comprehension | Use `[leg for leg in legs if leg is not None]` |
| 2 | MEDIUM | Fingerprint uses pipe-separated fields — collision if field contains "|" | Escape pipe characters or use hash-based fingerprint |
| 3 | MEDIUM | `ev_classification` could be "pass" or "" — inconsistent sentinel values | Standardize on single sentinel (e.g., always "pass") |
| 4 | LOW | Hard-coded limits (`_MIN_COMBINED_ODDS`, `_MAX_PARLAYS`) | Move to settings or constructor parameters |
| 5 | LOW | `_score_combo()` missing docstring explaining scoring methodology | Add docstring with formula explanation |

---

## vector_store.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `SentenceTransformer()` loaded eagerly in `__init__` — expensive on startup | Lazy-load on first use with `@property` |
| 2 | MEDIUM | No timeout on Qdrant operations — network requests could hang | Add `timeout=10` to Qdrant client |
| 3 | MEDIUM | Generic `Exception` catch (line 113) | Specify `(qdrant_client.QdrantException, ConnectionError)` |
| 4 | LOW | Hard-coded embedding model "all-MiniLM-L6-v2" | Move to `settings.EMBEDDING_MODEL` |
| 5 | LOW | Score threshold hard-coded at 0.5 | Expose as parameter with default |

---

## inference_service.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Hard-coded file paths (line 55) assume specific directory structure | Use `settings.MODEL_DIR` base path |
| 2 | MEDIUM | Missing features default to 0.0 — could mask data issues | Log warning for each missing feature |
| 3 | MEDIUM | `rf.fit()` could fail with singular matrices — no try/except | Wrap in `try/except sklearn.exceptions.NotFittedError` |
| 4 | MEDIUM | Generic `Exception` in feature extraction (line 236) | Specify `(KeyError, ValueError, TypeError)` |
| 5 | LOW | `random_state=42` not configurable | Move to settings or constructor parameter |
| 6 | LOW | When neighbors < 5, returns base rates without logging | Add `logger.debug("Insufficient neighbors")` |

---

## prop_probability.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Hard-coded league averages (`LEAGUE_AVG_PACE = 100.0`) — should be current season data | Pull from API or make configurable per season |
| 2 | MEDIUM | No validation on adjustment factors — could produce negative projected_mean | Add `projected_mean = max(projected_mean, 0.0)` guard |
| 3 | MEDIUM | Generic `Exception` in `batch_project()` | Specify `(ValueError, ZeroDivisionError)` |
| 4 | MEDIUM | All adjustment factors are magic numbers (0.40, 0.02, 0.5, etc.) | Extract to named constants with documentation |
| 5 | LOW | `usage_trend / 0.02` could be zero/negative | Add validation: `if usage_trend <= 0: return 1.0` |
| 6 | LOW | Logs with f-strings containing unvalidated floats — could throw if NaN/inf | Add `math.isfinite()` check before logging |

---

## Summary by Severity

| Severity | Count | Files Affected |
|----------|-------|----------------|
| CRITICAL | 1 | sharp_money_tracker.py |
| HIGH | 5 | prop_analyzer.py, ev_calculator.py (2), nba_dvp_analyzer.py, nba_ml_predictor.py |
| MEDIUM | 68 | All 17 service files |
| LOW | 19 | Various |

**Total Issues: 93**
