# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Context
Quantitative sports betting platform that identifies +EV wagers by comparing devigged market-maker odds (Pinnacle/Circa) against retail books (FanDuel, DraftKings). Uses Bayesian modeling, XGBoost ML, and sharp money signals (RLM, Steam, CLV). Bet sizing via Multivariate Fractional Kelly Criterion (Half or Quarter Kelly) with convex optimization for correlated risks.

### Pipeline
```
Market Data (Odds API, Scrapers)
  → Sharp Signal Detection (RLM, Steam, CLV)
  → Bayesian + Monte Carlo Probability Engine
  → ML Prediction Layer (XGBoost)
  → Multivariate Kelly Criterion (Correlated Portfolio)
  → Expert Agent Review (Sequential Thinking)
  → Final Slate Recommendations
```

### Infrastructure
- **Backend:** FastAPI (Python 3.9+), Supabase/PostgreSQL (SQLite fallback), Redis cache, Celery tasks
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Query
- **Reporting:** Telegram bot (3x daily), Notion sync, Google Sheets export
- **Logging:** Loguru everywhere (`from loguru import logger`). No `print()` in services.

## Current State & Agent Coordination (Handover)

### ACTIVE STATUS (Feb 23, 2026)
- **Agent:** Gemini CLI
- **Last Sync:** Finalized merging remote branches and integrated research references.
- **Reference Updates:**
    - `prediction-models.md`: Documentation on integrated XGBoost and Bayesian models.
    - `research-sources.md`: Core bibliography and market signal theories.
- **Logic Enhancements:**
    - Updated `NBAMLPredictor` fallback model to use a composite edge calculation (Matchup ORtg/DRtg + Win Pct weighting).
- **Critical Fixes:** 
    - Fixed SQLAlchemy `InvalidRequestError` by adding `extend_existing=True` to all models.
    - Updated `NBADvPAnalyzer` to use fallback player data when API times out.
    - Fixed test suite (262/262 passing).
    - Resolved dependency conflicts in `requirements.txt` (pinned `nba_api` and `requests` loosened).
- **MCP Infrastructure:**
    - `mcp-config.json` created in root.
    - `ExpertAgent` now uses `notebooklm` for research and `sequentialthinking` for reasoning.
    - `Redis` MCP added for cache visibility.
- **Database:** `DATABASE_URL` prioritized from environment; defaults to SQLite for tests.

### NEXT TASKS
- [ ] Implement frontend dashboard for Parlay RAG pipeline.
- [ ] Enhance `ExpertAgent` to use `sheets-reporting` MCP for manual override logging.
- [ ] Monitor `NBADvPAnalyzer` API stability.

### COORDINATION RULES
1. **Always run tests** before and after changes: `cd backend && source venv/bin/activate && pytest`.
2. **Update this section** after every major implementation or commit.
3. **Avoid hardcoding:** Use `settings` from `app.config`.
4. **Communicate logic changes** here first if they impact shared services (Bayesian, Kelly, Orchestrator).

## Build, Run, and Test Commands

### Backend
```bash
pip install -r backend/requirements.txt
python3 backend/run_server.py              # FastAPI server (port 8000)
python3 backend/run_ncaab_analysis.py      # NCAAB sharp money analysis
python3 backend/run_nba_analysis.py        # NBA XGBoost predictions
python3 backend/telegram_cron.py --daemon  # 3x daily report scheduler
python3 backend/telegram_cron.py --send-now # Send report immediately
```

### Frontend
```bash
cd frontend && npm install
npm run dev       # Dev server (port 3000, proxies /api → backend:8000)
npm run build     # tsc && vite build
npm run lint      # ESLint (ts,tsx)
```

### Docker (full stack)
```bash
docker-compose up --build
# Frontend: http://localhost:3000 | Backend: http://localhost:8000 | Docs: http://localhost:8000/docs
```

### Testing
```bash
pytest backend/                                       # All tests
pytest backend/tests/path/to/test_file.py             # Single file
pytest backend/tests/path/to/test_file.py::test_func  # Single test
```
Set `PYTHONPATH=$(pwd)/backend` if module imports fail.

### Linting & Formatting
Use `black` + `isort` conventions (88-100 char lines). Use `ruff` or `flake8` for static analysis.

## Code Style

