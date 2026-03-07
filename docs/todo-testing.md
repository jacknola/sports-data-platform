# Testing — Code Issues & Suggested Fixes

> Generated from review of `backend/tests/` and `frontend/src/test/`.

---

## Test Infrastructure

### backend/pytest.ini

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | LOW | `log_cli_level = WARNING` hides useful INFO logs during debugging | Use `INFO` for local, `WARNING` for CI |
| 2 | LOW | No coverage reporting configured | Add `--cov=app --cov-report=term-missing --cov-fail-under=70` |

### backend/tests/conftest.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Handles config import conflict (Pydantic vs package) — fragile workaround | Rename `app/config.py` to avoid conflict with `app/config/` directory |
| 2 | LOW | Test SECRET_KEY is `"test_secret_key_not_for_production"` — clear but verbose | Use shorter key, document why it's not production |

---

## Test Coverage Gaps

### Missing Unit Tests

| # | Service | Has Tests? | Priority |
|---|---------|------------|----------|
| 1 | `rag_pipeline.py` | Partial (`test_google_sheets_rag.py`) | HIGH — RAG is critical for data retrieval |
| 2 | `multivariate_kelly.py` | No | HIGH — financial calculations need validation |
| 3 | `prop_probability.py` | No | HIGH — probability model needs edge case testing |
| 4 | `telegram_service.py` | No | MEDIUM — message formatting and chunking |
| 5 | `inference_service.py` | No (`test_random_forest_model.py` covers RF) | MEDIUM — inference pipeline needs testing |
| 6 | `parlay_engine.py` | Partial (`test_parlay_helpers.py`) | MEDIUM — full generation pipeline untested |
| 7 | `sports_api.py` | Partial (`test_sports_api_sgo_fallback.py`) | MEDIUM — main API paths untested |
| 8 | `nba_ml_predictor.py` | Yes (`test_nba_ml_predictor.py`) | OK — expand edge cases |
| 9 | `google_sheets.py` | Yes (2 test files) | OK — expand with export validation |

### Missing Integration Tests

| # | Component | Has Tests? | Priority |
|---|-----------|------------|----------|
| 1 | Full prop analysis pipeline | No | HIGH — end-to-end prop analysis |
| 2 | Parlay generation + export | No | HIGH — parlay suggestion pipeline |
| 3 | Telegram report sending | No | MEDIUM — mock Telegram API |
| 4 | Agent orchestration flow | No | MEDIUM — multi-agent coordination |
| 5 | Prediction → bet tracking → settlement | No | HIGH — money flow pipeline |

---

## Existing Test Quality Issues

### Unit Tests (backend/tests/unit/)

| # | Test File | Severity | Issue | Suggested Fix |
|---|-----------|----------|-------|---------------|
| 1 | `test_bayesian.py` | MEDIUM | Tests basic flow but no edge cases (zero prob, extreme values) | Add parametrized edge case tests |
| 2 | `test_ev_calculator.py` | MEDIUM | Mocks most dependencies — doesn't test real calculation paths | Add tests with real number inputs |
| 3 | `test_bet_tracker.py` | LOW | Tests save/retrieve but not settlement or CLV tracking | Add settlement and CLV calculation tests |
| 4 | `test_orchestrator.py` | MEDIUM | Tests initialization but not full orchestration flow | Add end-to-end orchestration test with mock agents |
| 5 | `test_sharp_money_tracker.py` | LOW | May not cover the duplicated RLM detection code | Add test that covers both RLM code paths |
| 6 | `test_nba_dvp_analyzer.py` | MEDIUM | DvP fallback data not tested | Add test for `_fallback_player_baselines()` |

### Integration Tests (backend/tests/integration/)

| # | Test File | Severity | Issue | Suggested Fix |
|---|-----------|----------|-------|---------------|
| 1 | `test_google_sheets_service.py` | MEDIUM | May timeout on real API calls | Add `@pytest.mark.slow` marker and mock for CI |
| 2 | `test_dvp_router.py` | LOW | Router test but no DvP data validation | Add response schema validation |
| 3 | `test_bets_router.py` | LOW | Basic CRUD but no edge cases | Add tests for invalid inputs, boundary values |

---

## Frontend Test Gaps

| # | Component | Has Tests? | Priority | Suggested Fix |
|---|-----------|------------|----------|---------------|
| 1 | `Dashboard.tsx` | No | HIGH | Add render test, loading state, error state |
| 2 | `Agents.tsx` | No | MEDIUM | Test agent list rendering and status display |
| 3 | `Bets.tsx` | No | MEDIUM | Test bet listing, filtering, empty state |
| 4 | `Parlays.tsx` | No | MEDIUM | Test parlay display and status updates |
| 5 | `Analysis.tsx` | No | LOW | Test analysis form submission |
| 6 | `Settings.tsx` | No | LOW | Test settings form validation |
| 7 | `CollegeBasketball.tsx` | No | LOW | Test NCAAB page rendering |
| 8 | `QuickStats.tsx` | No | LOW | Test stat card rendering |
| 9 | `ActionCard.tsx` | No | LOW | Test card interactions |
| 10 | `AgentStatus.tsx` | No | LOW | Test status indicator states |

---

## Recommendations

### Quick Wins
1. Add `--cov` to pytest.ini for automatic coverage tracking
2. Add parametrized edge case tests to `test_bayesian.py` and `test_ev_calculator.py`
3. Create `test_multivariate_kelly.py` with known portfolio optimization scenarios
4. Create basic render tests for all frontend page components

### Medium-Term
1. Implement MSW (Mock Service Worker) for frontend API testing
2. Add property-based testing (Hypothesis) for probability calculations
3. Create `test_prop_probability.py` with distribution validation
4. Add integration test for full prop analysis pipeline

### Long-Term
1. Achieve ≥70% code coverage
2. Add end-to-end Playwright tests for frontend
3. Implement mutation testing to validate test quality
4. Add performance/load testing for API endpoints

---

## Summary

| Area | Missing Tests | Priority |
|------|--------------|----------|
| RAG pipeline | Unit + integration | HIGH |
| Multivariate Kelly | Unit | HIGH |
| Prop probability | Unit | HIGH |
| Full pipeline integration | Integration | HIGH |
| Frontend pages (7 components) | Unit | MEDIUM |
| Telegram service | Unit | MEDIUM |
| Agent orchestration | Integration | MEDIUM |

**Total test gaps: ~25 missing test files across backend and frontend**
