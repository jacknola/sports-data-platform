---
description: 'Global instructions for GitHub Copilot when working on the sports-data-platform repository'
applyTo: '**'
---

# Sports Data Platform — Copilot Instructions

## Project Overview

Quantitative sports betting intelligence platform that identifies +EV (positive expected value) wagers by comparing devigged market-maker odds (Pinnacle/Circa) against retail sportsbooks (FanDuel, DraftKings). The system uses Bayesian modeling, XGBoost/LightGBM ML, sharp money signal detection (RLM, Steam, CLV), and Multivariate Fractional Kelly Criterion for portfolio-level bet sizing.

### Architecture

```
Market Data (Odds API, ESPN, Scrapers)
  → Sharp Signal Detection (RLM, Steam, CLV)
  → Bayesian + Monte Carlo Probability Engine (20k iterations)
  → ML Prediction Layer (XGBoost + LightGBM + Bayesian stacked ensemble)
  → DvP Matchup Analysis (Defense vs Position rankings)
  → Multivariate Kelly Criterion (Correlated portfolio optimization)
  → Expert Agent Review (Sequential Thinking MCP)
  → Final Slate Recommendations
  → Google Sheets / Telegram / Notion export
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.9+), Pydantic, SQLAlchemy |
| Database | Supabase/PostgreSQL (SQLite fallback for tests/dev) |
| Cache | Redis 7 |
| Vector DB | Qdrant (game scenarios, player performances, NBA props) |
| ML | XGBoost, LightGBM, scikit-learn, scipy, PyMC |
| Task Queue | Celery + Redis broker, Flower monitoring |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Query |
| Reporting | Telegram bot, Google Sheets (gspread), Notion API |
| MCP Servers | NotebookLM, Sequential Thinking, Redis |

## Build, Test, and Run Commands

### Backend

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run API server
python3 backend/run_server.py                # FastAPI on port 8000

# Run analysis scripts
python3 backend/run_ncaab_analysis.py        # NCAAB sharp money analysis
python3 backend/run_nba_analysis.py          # NBA XGBoost predictions

# Run tests (ALWAYS set PYTHONPATH)
cd backend && PYTHONPATH=$(pwd) pytest tests/unit/ --tb=short -q

# Run single test file
cd backend && PYTHONPATH=$(pwd) pytest tests/unit/test_bayesian.py -v

# Smoke test (verifies imports and runtime)
python3 backend/run_ncaab_analysis.py > /dev/null 2>&1

# Telegram reports
python3 backend/telegram_cron.py --send-now  # Immediate report
python3 backend/telegram_cron.py --daemon    # 3x daily scheduler
```

### Frontend

```bash
cd frontend && npm install
npm run dev       # Dev server on port 3000 (proxies /api → backend:8000)
npm run build     # TypeScript check + Vite production build
npm run lint      # ESLint with zero warnings policy
```

### Docker (Full Stack)

```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API Docs: http://localhost:8000/docs
# Flower:   http://localhost:5555
```

## Code Conventions (Enforced)

### Python Backend

- **Logging:** `from loguru import logger` — **never** use `print()` in any service or agent.
- **Type hints:** Required on ALL function parameters and return types. Use `typing.Dict`, `List`, `Optional`, `Any`.
- **Imports:** Absolute imports starting with `app.` (e.g., `from app.services.bet_tracker import BetTracker`).
- **Config:** Load via `from app.config import settings`. Never hardcode API keys or URLs.
- **Entry scripts** (`backend/run_*.py`): Add `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` at top.
- **Error handling:** Specific exceptions only — no bare `except:`. Always `except Exception as e:` at minimum. Log with `logger.error(f"Context: {e}")`.
- **DB sessions:** Use context managers. Always close in `finally` blocks.
- **Async HTTP:** Use `httpx.AsyncClient` with `timeout=15.0`. Wrap in `try/except`.
- **Graceful degradation:** All services must handle unavailable external APIs/DBs. Example: `BetTracker` falls back to SQLite when Supabase is down.
- **Model registration imports:** Use `_ = (Model1, Model2)` pattern to keep SQLAlchemy model imports active (needed for ORM table registration) while satisfying pyflakes unused-import checks. This is preferred over `# noqa: F401` per codebase convention.
- **Docstrings:** Required on all classes and public methods. Explain business logic (the *why*), not just the *what*.

### TypeScript Frontend

- **Components:** Functional with hooks only. No class components.
- **Server state:** React Query (`@tanstack/react-query`). No Redux or Context for API data.
- **Styling:** Tailwind CSS only. Custom colors: `primary-*`, `accent-*`. No inline styles unless dynamic.
- **Types:** No `any` type. No `@ts-ignore`. Define interfaces in `src/types/api.ts`.
- **API calls:** Use `src/utils/api.ts` axios wrapper. All requests prefixed with `/api`.
- **Path alias:** `@/*` maps to `./src/*`.
- **Environment:** Use `import.meta.env.VITE_*` pattern for env vars.
- **Strict compilation:** `noUnusedLocals` and `noUnusedParameters` are enabled.

