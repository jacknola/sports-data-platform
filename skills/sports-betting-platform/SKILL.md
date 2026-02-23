---
name: sports-betting-platform
description: >
  Development skill for the Sports Data Intelligence Platform — quantitative sports betting
  with Bayesian modeling, XGBoost ML, sharp money detection, and multi-agent analysis.
  MCP integrations: GitHub, Playwright, Filesystem, Fetch, Postgres, Brave Search, Memory,
  Sequential Thinking, Puppeteer, Google Maps, Slack, Google Sheets.
  Use when: (1) Running or modifying NCAAB/NBA analysis pipelines, (2) Calculating EV, devigging
  Pinnacle odds, or Kelly sizing, (3) Working with the 7-agent system (odds, analysis, expert,
  scraping, DVP, Twitter, orchestrator), (4) Adding games to slates or managing Telegram reports,
  (5) Working with any of the 13 MCP servers, (6) Modifying FastAPI endpoints or services,
  (7) Implementing sharp money signals (RLM, steam, CLV, line freeze, head fakes).
---

# Sports Data Intelligence Platform — Development Skill

## Analysis Pipeline
```
Market Data (Odds API) → Sharp Signal Detection (RLM, Steam, CLV)
→ Bayesian + Monte Carlo → ML Predictions (XGBoost)
→ Multivariate Kelly → Agent Review → Final Slate
```

## Quick Commands
- NCAAB analysis: `python3 backend/run_ncaab_analysis.py`
- NBA analysis: `python3 backend/run_nba_analysis.py`
- FastAPI server: `python3 backend/run_server.py`
- Telegram daemon: `python3 backend/telegram_cron.py --daemon`
- Send report now: `python3 backend/telegram_cron.py --send-now`
- Tests: `PYTHONPATH=$(pwd)/backend pytest backend/`
- Infra: `docker compose up -d`

## MCP Servers
13 servers configured in `sports-data-platform.code-workspace`. See [references/mcp-servers.md](references/mcp-servers.md) for full details.

**Quick lookup:**
- Repo automation → GitHub
- Browser automation → Playwright / Puppeteer
- File operations → Filesystem
- URL fetching → Fetch
- Database queries → Postgres
- Web search → Brave Search
- Knowledge graph → Memory
- Reasoning → Sequential Thinking
- Notifications → Slack
- Spreadsheets → Google Sheets

## EV Calculation
See [references/ev-kelly.md](references/ev-kelly.md) for devigging formulas, EV computation, Kelly fraction sizing, and minimum edge thresholds.

## Sharp Money Signals
See [references/sharp-signals.md](references/sharp-signals.md) for RLM, steam moves, line freeze, head fake detection, and CLV tracking.

## Code Patterns

### New service
1. Create `backend/app/services/new_service.py`
2. Use `from loguru import logger` (never `print()`)
3. Use `httpx.AsyncClient` with `timeout=15.0` for external APIs
4. Wrap network/DB calls in try/except, log errors with `logger.error`
5. Add to `backend/app/services/__init__.py`

### New agent
1. Create `backend/app/agents/new_agent.py`, extend `base_agent.py`
2. Wire into `orchestrator.py`
3. Add endpoint in `backend/app/routers/agents.py`

### New game to slate
Append to `TONIGHT_GAMES` in `backend/run_ncaab_analysis.py`:
```python
{
    'game_id': 'NCAAB_YYYYMMDD_NN',
    'home': 'Team', 'away': 'Team',
    'conference': 'Big 12',
    'pinnacle_home_odds': -108, 'pinnacle_away_odds': -108,
    'retail_home_odds': -110, 'retail_away_odds': -110,
    'spread': -3.5, 'open_spread': -2.5,
    'home_ticket_pct': 0.71, 'home_money_pct': 0.44,
    'model_home_prob': 0.567,
    'notes': 'RLM detected: 71% tickets on home, line moved away to -3',
},
```

## Service Map
- `backend/app/services/bayesian.py` — Posterior prob, Monte Carlo, Kelly
- `backend/app/services/sharp_money_detector.py` — RLM, steam, CLV, head fake
- `backend/app/services/multivariate_kelly.py` — Correlated portfolio optimization
- `backend/app/services/nba_ml_predictor.py` — XGBoost predictions
- `backend/app/services/telegram_service.py` — Bot messaging

## Style Rules
- Python 3.9+ type hints (`Dict`, `List`, `Optional`)
- Absolute imports: `from app.services.x import X`
- Loguru only: `from loguru import logger`
- No `print()` in services
- Graceful degradation on API/DB failures
- Convert American odds → Decimal before calculation
- Round Kelly stakes to human-like amounts ($412 → $400)
- Always use Half or Quarter Kelly, never full