### Python
- **Imports:** Absolute imports starting with `app.` (e.g., `from app.services.bet_tracker import BetTracker`).
- **Entry scripts** (`backend/run_*.py`): Add `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` at top.
- **Config:** Load via `app.config.settings` (pydantic-settings). Use explicit `.env` path resolution: `os.path.join(os.path.dirname(__file__), "..", ".env")`.
- **Type hints:** Required on all function arguments and return types (`typing.Dict`, `List`, `Optional`, `Any`).
- **Docstrings:** Concise, on all classes and public methods. Explain *what* and *why* (business logic).
- **Async:** Use `httpx.AsyncClient` for HTTP with `timeout=15.0`. Wrap network/DB calls in `try/except`, log with `logger.error`.
- **Graceful degradation:** Services must handle unavailable APIs/DBs (e.g., `BetTracker` falls back to SQLite when Supabase is down).

### Frontend (TypeScript/React)
- Functional components with hooks. No class components.
- React Query (`@tanstack/react-query`) for server state; no Redux/Context for global state.
- Tailwind CSS only (no inline styles unless dynamic). Custom colors: `primary-*`, `accent-*`.
- Axios client in `src/utils/api.ts` unwraps `response.data` via interceptor — callers receive `T` directly.
- Path alias: `@/*` maps to `./src/*`.
- All frontend API requests must be prefixed with `/api` for Vite proxy routing.

## Betting Logic Conventions (Strict)

- **Devigging:** Always derive true probability from Pinnacle/sharp books before calculating EV. `EV = (True Probability × Decimal Odds) - 1`.
- **Odds format:** Internal calculations use Decimal odds or True Probabilities. Convert American odds via `american_to_decimal`.
- **Kelly sizing:** Always Fractional Kelly (Quarter or Half). Never Full Kelly. Cap single bet at 5% of bankroll.
- **Minimum edge thresholds:** Low confidence ≥3% (quarter-Kelly), Medium ≥5% (half-Kelly), High ≥7%, Max conviction ≥10%.
- **Stake rounding:** Round Kelly outputs to human-like denominations ($412.37 → $425) to avoid algorithmic profiling by retail books.
- **CLV tracking:** `CLV > 0` consistently = profitable strategy. `CLV < 0` = no edge.
- **Drawdown rule:** If EMDD > 30% of bankroll, reduce Kelly fraction across portfolio until EMDD < 20%.

## Sharp Money Signals
- **RLM:** ≥65% public tickets + line moves against public + ≥10% ticket/money gap.
- **Steam:** >0.5 point shift across 3+ books within 60 seconds. Only act if execution latency < 3 seconds.
- **Line Freeze:** ≥80% tickets on one side, line doesn't move → fade the public.
- **Head Fake Filter:** Sudden movement that reverses within 15 minutes in low-liquidity markets.
- **Juice Shift (Props):** Line unchanged but vig shifts ≥10 cents → sharp money signal.

## Key Services
- `bayesian.py` — Posterior probability, Monte Carlo (20k iterations), Kelly sizing
- `sharp_money_detector.py` — RLM, steam, CLV, head fake detection
- `multivariate_kelly.py` — Correlated portfolio optimization via convex optimization
- `nba_ml_predictor.py` — XGBoost predictions (optimize for probability calibration, not accuracy)
- `prop_analyzer.py` — Player prop analysis with sharp signal identification
- `sports_api.py` — Unified interface for Odds API, ESPN, scrapers
- `telegram_service.py` — Bot messaging (4096 char limit, HTML parse mode, 30 msg/sec)
- `bet_tracker.py` — Wager lifecycle management with Supabase/SQLite fallback
- `nba_stats_service.py` — nba_api integration for player stats, game logs, team advanced stats

## Anti-Patterns
- **Bare except** — Use `except Exception:` or specific types
- **print() in services** — Use `logger` from loguru
- **Full Kelly** — Always Quarter or Half Kelly
- **Type suppression** (`as any`, `@ts-ignore`) — Never
- **Schema changes** — Don't modify Supabase/SQLite schema without verifying data flow
- **Heavy deps** — Don't add `torch`, `crawl4ai` etc. unless absolutely necessary

## Operational Directives
- **Self-verify:** Before concluding a task, run `python3 backend/run_ncaab_analysis.py > /dev/null` to check for syntax/import/runtime errors.
- **Dependencies:** Add new packages to `backend/requirements.txt`.
- Subdirectory-specific guidance lives in `AGENTS.md` files under `frontend/`, `backend/app/agents/`, `backend/app/routers/`, and `backend/app/services/`.
