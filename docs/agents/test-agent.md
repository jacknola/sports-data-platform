# Test Agent — Actionable Tasks

> This agent handles all testing: writing tests, improving coverage, fixing test infrastructure, and validating changes.

---

## Identity & Scope

- **Name:** Test Agent
- **Languages:** Python (pytest), TypeScript (Vitest)
- **Responsibilities:** Write unit/integration tests, fix broken tests, improve coverage, validate CI

---

## Setup Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
```

### Frontend
```bash
cd frontend
npm install
```

## Run Commands

### Backend Tests
```bash
# All unit tests
pytest tests/unit/ --tb=short -q

# All integration tests
pytest tests/integration/ --tb=short -q

# Single test file
pytest tests/unit/test_bayesian.py -v

# Single test function
pytest tests/unit/test_bayesian.py::test_calculate_posterior -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60

# Only failed tests from last run
pytest --lf
```

### Frontend Tests
```bash
cd frontend
npx vitest run              # All tests
npx vitest run --reporter=verbose  # Verbose output
npx vitest run src/utils/   # Single directory
```

---

## Priority Tasks

### P0 — Missing Critical Tests

- [ ] **Create `tests/unit/test_multivariate_kelly.py`**
  - Test portfolio optimization with known inputs/outputs
  - Test edge cases: empty portfolio, singular matrix, 100% correlation
  - Test Kelly fraction bounds (never > 5% single bet)
  - Test `_round_fractions()` with edge values
  ```python
  def test_kelly_single_bet():
      """Quarter-Kelly on a single bet should match hand-calculated result."""
      kelly = MultivariateKelly()
      result = kelly.optimize([{"prob": 0.55, "odds": -110}])
      assert 0 < result[0]["fraction"] <= 0.05

  def test_kelly_empty_portfolio():
      """Empty portfolio should return empty result."""
      kelly = MultivariateKelly()
      result = kelly.optimize([])
      assert result == []
  ```

- [ ] **Create `tests/unit/test_prop_probability.py`**
  - Test Normal distribution calculations
  - Test adjustment factors don't produce negative projections
  - Test over/under probability sum ≈ 1.0
  - Test pace adjustment scaling
  ```python
  def test_over_under_sum_to_one():
      """Over + Under probability should approximately sum to 1.0."""
      pp = PropProbability()
      result = pp.project(mean=25.0, std=5.0, line=22.5)
      assert abs(result["over_prob"] + result["under_prob"] - 1.0) < 0.001
  ```

- [ ] **Create `tests/unit/test_rag_pipeline.py`**
  - Test embedding generation
  - Test semantic search with mock Qdrant
  - Test cache invalidation
  - Test parlay-to-dict conversion

### P1 — Fix Existing Test Gaps

- [ ] **Add edge case tests to `test_bayesian.py`**
  ```python
  @pytest.mark.parametrize("prob", [0.0, 0.01, 0.5, 0.99, 1.0])
  def test_posterior_boundary_values(prob):
      """Posterior should handle boundary probability values."""
      result = bayesian.calculate_posterior(prob)
      assert 0.0 < result < 1.0

  def test_nan_handling():
      """NaN inputs should not crash the Bayesian calculator."""
      result = bayesian.calculate_posterior(float('nan'))
      assert not math.isnan(result)
  ```

- [ ] **Add real calculation tests to `test_ev_calculator.py`**
  - Test with known decimal odds and true probabilities
  - Verify EV = (True Probability × Decimal Odds) - 1

- [ ] **Add settlement tests to `test_bet_tracker.py`**
  - Test win settlement with correct P/L calculation
  - Test loss settlement
  - Test CLV tracking after settlement

- [ ] **Add DvP fallback tests to `test_nba_dvp_analyzer.py`**
  - Test `_fallback_player_baselines()` returns valid data
  - Test with missing team in TEAM_NAME_TO_ABBREV

### P2 — Integration Tests

- [ ] **Create `tests/integration/test_prop_pipeline.py`**
  - End-to-end: fetch props → analyze → calculate EV → size bets
  - Mock external APIs, use real internal logic
  ```python
  @pytest.mark.integration
  async def test_full_prop_analysis_pipeline():
      """Test complete prop analysis from odds to Kelly sizing."""
      # Mock external data
      with patch("app.services.sports_api.get_props") as mock_props:
          mock_props.return_value = SAMPLE_PROPS
          result = await orchestrator.execute_prop_analysis("NBA")
          assert "picks" in result
          for pick in result["picks"]:
              assert "kelly_fraction" in pick
              assert pick["kelly_fraction"] <= 0.05  # Max 5%
  ```

- [ ] **Create `tests/integration/test_agent_orchestration.py`**
  - Test multi-agent coordination flow
  - Verify agents communicate correctly
  - Test error propagation between agents

- [ ] **Create `tests/integration/test_parlay_pipeline.py`**
  - Test parlay generation → scoring → export
  - Verify deduplication works
  - Test SGP and cross-game combinations

### P3 — Frontend Tests

- [ ] **Create `Dashboard.test.tsx`**
  ```typescript
  describe('Dashboard', () => {
    it('renders loading state', () => {
      // Mock useQuery to return isLoading: true
      render(<Dashboard />);
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('renders error state', () => {
      // Mock useQuery to return error
      render(<Dashboard />);
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });

    it('renders agent status cards', () => {
      // Mock useQuery with agent data
      render(<Dashboard />);
      expect(screen.getAllByTestId('agent-card')).toHaveLength(5);
    });
  });
  ```

- [ ] **Install and configure MSW for API mocking**
  ```bash
  npm install -D msw
  ```
  Create `test/mocks/handlers.ts` with all API endpoint mocks

- [ ] **Create render tests for all pages**
  - Bets.test.tsx, Parlays.test.tsx, Analysis.test.tsx, Settings.test.tsx

### P4 — Test Infrastructure

- [ ] **Add coverage reporting to pytest.ini**
  ```ini
  addopts = --tb=short -q --cov=app --cov-report=term-missing
  ```

- [ ] **Add `@pytest.mark.slow` marker** for tests that hit real APIs
  ```python
  # conftest.py
  def pytest_configure(config):
      config.addinivalue_line("markers", "slow: marks tests as slow (deselect with -m 'not slow')")
  ```

- [ ] **Add property-based testing** for probability calculations
  ```bash
  pip install hypothesis
  ```
  ```python
  from hypothesis import given, strategies as st

  @given(prob=st.floats(min_value=0.01, max_value=0.99))
  def test_ev_calculation_properties(prob):
      """EV should be positive when true prob > implied prob."""
      implied = 0.5
      ev = (prob * 2.0) - 1  # decimal odds = 2.0
      if prob > implied:
          assert ev > 0
  ```

---

## Testing Conventions

1. **File naming:** `test_<module_name>.py`
2. **Function naming:** `test_<what_it_tests>`
3. **Use fixtures** from `conftest.py` — avoid duplicating setup
4. **Mock external services** — never call real APIs in unit tests
5. **Use `@pytest.mark.parametrize`** for multiple input variations
6. **Assert specific values** — not just "result is truthy"
7. **Test edge cases:** None, empty, boundary values, NaN, negative
8. **Frontend:** Use `@testing-library/react` + MSW for component tests

---

## Verification Checklist

After writing tests:
1. `pytest tests/unit/ -q` — all pass
2. `pytest tests/unit/ --cov=app --cov-report=term-missing` — coverage ≥ 60%
3. New tests cover the specific bug/feature being implemented
4. No tests depend on external services (all mocked)
5. Tests run in < 30 seconds total
