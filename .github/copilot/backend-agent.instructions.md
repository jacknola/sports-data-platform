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
to Python backend code, follow these rules:

## Before Any Change
1. Read the relevant `docs/todo-backend-*.md` file for known issues.
2. Run existing tests: `cd backend && PYTHONPATH=$(pwd) pytest tests/unit/ --tb=short -q`
3. Understand the current service architecture in `backend/app/services/`.

## Conventions (Strict)
- **Logging:** `from loguru import logger` — never `print()`.
- **Type hints:** Required on all function parameters and return types.
- **Imports:** Absolute, starting with `app.` (e.g., `from app.services.bet_tracker import BetTracker`).
- **Config:** Load via `from app.config import settings`.
- **Edge values:** Decimal fractions (0.05 = 5%). Multiply by 100 for display.
- **Kelly sizing:** Always Quarter or Half Kelly. Never Full Kelly. Max 5% single bet.
- **Error handling:** Specific exceptions (no bare `except:`). Log with `logger.error()`.
- **DB sessions:** Use context managers. Always close sessions in `finally` blocks.
- **Async HTTP:** Use `httpx.AsyncClient` with `timeout=15.0`.

## Agent System Pattern
New agents must:
1. Inherit from `app.agents.base_agent.BaseAgent`
2. Implement `execute(task: Dict[str, Any]) -> Dict[str, Any]`
3. Implement `learn_from_mistake(mistake: Dict[str, Any]) -> None`
4. Use structured dict communication (see orchestrator.py)
5. Record execution history and mistakes

## After Any Change
1. Run: `cd backend && PYTHONPATH=$(pwd) pytest tests/unit/ --tb=short -q`
2. Run: `python3 backend/run_ncaab_analysis.py > /dev/null 2>&1` (smoke test)
3. Verify no new bare `except:` or `print()` statements added.