## Betting Logic (Critical Domain Rules)

- **Edge values are decimal fractions**: `0.05` means 5% edge. Multiply by 100 for display. Never confuse with percentage points.
- **Devigging:** Always derive true probability from Pinnacle/sharp books before calculating EV: `EV = (True Probability × Decimal Odds) - 1`.
- **Odds format:** Internal calculations use Decimal odds or True Probabilities. Convert American odds via `american_to_decimal()`.
- **Kelly sizing:** Always Fractional Kelly (Quarter or Half). **Never Full Kelly.** Cap single bet at 5% of bankroll.
- **Edge thresholds:** Low ≥3% (quarter-Kelly), Medium ≥5% (half-Kelly), High ≥7%, Max conviction ≥10%.
- **Stake rounding:** Round Kelly outputs to human-like denominations ($412.37 → $425) to avoid algorithmic profiling.
- **CLV tracking:** `CLV > 0` consistently = profitable strategy. `CLV < 0` = no edge.
- **FanDuel is the primary book.** Odds floor of -200 for prop legs. Win probability is the primary ranking metric.

## Key Services Reference

| Service | Purpose |
|---------|---------|
| `bayesian.py` | Posterior probability, Monte Carlo (20k iterations), Kelly sizing |
| `prop_analyzer.py` | Player prop analysis with sharp signal identification |
| `ev_calculator.py` | Expected value calculation, de-vigging |
| `multivariate_kelly.py` | Correlated portfolio optimization via convex optimization |
| `nba_ml_predictor.py` | XGBoost predictions (optimize for calibration, not accuracy) |
| `nba_dvp_analyzer.py` | NBA Defense vs Position matchup analysis |
| `sports_api.py` | Unified interface for Odds API, ESPN, scrapers |
| `google_sheets.py` | Props, HighValueProps, Parlays export to Google Sheets |
| `telegram_service.py` | Bot messaging (4096 char limit, HTML parse mode) |
| `bet_tracker.py` | Wager lifecycle with Supabase/SQLite fallback |
| `parlay_engine.py` | Parlay suggestion generation with diversity rules |
| `cache.py` | Redis singleton wrapper (get/set/delete with JSON helpers, 3600s TTL) |
| `vector_store.py` | Qdrant vector DB for game scenarios and player embeddings |
| `rag_pipeline.py` | RAG retrieval for context-augmented analysis |
| `sharp_money_tracker.py` | RLM, steam move, CLV, head fake detection |

## Agent System

Agents inherit from `app.agents.base_agent.BaseAgent` and must implement:
- `execute(task: Dict[str, Any]) -> Dict[str, Any]` — main execution
- `learn_from_mistake(mistake: Dict[str, Any]) -> None` — feedback loop

The `OrchestratorAgent` coordinates all sub-agents via async factory pattern (`await OrchestratorAgent.create()`). It initializes: OddsAgent, AnalysisAgent, ExpertAgent, DvPAgent, NCAABDvPAgent, RAGAgent, and optionally TwitterAgent.

## Anti-Patterns (Never Do These)

- `print()` in services → use `logger` from loguru
- Bare `except:` → use `except Exception as e:` or specific types
- Full Kelly sizing → always Quarter or Half Kelly
- `as any` / `@ts-ignore` in TypeScript → create proper types
- Hardcoded secrets → use `settings.*` or `os.getenv()`
- Schema changes without verifying data flow
- Adding heavy dependencies (`torch`, `crawl4ai`) without justification

## File Organization

```
backend/
  app/
    agents/         # Multi-agent system (BaseAgent, Orchestrator, domain agents)
    config/         # Pydantic Settings, DvP slate JSON
    models/         # SQLAlchemy ORM models (Bet, Game, Player, Parlay, etc.)
    routers/        # FastAPI endpoints (props, bets, dvp, parlays, agents, etc.)
    services/       # Core business logic (60+ service modules)
    memory/         # Agent memory system (Redis-backed)
    database.py     # SQLAlchemy engine, Base, init_db()
    main.py         # FastAPI app with lifespan, CORS, router registration
  tests/unit/       # pytest unit tests (37+ test files)
  run_*.py          # CLI entry scripts

frontend/
  src/
    components/     # Reusable React components
    pages/          # Route-level page components
    types/          # TypeScript interfaces (api.ts)
    utils/          # Axios wrapper, helpers

scripts/            # Utility scripts (predict_props_v2.py)
docs/               # Todo lists, agent docs, suggestions
```
