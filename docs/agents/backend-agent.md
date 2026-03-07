# Backend Agent — Actionable Tasks

> This agent handles all Python backend changes: services, models, routers, agents, and scripts.

---

## Identity & Scope

- **Name:** Backend Agent
- **Language:** Python 3.9+
- **Framework:** FastAPI, SQLAlchemy, Pydantic
- **Responsibilities:** Fix bugs, implement features, refactor services, maintain API endpoints

---

## Setup Commands

```bash
cd backend
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
```

## Verification Commands

```bash
# Run all tests
pytest tests/ --tb=short -q

# Run specific test file
pytest tests/unit/test_bayesian.py -v

# Run linting
ruff check app/ --fix
black app/ --check

# Run type checking
mypy app/ --ignore-missing-imports

# Verify no runtime errors
python3 run_ncaab_analysis.py > /dev/null 2>&1 && echo "OK" || echo "FAIL"
```

---

## Priority Tasks

### P0 — Critical Security Fixes

- [ ] **Remove hardcoded DB password** in `predict_props.py:11`
  - Replace `"postgresql://postgres:Maheart1622!@..."` with `os.getenv("DATABASE_URL")`
  - Verify `.env` has `DATABASE_URL` entry

- [ ] **Replace `pickle.load()` with safe alternative** in `nba_ml_predictor.py`
  - Use `joblib.load()` for sklearn models
  - Use `xgboost.Booster().load_model()` for XGBoost models

### P1 — High Priority Bug Fixes

- [ ] **Fix duplicated RLM detection** in `sharp_money_tracker.py:311-352`
  - Extract to `_detect_rlm()` helper method
  - Remove duplicate code block

- [ ] **Fix typo** in `analysis_agent.py:115`
  - Change `'probabilty_estimation'` → `'probability_estimation'`

- [ ] **Add null check for twitter_agent** in `orchestrator.py:223`
  - Add `if self.twitter_agent:` guard before `.execute()` call

- [ ] **Fix SessionLocal resource leaks** in `ev_calculator.py` and `rag_pipeline.py`
  - Convert to context managers

- [ ] **Fix silent exception handlers** in `ev_calculator.py:494`
  - Replace `except Exception: pass` with `except Exception as e: logger.warning(f"Error: {e}")`

### P2 — Medium Priority Improvements

- [ ] **Add CORS middleware** to `main.py`
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.ALLOWED_ORIGINS,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

- [ ] **Add model weight validation** in `ev_calculator.py`
  - Assert `abs(sum(MODEL_WEIGHTS.values()) - 1.0) < 0.001`

- [ ] **Replace bare exception catches** across all services
  - Target files: `prop_analyzer.py`, `sports_api.py`, `nba_stats_service.py`, `vector_store.py`

- [ ] **Add input validation** to routers
  - `analyze.py`: Add sport enum validation
  - `bets.py`: Add `Query(ge=0.0, le=1.0)` for edge parameter
  - `predictions.py`: Validate date_limit < today

- [ ] **Implement analyze.py endpoint** or return proper 501 status
  - Currently returns dummy response

- [ ] **Enforce SECRET_KEY in production**
  ```python
  @validator("SECRET_KEY")
  def validate_secret_key(cls, v):
      if v == "dev_secret_key_change_in_production":
          logger.warning("Using default SECRET_KEY — change for production")
      return v
  ```

### P3 — Feature Implementation

- [ ] **Create `scripts/predict_props_v2.py`** — ML prediction engine
  - XGBoost + LightGBM + Bayesian stacked ensemble
  - Walk-forward TimeSeriesSplit validation
  - Edge detection with de-vigging
  - Kelly criterion sizing
  - See `docs/todo-scripts.md` for full spec

- [ ] **Improve RAG pipeline** in `rag_pipeline.py`
  - Add chunking strategy for large documents
  - Implement hybrid search (semantic + keyword)
  - Add relevance scoring with re-ranking
  - Cache embeddings in Redis

- [ ] **Add API rate limiting**
  ```python
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  ```

- [ ] **Add connection pooling** in `database.py`
  - Use `QueuePool` for PostgreSQL production

---

## Code Style Rules

1. Use `from loguru import logger` — never `print()`
2. All functions need type hints on parameters and return types
3. Use `from app.config import settings` for configuration
4. Absolute imports: `from app.services.bet_tracker import BetTracker`
5. Add `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` to entry scripts
6. Edge values are decimal fractions (0.05 = 5%) — multiply by 100 for display
7. Always use Quarter or Half Kelly — never Full Kelly
8. Wrap network/DB calls in `try/except`, log with `logger.error()`

---

## Testing Checklist

After any change:
1. `pytest tests/unit/ -q` — all unit tests pass
2. `pytest tests/integration/ -q` — all integration tests pass (if applicable)
3. `ruff check app/` — no linting errors
4. `python3 run_ncaab_analysis.py > /dev/null` — no runtime errors
