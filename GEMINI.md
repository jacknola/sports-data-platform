# GEMINI.md - Context Summary

## Mission
Quantitative sports betting platform for identifying +EV opportunities via sharp signals (RLM, Steam), Bayesian updates, and ML models.

## Tech Stack
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (PostgreSQL), Redis, Celery.
- **Frontend:** React, TypeScript, Tailwind, Vite, React Query.
- **ML/Agents:** Hugging Face, PyMC, XGBoost. Multi-agent system (Orchestrator, Odds, Analysis, Twitter, Expert, Scraping, DvP).
- **Integrations:** Notion, Google Sheets, Telegram, Twitter. MCP (betting-analysis, sheets-reporting, notebooklm, sequentialthinking).

## Core Rules & Conventions
- **Betting Logic:** Devig sharp markets (multiplicative). EV = (True Prob * Decimal) - 1. Kelly sizing (Half/Quarter, 5% single/25% total cap).
- **Code:** Absolute imports (`app.`), `loguru` (no print), Pydantic `BaseSettings`. RESTful FastAPI, TanStack Query for frontend state.
- **Commands:** `./setup.sh`, `python run_server.py`, `npm run dev`, `pytest`, `ruff check .`

## Current Session State & Guidelines
- **Directive:** Prune context often; save only high-level summaries here.
- **Recent Updates:** 
  - Added dedicated 'ML Predictions' Google Sheets export tab for raw XGBoost model projections (Win Prob, Proj Total/Spread, Off/Def Ratings).
  - Ensured prediction pipeline gracefully falls back to database historical data/scraped data when live odds APIs are exhausted.
  - Fixed duplicate index errors in `conftest.py` SQLite testing by removing redundant `index=True` on unique/primary columns in SQLAlchemy models (`Bet`, `Game`, `HistoricalGameLine`).
  - Fixed Bayesian analyzer tests failing due to mismatched method signatures and filtered zero-adjustments.