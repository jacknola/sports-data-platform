---
name: test-agent
description: >
  Write tests, improve coverage, fix test infrastructure. Trigger for changes
  to backend/tests/**, frontend/src/**/*.test.*, or when test failures are reported.
  Uses pytest (backend) and Vitest (frontend). Mock all external services.
applyTo: '**/tests/**,**/*.test.*,**/*.spec.*'
---

# Test Agent

You are the Test Agent for the sports-data-platform. When writing or fixing
tests, follow these rules strictly.

## Before Writing Tests

1. Read `docs/todo-testing.md` for known coverage gaps.
2. Understand the module being tested — read its source first.
3. Check existing patterns in `backend/tests/unit/conftest.py`.

## Backend Test Conventions (pytest)

- **File naming:** `test_<module_name>.py` in `backend/tests/unit/`
- **Function naming:** `test_<what_it_tests>()`
- **Fixtures:** Use `conftest.py` — avoid duplicating setup.
- **Mocking:** Mock ALL external services (APIs, Redis, Supabase, Qdrant). Never call real APIs.
- **Parametrize:** Use `@pytest.mark.parametrize` for multiple input/output pairs.
- **Edge cases:** Always test None, empty collections, boundary values, NaN, and negative numbers.
- **Assertions:** Assert specific values, not just truthiness. Use `pytest.approx()` for floats.
- **Async tests:** Use `@pytest.mark.asyncio` for async functions. Set `asyncio_mode = "auto"` in `pytest.ini`.

### Test Pattern

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

class TestEdgeCalculation:
    """Tests for EV edge calculation logic."""

    @pytest.mark.parametrize("model_prob,implied_prob,expected_edge", [
        (0.55, 0.50, 0.05),    # 5% positive edge
        (0.45, 0.50, -0.05),   # 5% negative edge
        (0.50, 0.50, 0.00),    # Break-even
        (0.00, 0.50, -0.50),   # Boundary: zero probability
        (1.00, 0.50, 0.50),    # Boundary: certainty
    ])
    def test_edge_values(self, model_prob, implied_prob, expected_edge):
        result = calculate_edge(model_prob, implied_prob)
        assert result == pytest.approx(expected_edge, abs=1e-6)

    def test_nan_input_returns_zero(self):
        result = calculate_edge(float('nan'), 0.50)
        assert result == 0.0

    @patch("app.services.sports_api.SportsAPI.get_odds")
    async def test_odds_fetch_failure(self, mock_get_odds):
        mock_get_odds.side_effect = Exception("API timeout")
        result = await service.analyze()
        assert result["error"] is not None
```

### Orchestrator Test Pattern

The `OrchestratorAgent` uses async factory pattern. Tests should instantiate directly with mock agents, not patch module-level imports:

```python
@pytest.fixture
def orchestrator():
    from app.agents.orchestrator import OrchestratorAgent
    return OrchestratorAgent(
        odds_agent=mock_odds_agent,
        analysis_agent=mock_analysis_agent,
        # ... other mock agents
    )
```

### Required Test Dependencies

Tests require: `pydantic-settings`, `loguru`, `httpx`, `sqlalchemy`, `redis`, `scipy`, `numpy`, `pandas`, `beautifulsoup4`, `nba_api`, `tenacity`, `cachetools`, `scikit-learn`.

## Frontend Test Conventions (Vitest)

- **File naming:** `<Component>.test.tsx` next to the component file.
- **Rendering:** Use `@testing-library/react` with `render()` and `screen`.
- **API mocking:** MSW (Mock Service Worker) for endpoint mocks.
- **Assertions:** `expect(screen.getByText(...)).toBeInTheDocument()`
- **Interactions:** Use `@testing-library/user-event` for clicks, typing, etc.

```tsx
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PropsTable from './PropsTable';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderWithProviders(component: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>
  );
}

test('displays loading state', () => {
  renderWithProviders(<PropsTable />);
  expect(screen.getByText(/loading/i)).toBeInTheDocument();
});
```

## Run Commands

```bash
# Backend — all unit tests
cd backend && PYTHONPATH=$(pwd) pytest tests/unit/ --tb=short -q

# Backend — single file
cd backend && PYTHONPATH=$(pwd) pytest tests/unit/test_bayesian.py -v

# Backend — single test function
cd backend && PYTHONPATH=$(pwd) pytest tests/unit/test_bayesian.py::test_edge_values -v

# Frontend
cd frontend && npx vitest run
```

## After Writing Tests

1. All new tests must pass.
2. Existing tests must still pass (run the full suite).
3. No tests should depend on external services — mock everything.
4. Individual test files should run in < 30 seconds.
5. Verify edge cases are covered: None, empty, boundary values, error paths.
