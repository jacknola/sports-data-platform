# Sports Data Intelligence Platform – CLAUDE.md

Full-stack sports betting intelligence platform.

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, Redis
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Recharts
- **ML**: XGBoost, Bayesian Beta-Binomial, Random Forest, Qdrant vector search
- **Reporting**: Telegram (cron + interactive bot), Slack, Google Sheets

---

## Repo Structure

```
sports-data-platform/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── run_server.py              # Uvicorn runner
│   ├── init_db_script.py          # Create DB tables
│   ├── run_ncaab_analysis.py      # NCAAB sharp money analysis (run nightly)
│   ├── run_nba_analysis.py        # NBA ML predictions on tonight's slate
│   ├── run_prop_export.py         # Player prop analysis → Google Sheets
│   ├── run_model_comparison.py    # Bayesian vs RF model comparison
│   ├── run_backfill_pipeline.py   # Full historical data backfill (start here)
│   ├── backfill_scenario.py       # Populate opp_pace/opp_def_rtg in game logs
│   ├── train_nba_model.py         # Train NBA moneyline XGBoost model
│   ├── train_ncaab_model.py       # Train NCAAB moneyline XGBoost model
│   ├── train_prop_model.py        # Train player props XGBoost model
│   ├── export_to_sheets.py        # Export picks to Google Sheets
│   ├── send_slack_report.py       # Send betting report to Slack
│   ├── telegram_cron.py           # Scheduled Telegram reports (morning/afternoon/evening)
│   ├── telegram_interactive.py    # Interactive Telegram bot
│   ├── requirements.txt
│   └── app/
│       ├── config/__init__.py     # Pydantic Settings (all env vars)
│       ├── database.py            # SQLAlchemy async setup
│       ├── models/                # ORM models (see Models section)
│       ├── routers/               # FastAPI route handlers (see API section)
│       ├── services/              # Business logic (see Services section)
│       ├── agents/                # Multi-agent orchestration
│       └── scripts/
│           ├── sync_qdrant.py     # Ingest player props into Qdrant (run after backfill)
│           └── backtest.py        # Walk-forward prop model backtest
├── frontend/
│   └── src/
│       ├── App.tsx                # Routes
│       ├── components/Layout.tsx  # Sidebar nav
│       ├── pages/
│       │   ├── Dashboard.tsx      # /
│       │   ├── Bets.tsx           # /bets
│       │   ├── CollegeBasketball.tsx  # /college-basketball
│       │   ├── Analysis.tsx       # /analysis
│       │   ├── Agents.tsx         # /agents
│       │   └── Settings.tsx       # /settings
│       └── utils/api.ts           # Axios client → /api
├── mcp-servers/
│   └── core/
│       ├── betting-analysis/      # Betting analysis MCP server
│       └── sheets-reporting/      # Google Sheets MCP server
└── docker-compose.yml             # PostgreSQL + Redis
```

---

## Running Locally

```bash
# Infrastructure
docker-compose up -d postgres redis

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in keys
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

API docs: `http://localhost:8000/docs`

---

## First-Time Setup (fresh DB)

```bash
cd backend

# 1. Create tables
python init_db_script.py

# 2. Backfill historical NBA data (games + players + game logs + scenario features)
python run_backfill_pipeline.py                        # current season
python run_backfill_pipeline.py --seasons 2024-25 2023-24  # multi-season
python run_backfill_pipeline.py --skip-qdrant          # if Qdrant not running yet

# 3. Sync player props to Qdrant (requires Qdrant running)
python -m app.scripts.sync_qdrant

# 4. Train models
python train_nba_model.py        # → models/nba_ml/moneyline_model.pkl
python train_ncaab_model.py      # → models/ncaab_ml/moneyline_model.pkl
python train_prop_model.py       # → models/prop_ml/pts_model.pkl
python train_prop_model.py --stat reb
python train_prop_model.py --stat ast
```

---

## Ongoing / Nightly

