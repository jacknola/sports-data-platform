# Sports Data Intelligence Platform - Agent Instructions (AGENTS.md)

This document contains essential context, build/test commands, and code style guidelines for AI coding agents operating within this repository. It supplements `CLAUDE.md` and provides strict operational directives.

## 1. Project Context & Architecture
- **Goal:** Quantitative sports betting platform using Bayesian modeling, ML (XGBoost), and sharp money signals (RLM, Steam).
- **Core Principle:** Identify +EV wagers by comparing devigged market-maker odds (Pinnacle/Circa) against retail books (FanDuel, DraftKings).
- **Sizing:** Use Multivariate Fractional Kelly Criterion (Half or Quarter Kelly) via convex optimization to manage bankroll and correlated risks.
- **Infrastructure:** FastAPI backend, Supabase DB (with local SQLite fallback), Telegram bot for reporting, Loguru for logging, Pytest for testing.

## 2. Build, Run, and Test Commands

### Core Execution
- **Run NCAAB Analysis:** `python3 backend/run_ncaab_analysis.py`
- **Run Telegram Daemon:** `python3 backend/telegram_cron.py --daemon`
- **Send Ad-Hoc Report:** `python3 backend/telegram_cron.py --send-now`

### Testing
- **Run all tests:** `pytest backend/`
- **Run a single test file:** `pytest backend/tests/path/to/test_file.py`
- **Run a specific test function:** `pytest backend/tests/path/to/test_file.py::test_function_name`
- *Note:* Ensure you set `PYTHONPATH=$(pwd)/backend` if tests fail to resolve module imports.

### Linting & Formatting
*(While strict linters may not be globally enforced in CI yet, adhere to these standards)*
- **Formatting:** Use `black` and `isort` conventions. Maximum line length is usually 88-100 characters.
- **Linting:** Use `ruff` or `flake8` for basic static analysis to catch unused imports/variables.

### Dependencies
- **Install dependencies:** `pip install -r backend/requirements.txt`
- Avoid adding heavy ML dependencies (like `torch` or `crawl4ai`) unless absolutely necessary, to keep deployment and inference fast. Add new dependencies to `backend/requirements.txt`.

## 3. Code Style & Engineering Guidelines

### General Python Standards
- **Python Version:** 3.9+ syntax is expected.
- **Type Hinting:** Use strict type hints (`typing.Dict`, `List`, `Optional`, `Any`) for all function arguments and return types. 
- **Docstrings:** Provide concise docstrings for all classes and public methods explaining *what* it does and *why* (business logic).

### Imports & Path Resolution
- **Internal Imports:** Use absolute imports starting with `app.` (e.g., `from app.services.bet_tracker import BetTracker`).
- **Script Execution:** For root executable scripts (`backend/run_*.py`), include the following at the top to ensure module resolution:
  ```python
  import sys
  import os
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  ```
- **Environment Variables:** Load variables via `app.config.settings` (powered by `pydantic-settings`). Always use explicit path resolution for `.env` files: `os.path.join(os.path.dirname(__file__), "..", ".env")`. Provide sensible defaults for local development.

### Logging & Output
- **Loguru:** Use `loguru` for all logging (`from loguru import logger`).
- **No Prints:** Do not use standard `print()` statements in service or library code. Use `logger.info`, `logger.warning`, `logger.error`. `print()` is only allowed in CLI output scripts (like `run_ncaab_analysis.py`) for user-facing formatting.

### Error Handling & Resilience
- **Graceful Degradation:** Services should gracefully degrade if a third-party API or database is unavailable. Example: `BetTracker` falling back to local SQLite if Supabase connection fails.
- **API Requests:** Use `httpx.AsyncClient` for async HTTP requests (e.g. Odds API, scraping) and include reasonable timeouts (`timeout=15.0`).
- **Catching Exceptions:** Wrap network calls and DB queries in `try/except` blocks. Log the exact error with `logger.error` rather than crashing the daemon or cron job.

### Betting Logic Conventions (Strict)
- **Odds Format:** Calculations expect Decimal odds or True Probabilities. When parsing American odds, explicitly convert them using `american_to_decimal`.
- **Devigging:** Always derive true probability from Pinnacle/sharp books using a devigging formula before calculating Expected Value (EV). EV is calculated as `(True Probability × Decimal Odds) - 1`.
- **Stake Denominations:** Round calculated Kelly bet fractions to human-readable increments (e.g., $412.37 → $425) to avoid algorithmic behavioral profiling by retail sportsbooks.

## 4. Operational Directives for Agents
- **Do not introduce breaking schema changes** to Supabase or SQLite without verifying existing data flow.
- **Do not modify `CLAUDE.md`** unless specifically requested by the user.
- **Self-Verification:** Before concluding a task, run the main execution scripts (e.g., `python3 backend/run_ncaab_analysis.py > /dev/null`) to verify that your changes did not introduce syntax errors, import errors, or runtime crashes.



## 5. Entry Points
| Script | Purpose |
|--------|---------|
| `backend/run_ncaab_analysis.py` | NCAAB sharp money analysis (main) |
| `backend/run_nba_analysis.py` | NBA XGBoost predictions |
| `backend/run_server.py` | FastAPI server (uvicorn wrapper) |
| `backend/telegram_cron.py --daemon` | 3x daily betting report scheduler |
| `backend/telegram_cron.py --send-now` | Send report immediately |

## 6. Directory Structure
```
backend/
├── app/
│   ├── agents/      # Multi-agent system (7 agents)
│   ├── routers/    # FastAPI endpoints (11 routers)
│   ├── services/   # Core business logic (20 services)
│   ├── models/     # SQLAlchemy models
│   └── core/       # Core utilities
├── run_*.py        # Entry scripts
└── telegram_cron.py
frontend/
├── src/
│   ├── components/ # React components
│   ├── pages/      # Page components
│   └── utils/     # API client
```

## 7. Anti-Patterns (THIS PROJECT)
- **Bare except** — Use `except Exception:` or specific types
- **print() in services** — Use `logger` from loguru
- **Full Kelly** — Always use Quarter or Half Kelly
- **Type suppression** (`as any`, `@ts-ignore`) — Never
- **Schema changes** — Don't modify without verifying data flow

## 8. Missing Infrastructure (Non-Standard)
- No `.env.example` file
- No `tests/` directory (tests are flat files in `backend/`)
- No `pytest.ini` or `conftest.py`
- No GitHub Actions CI/CD
- No Pydantic request models (uses `Dict[str, Any]`)

## 9. Key Dependencies
```
# Core
fastapi, uvicorn, pydantic, sqlalchemy
# ML/Stats
xgboost, scikit-learn, pandas, numpy, pymc
# Data
httpx, requests, beautifulsoup4
# Integrations
telegram, notion-client, gspread, tweepy
# Infra
loguru, redis, celery, postgres
```
