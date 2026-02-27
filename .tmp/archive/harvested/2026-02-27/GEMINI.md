# GEMINI.md

## Project Overview

The **Sports Data Intelligence Platform** is a sophisticated quantitative sports betting platform designed to identify +EV (Positive Expected Value) wagering opportunities using a multi-agent system. It combines sharp signal detection (Reverse Line Movement, Steam, CLV), Bayesian modeling, and machine learning to provide actionable betting insights.

### Core Technologies
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (PostgreSQL), Redis (Caching), Celery (Async Tasks).
- **Frontend:** React, TypeScript, Tailwind CSS, Vite, React Query, Recharts.
- **ML & Data:** Hugging Face Transformers, PyMC (Bayesian Modeling), XGBoost, TensorFlow, Crawl4AI.
- **Integrations:** Notion, Google Sheets, Telegram, Twitter.

## Architecture: Multi-Agent System

The platform utilizes an **Orchestrator Agent** to coordinate specialized agents:
- **OddsAgent:** Aggregates and devigs odds from sharp (Pinnacle/Circa) and retail books.
- **AnalysisAgent:** Performs deep value analysis and Bayesian probability updates.
- **TwitterAgent:** Monitors Twitter sentiment for teams and players.
- **ExpertAgent:** Provides high-level recommendations using sequential thinking.
- **ScrapingAgent:** Extracts real-time news and stats using AI-enhanced scraping.
- **DvPAgent / NCAABDvPAgent:** Specialized agents for NBA and NCAAB efficiency analysis.

## Core Betting Logic

Adherence to these mathematical principles is mandatory across the codebase:
- **Devigging:** Uses the multiplicative method to derive true probabilities from sharp markets.
- **Expected Value (EV):** Calculated as `(True Probability × Decimal Odds) - 1`.
- **Kelly Criterion:**
    - **Default Scaling:** Half-Kelly (0.5) or Quarter-Kelly (0.25).
    - **Single Bet Cap:** 5% of bankroll.
    - **Total Exposure Cap:** 25% of bankroll.
    - **Rounding:** Rounds to the nearest 0.25% (human-like sizing) to avoid sportsbook fingerprinting.
- **Sharp Signals:** Tracks Reverse Line Movement (RLM) and Steam Moves as primary indicators of sharp intent.

## Building and Running

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL & Redis
- Docker (optional)

### Key Commands

| Task | Command | Directory |
| :--- | :--- | :--- |
| **Initial Setup** | `./setup.sh` | Root |
| **Backend Dev** | `python run_server.py` | `backend/` |
| **Frontend Dev** | `npm run dev` | `frontend/` |
| **Run Migrations**| `alembic upgrade head` | `backend/` |
| **Celery Worker** | `celery -A app.celery_app worker --loglevel=info` | `backend/` |
| **Run Tests** | `pytest` | `backend/` |
| **Linting** | `ruff check .` (Py) / `npm run lint` (TS) | `backend/` or `frontend/` |

## Development Conventions

- **Imports:** Always use absolute imports starting with `app.` (e.g., `from app.core.betting import ...`).
- **Logging:** Use `loguru` exclusively. No `print()` statements.
- **Configuration:** Managed via Pydantic `BaseSettings` in `backend/app/config`.
- **API Style:** RESTful endpoints using FastAPI's dependency injection and Pydantic models.
- **Frontend State:** Use `React Query` (TanStack Query) for all server state and caching.
- **Database:** SQLAlchemy 2.0+ with async support.

## MCP Integration

The project integrates several Model Context Protocol (MCP) servers for enhanced capabilities:
- **betting-analysis:** Specialized tools for betting calculations.
- **sheets-reporting:** Automated Google Sheets syncing.
- **notebooklm:** Research and knowledge retrieval.
- **sequentialthinking:** Enhanced reasoning for complex analysis.
- **redis:** Direct cache inspection and management.

Refer to `mcp-config.json` for server configurations.