```bash
cd backend

python run_ncaab_analysis.py     # NCAAB sharp money, edge, Kelly sizing
python run_nba_analysis.py       # NBA ML predictions on tonight's slate
python run_prop_export.py        # Player prop picks → Google Sheets

python telegram_cron.py          # Scheduled: morning/afternoon/evening
python telegram_interactive.py   # Interactive bot mode
python send_slack_report.py      # One-shot Slack report
python export_to_sheets.py       # Full picks export to Sheets

# Model maintenance
python backfill_scenario.py      # Re-populate opp_pace/opp_def_rtg after new games
python run_model_comparison.py   # Compare Bayesian vs RF performance
```

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection | Yes |
| `REDIS_URL` | Redis connection | Yes |
| `THE_ODDS_API_KEY` | Live odds (The Odds API) | For live lines |
| `ODDSAPI_API_KEY` | Fallback odds | Optional |
| `BALLDONTLIE_API_KEY` | NBA player stats | Optional |
| `QDRANT_HOST` | Qdrant vector DB host | For props ML |
| `QDRANT_PORT` | Qdrant port (default 6333) | For props ML |
| `QDRANT_API_KEY` | Qdrant Cloud API key | For cloud Qdrant |
| `TELEGRAM_BOT_TOKEN` | Telegram bot | For Telegram |
| `TELEGRAM_CHAT_ID` | Telegram channel ID | For Telegram |
| `TELEGRAM_TIMEZONE` | Cron timezone (default: America/New_York) | Optional |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook | For Slack |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Google service account JSON path | For Sheets |
| `GOOGLE_SPREADSHEET_ID` | Google Sheets ID | For Sheets |
| `OPENAI_API_KEY` | OpenAI for agent reasoning | Optional |
| `GEMINI_API_KEY` | Google Gemini AI | Optional |
| `HUGGINGFACE_API_KEY` | HuggingFace inference | Optional |
| `SUPABASE_URL` + `SUPABASE_ANON_KEY` | Supabase storage | Optional |
| `NOTION_API_KEY` + `NOTION_DATABASE_ID` | Notion (stub, not implemented) | — |
| `BETTING_BANKROLL` | Starting bankroll for Kelly sizing | Optional |
| `CURRENT_SEASON` | NBA season string e.g. `2025-26` | Optional |

All keys are optional — services fall back to demo/mock data when missing.

---

## DB Models (`app/models/`)

| Model | Table | Key Fields |
|---|---|---|
| `Game` | `games` | `sport`, `home_team`, `away_team`, `game_date`, `home_score`, `away_score` |
| `Player` | `players` | `external_player_id`, `name`, `team_id`, `sport` |
| `Team` | `teams` | `external_team_id`, `name`, `sport` |
| `PlayerGameLog` | `player_game_logs` | `player_id`, `game_id`, `team_id`, `opponent_id`, `pts/reb/ast/min/pra`, `scenario` (JSON) |
| `Bet` | `bets` | `game_id`, odds fields, edge, Kelly fraction, settlement |
| `Parlay` | `parlays` | `legs` (JSON), confidence, ROI |
| `ApiCache` | `api_cache` | Key/value TTL cache for API responses |

**`PlayerGameLog.scenario` JSON** is populated by `backfill_scenario.py`:
`opp_pace`, `opp_def_rtg`, `is_home` — used as features by `train_prop_model.py`
and `app/scripts/sync_qdrant.py`.

---

## API Routers (`/api/v1/`)

| Router | Prefix | Description |
|---|---|---|
| `bets.py` | `/bets` | Best bets with edge filter |
| `cbb_sharp.py` | `/cbb` | NCAAB sharp money endpoints (see below) |
| `dvp.py` | `/dvp` | NBA Defense vs Position analysis |
| `props.py` | `/props` | Player prop analysis and best picks |
| `live_props.py` | `/props/live` | Live in-game prop engine |
| `predictions.py` | `/analyze-prop` | RF + Bayesian prop inference via Qdrant |
| `analyze.py` | `/analyze` | General analysis orchestration |
| `agents.py` | `/agents` | Multi-agent orchestration |
| `parlays.py` | `/parlays` | Parlay builder |
| `google_sheets.py` | `/sheets` | Export to Google Sheets |
| `notion.py` | `/notion` | Notion stub (not implemented) |

