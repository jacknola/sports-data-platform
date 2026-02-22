# CLAUDE.md - Sports Data Intelligence Platform

## Project Overview

A comprehensive sports betting intelligence platform with multi-agent architecture, Bayesian modeling, ML predictions, and automated data syncing. Built with FastAPI (backend) and React/TypeScript (frontend).

## Architecture

```
backend/
  app/
    agents/          # Multi-agent system (BaseAgent ABC pattern)
      base_agent.py  # Abstract base class — all agents extend this
      odds_agent.py  # Odds fetching and value detection
      analysis_agent.py  # Bayesian/ML analysis orchestration
      expert_agent.py    # Sequential thinking expert decisions
      twitter_agent.py   # Twitter sentiment analysis
      scraping_agent.py  # Web scraping sports data
      dvp_agent.py       # NBA DvP +EV prop analyzer agent
      orchestrator.py    # Coordinates all agents
    config/          # Configuration data files
      nba_dvp_slate.json  # Today's NBA matchup slate (spreads, O/U)
    memory/          # Agent learning and memory system
      agent_memory.py
    models/          # SQLAlchemy ORM models (Bet, Game, Team, Player)
    routers/         # FastAPI route handlers
      agents.py, bets.py, analyze.py, odds.py, sentiment.py,
      predictions.py, notion.py, google_sheets.py, dvp.py
    services/        # Business logic layer
      bayesian.py           # Bayesian posterior probability + Monte Carlo
      ml_service.py         # HuggingFace transformer models
      nba_ml_predictor.py   # XGBoost NBA game predictions
      nba_dvp_analyzer.py   # DvP matchup analysis + prop projections
      sports_api.py         # External sports API aggregation
      sequential_thinking.py  # Expert reasoning service
      cache.py              # Redis cache (singleton)
    config.py        # Pydantic settings (env vars, API keys)
    database.py      # SQLAlchemy engine + session setup
  main.py            # FastAPI app entry point
  requirements.txt   # Python dependencies
frontend/
  src/
    components/      # React UI components
    pages/           # Dashboard, Bets, Analysis, Agents, Settings
    utils/api.ts     # HTTP client
```

## Key Patterns

- **BaseAgent ABC**: All agents inherit from `BaseAgent` and implement `execute()` and `learn_from_mistake()`. Agents track execution history and mistakes for adaptive learning.
- **Service Layer**: Heavy logic lives in `services/`. Agents and routers call services.
- **Router Layer**: FastAPI routers at `/api/v1/*`. Each router is registered in `main.py`.
- **Configuration**: Pydantic `Settings` in `config.py`, reads from `.env`.
- **Orchestrator**: `OrchestratorAgent` coordinates multi-agent workflows.

## NBA DvP +EV Analyzer

### What it does
Identifies +EV (positive expected value) NBA player prop bets using:
- **Defense vs. Position (DvP)** metrics — how many points/rebounds/assists each team allows to each position
- **Pace multipliers** — pace-up/pace-down adjustments based on game tempo
- **Vegas Implied Totals** — derived from spread + over/under to estimate game scoring environment
- **Rolling player baselines** — recent-game averages (configurable window, default 15 games)

### Files
| File | Role |
|------|------|
| `services/nba_dvp_analyzer.py` | Core `NBADvPAnalyzer` class — data fetching, DvP math, projections |
| `agents/dvp_agent.py` | `DvPAgent` extending `BaseAgent` — task routing, error handling, learning |
| `routers/dvp.py` | REST API endpoints for DvP analysis |
| `config/nba_dvp_slate.json` | Today's game slate with spreads and over/unders |

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/dvp/analysis` | Full DvP analysis for today's slate |
| `POST` | `/api/v1/dvp/analysis` | Custom analysis with slate override |
| `GET` | `/api/v1/dvp/implied-totals` | Implied team totals from spread + O/U |
| `GET` | `/api/v1/dvp/player/{name}` | Single player projection |
| `GET` | `/api/v1/dvp/status` | DvP agent execution stats |

### Query Parameters
- `high_value_only=true` — filter to HIGH VALUE OVER/UNDER plays only
- `num_recent=15` — rolling average game window
- `stat=PTS` — stat category (PTS, REB, AST, PTS+REB+AST)

### Data Sources
- **Primary**: `nba_api` (swar/nba_api) — maps NBA.com endpoints for player stats, team stats, pace
- **Fallback**: Built-in approximated data when `nba_api` is unavailable or rate-limited
- **Slate**: JSON config with today's matchups, spreads, and over/unders

### DvP Math
```
implied_team_total = (O/U +/- |spread|) / 2
pace_multiplier = (team_pace + opp_pace) / 2 / league_avg_pace
dvp_factor = opp_dvp_allowed / league_avg_dvp
environment_factor = implied_total / season_avg_total
matchup_modifier = dvp_factor * environment_factor * pace_multiplier
projected_line = season_avg * matchup_modifier
```

### Flagging Thresholds
- `> +12%` above baseline → **HIGH VALUE OVER**
- `< -12%` below baseline → **HIGH VALUE UNDER**
- `+5% to +12%` → LEAN OVER
- `-5% to -12%` → LEAN UNDER

### Usage Example
```python
from app.services.nba_dvp_analyzer import NBADvPAnalyzer

analyzer = NBADvPAnalyzer()
df = analyzer.run_analysis()  # uses config/nba_dvp_slate.json
high_value = analyzer.get_high_value_plays(df)
print(high_value)
```

## Development Workflow

1. **Adding new services**: Create in `backend/app/services/`, import in relevant agent or router
2. **Adding new agents**: Extend `BaseAgent` in `backend/app/agents/`, register in orchestrator
3. **Adding new routes**: Create router in `backend/app/routers/`, register in `main.py`
4. **Updating slate**: Edit `backend/app/config/nba_dvp_slate.json` with today's lines

## Running

```bash
# Backend
cd backend && python run_server.py

# Frontend
cd frontend && npm start

# Docker (full stack)
docker-compose up
```

## Environment Variables

See `backend/app/config.py` for full list. Key ones:
- `DATABASE_URL`, `REDIS_URL` — infrastructure
- `THE_ODDS_API_KEY` — live odds integration
- `SPORTSRADAR_API_KEY`, `ODDSAPI_API_KEY` — sports data
- `NBA_MODEL_PATH` — path to trained XGBoost models

## Dependencies

Core: FastAPI, SQLAlchemy, pandas, numpy, scipy, scikit-learn, xgboost, nba_api
See `backend/requirements.txt` for complete list.
