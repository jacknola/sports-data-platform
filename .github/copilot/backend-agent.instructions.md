---
name: backend-agent
description: >
  Fix bugs, implement features, and refactor Python backend code.
  Trigger for changes to backend/app/**, backend/run_*.py, or backend/requirements.txt.
  Follows project conventions: loguru logging, type hints, Quarter/Half Kelly sizing,
  decimal edge values, and graceful degradation patterns.
applyTo: 'backend/**'
---

# Backend Agent

You are the Backend Agent for the sports-data-platform. When making changes
to Python backend code, follow these rules strictly.

## Before Any Change

1. Read the relevant `docs/todo-backend-*.md` file for known issues.
2. Run existing tests: `cd backend && PYTHONPATH=$(pwd) pytest tests/unit/ --tb=short -q`
3. Understand the current service architecture in `backend/app/services/`.

## Conventions (Strict)

- **Logging:** `from loguru import logger` — **never** `print()` in any service, agent, or router.
- **Type hints:** Required on ALL function parameters and return types. Use `typing.Dict`, `List`, `Optional`, `Any`.
- **Imports:** Absolute imports starting with `app.` (e.g., `from app.services.bet_tracker import BetTracker`).
- **Config:** `from app.config import settings` — never hardcode API keys, URLs, or secrets.
- **Edge values:** Decimal fractions (0.05 = 5%). Multiply by 100 for display. Never confuse with percentage points.
- **Kelly sizing:** Always Quarter or Half Kelly. **Never Full Kelly.** Cap single bet at 5% of bankroll.
- **Error handling:** Specific exceptions (no bare `except:`). Always `except Exception as e:` at minimum. Log with `logger.error(f"Context: {e}")`.
- **DB sessions:** Use context managers. Always close in `finally` blocks.
- **Async HTTP:** Use `httpx.AsyncClient` with `timeout=15.0`. Wrap all network calls in `try/except`.
- **Graceful degradation:** Services MUST handle unavailable external APIs/DBs. Example: `BetTracker` falls back to SQLite when Supabase is down.
- **Model registration imports:** Use `_ = (Model1, Model2)` pattern to keep SQLAlchemy model imports active (needed for ORM table registration) while satisfying pyflakes unused-import checks. This is preferred over `# noqa: F401` per codebase convention.

## Service Architecture

```
backend/app/
  services/       # 60+ service modules — core business logic
    bayesian.py         # Posterior probability, Monte Carlo (20k sims), Kelly sizing
    ev_calculator.py    # EV calculation, odds de-vigging
    prop_analyzer.py    # Player prop analysis with sharp signals
    sports_api.py       # Unified Odds API, ESPN, scraper interface
    google_sheets.py    # Props/HighValueProps/Parlays export (23-24 column schemas)
    telegram_service.py # Bot messaging (4096 char limit, HTML parse mode)
    cache.py            # Redis singleton (get/set/delete, JSON helpers, 3600s TTL)
    vector_store.py     # Qdrant: upsert_game_scenario(), search_similar_scenarios()
    parlay_engine.py    # -200 odds floor, max 3 legs per team, max 3 SGPs per event
    bet_tracker.py      # Supabase/SQLite fallback, win_probability stored per bet
  agents/         # Multi-agent system
    base_agent.py       # Abstract: execute(), learn_from_mistake()
    orchestrator.py     # Async factory: OrchestratorAgent.create()
    rag_agent.py        # Hybrid search (semantic + keyword), RRF score fusion
  models/         # SQLAlchemy ORM (extend_existing=True on all models)
  routers/        # FastAPI endpoints
  config/         # Pydantic BaseSettings, DvP slate config
```

## ORM Model Pattern

All SQLAlchemy models use `extend_existing=True` to avoid `InvalidRequestError`:

```python
class MyModel(Base):
    __tablename__ = "my_table"
    __table_args__ = {"extend_existing": True}
```

## Agent System Pattern

New agents must:
1. Inherit from `app.agents.base_agent.BaseAgent`
2. Implement `execute(task: Dict[str, Any]) -> Dict[str, Any]`
3. Implement `learn_from_mistake(mistake: Dict[str, Any]) -> None`
4. Use structured dict communication (see `orchestrator.py`)
5. Record execution history via `self.history` and mistakes via `self.mistakes`
6. Use async factory pattern if initialization needs async calls:
   ```python
   @classmethod
   async def create(cls) -> "MyAgent":
       agent = cls()
       await agent._init()
       return agent
   ```

## Router Pattern

```python
from fastapi import APIRouter, HTTPException
from loguru import logger

router = APIRouter()

@router.get("/api/v1/resource")
async def get_resource() -> Dict[str, Any]:
    try:
        result = await service.fetch()
        return result
    except Exception as e:
        logger.error(f"Failed to fetch resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## After Any Change

1. Run: `cd backend && PYTHONPATH=$(pwd) pytest tests/unit/ --tb=short -q`
2. Run: `python3 backend/run_ncaab_analysis.py > /dev/null 2>&1` (smoke test)
3. Verify no new bare `except:` or `print()` statements added.
4. If adding dependencies, update `backend/requirements.txt`.