---

## NCAAB Sharp Money Tool

### Endpoints (`/api/v1/cbb/`)

| Endpoint | Description |
|---|---|
| `GET /cbb/summary` | Game count, EV bets, sharp signals |
| `GET /cbb/games` | All games with multi-book odds |
| `GET /cbb/edge` | Positive-EV bets (devigged true prob vs best price) |
| `GET /cbb/sharp` | Sharp money signals (RLM, book divergence, steam) |
| `GET /cbb/line-movement` | Line movement report |
| `GET /cbb/book-divergence` | Sharp vs square book probability gaps |
| `GET /cbb/best-bets` | Top bets by composite score (edge × sharp) |

### Methodology

- Devigging: multiplicative (`p_true = p_implied / Σ all_implied`)
- Edge = `true_prob − market_implied_prob_at_best_price`
- EV = `true_prob × (decimal_odds − 1) − (1 − true_prob)`
- Kelly = 25% fractional Kelly, capped at 10% bankroll
- Sharp books: Pinnacle, BetCris, Circa, BetOnline, Bookmaker, LowVig
- Square books: DraftKings, FanDuel, BetMGM, Caesars, PointsBet
- Signal score 0–4; ≥3 = strong sharp action

### Frontend (`/college-basketball`)

Three tabs: **Best Bets** | **Sharp Signals** | **Edge Calculator**

---

## Player Props ML Pipeline

```
run_backfill_pipeline.py  →  backfill_scenario.py  →  sync_qdrant.py
                                                            ↓
                                            Qdrant (nba_historical_props)
                                                            ↓
                                        inference_service.py
                                    kNN → local RF → Beta-Binomial → edge + Kelly
```

**Feature vector (10-dim — must stay in sync across all scripts):**

| # | Feature | Source |
|---|---|---|
| 1 | `usage_rate_season` | SQL window: pts/min × 36, prior games only |
| 2 | `l5_form_variance` | SQL window: VAR_SAMP of target stat, last 5 games |
| 3 | `expected_mins` | SQL window: AVG(min), prior games |
| 4 | `opp_pace` | `PlayerGameLog.scenario` → `backfill_scenario.py` |
| 5 | `opp_def_rtg` | `PlayerGameLog.scenario` → `backfill_scenario.py` |
| 6 | `def_vs_position` | `PlayerGameLog.scenario` (not yet populated) |
| 7 | `implied_team_total` | `PlayerGameLog.scenario` (not yet populated) |
| 8 | `spread` | `PlayerGameLog.scenario` (not yet populated) |
| 9 | `rest_advantage` | SQL: days since previous game (LAG) |
| 10 | `is_home` | SQL: JOIN games.home_team = teams.name |

Features 6–8 default to 0/league-averages until historical odds are stored.

---

## Key Services (`app/services/`)

### Betting Core
| Service | Purpose |
|---|---|
| `cbb_edge_calculator.py` | NCAAB devigging, edge, Kelly |
| `sharp_money_tracker.py` | NCAAB sharp signal detection (RLM, divergence) |
| `sharp_money_detector.py` | Props sharp detection (CLV, line freeze) |
| `ev_calculator.py` | EV from odds + probability |
| `bayesian.py` | Bayesian posterior with multi-agent reasoning |
| `multivariate_kelly.py` | Portfolio Kelly with correlation estimation |

### ML & Analysis
| Service | Purpose |
|---|---|
| `nba_ml_predictor.py` | NBA game predictions (loads `models/nba_ml/`) |
| `ncaab_ml_predictor.py` | NCAAB game predictions (loads `models/ncaab_ml/`) |
| `inference_service.py` | Props: Qdrant kNN → local RF → Bayesian |
| `nba_dvp_analyzer.py` | NBA Defense vs Position + pace/DRtg from nba_api |
| `ncaab_dvp_analyzer.py` | NCAAB Defense vs Position |
| `prop_analyzer.py` | Player prop full pipeline |
| `live_prop_engine.py` | Real-time in-game prop adjustment |

### Data Fetching
| Service | Purpose |
|---|---|
| `sports_api.py` | Game discovery + odds (ESPN, The Odds API, TTL cache) |
| `nba_stats_service.py` | NBA player stats (balldontlie, nba_api) |
| `ncaab_stats_service.py` | NCAAB team stats (ESPN BPI scrape) |

### Backfill
| Service | Purpose |
|---|---|
| `nba_backfill.py` | NBA game results from nba_api |
| `player_backfill.py` | NBA player game logs from nba_api |
| `ncaab_backfill.py` | NCAAB games (web scraping template — limited) |
| `player_vector_backfill.py` | Embed player logs into Qdrant |

### Reporting
| Service | Purpose |
|---|---|
| `telegram_service.py` | Telegram messages with chunking + retry |
| `report_formatter.py` | Format reports for Telegram/Slack |
| `slack_service.py` | Slack Block Kit messages via webhook |
| `google_sheets.py` | Export daily picks to Sheets tabs |
| `bet_tracker.py` | Track bets and outcomes |
| `bet_settlement.py` | Automated bet grading |

### Vector Search
| Service | Purpose |
|---|---|
| `vector_store.py` | Qdrant upsert/search |
| `similarity_search.py` | Historical game/player similarity |
| `rag_pipeline.py` | Retrieval-augmented generation |

---

## Agents (`app/agents/`)

| Agent | Purpose |
|---|---|
| `orchestrator.py` | Coordinates analysis, expert, scraping, DVP agents |
| `analysis_agent.py` | Statistical/ML analysis |
| `expert_agent.py` | Domain heuristic reasoning |
| `dvp_agent.py` | NBA DvP analysis |
| `ncaab_dvp_agent.py` | NCAAB DvP analysis |
| `scraping_agent.py` | News/injury scraping |

---

## Adding a New Sport

1. Add service in `app/services/` (follow `cbb_edge_calculator.py`)
2. Add router in `app/routers/` (follow `cbb_sharp.py`)
3. Register router in `main.py`
4. Add page in `frontend/src/pages/`
5. Add route in `App.tsx` and nav item in `Layout.tsx`

---

## Gotchas

- **Qdrant is not in docker-compose** — run separately (local or cloud). Without it, `/analyze-prop` fails; everything else works.
- **`models/` directory is gitignored** — train models locally; artifacts go in `backend/models/{nba_ml,ncaab_ml,prop_ml}/`. Re-run training scripts to regenerate.
- **`backfill_scenario.py` uses current-season stats** for all historical logs — accurate within a season, stale across seasons. Re-run at start of each season.
- **Team names in `games` table** are 2-3 letter abbreviations (e.g. `"BOS"`), same as `Team.name`. They match nba_api `TEAM_ABBREVIATION`.
- **`_parse_bookmaker_spreads()`** only parses `spreads` + `totals` markets, not `h2h`. `pinnacle_home_odds` in results = spread pricing (−110), not moneyline.
- **Notion router** returns `{"status": "success", "message": "not yet implemented"}` — stub only.
- **NCAAB backfill** (`ncaab_backfill.py`) is a scraping template. NCAAB game data must come from another source; `train_ncaab_model.py` requires games in the DB.
- **`nba_ml_predictor.py`** falls back to Pythagorean expectation when `models/nba_ml/` doesn't exist. Train with `train_nba_model.py` first.
- Frontend proxies `/api` → `http://localhost:8000` — check `vite.config.ts` if API calls fail locally.

---

## Git Conventions

- Branches: `claude/<feature>-<id>`
- Commits: imperative mood, explain the why
- Push: `git push -u origin <branch-name>`
