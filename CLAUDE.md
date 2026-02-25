# Sports Data Intelligence Platform – CLAUDE.md

This file documents the codebase for Claude Code and AI assistants working in this repo.

---

## Project Overview

Full-stack sports betting intelligence platform with:
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, Redis
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Recharts
- **ML/Analysis**: XGBoost, PyMC (Bayesian), Hugging Face Transformers
- **Telegram Pipeline**: Automated bet reports via cron (morning/afternoon/evening)
- **College Basketball Tool**: Sharp money detection + edge calculator for NCAAB

---

## Repo Structure

```
sports-data-platform/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── run_server.py            # Uvicorn runner
│   ├── run_ncaab_analysis.py    # NCAAB sharp money analysis script
│   ├── run_nba_analysis.py      # NBA analysis script
│   ├── telegram_cron.py         # Scheduled Telegram report runner
│   ├── telegram_interactive.py  # Interactive Telegram bot
│   ├── requirements.txt
│   └── app/
│       ├── config/__init__.py   # Pydantic Settings (env vars)
│       ├── database.py          # SQLAlchemy async setup
│       ├── models/              # SQLAlchemy ORM models
│       ├── routers/             # FastAPI route handlers (see API section)
│       ├── services/            # Business logic (see Services section)
│       └── agents/              # Multi-agent system (see Agents section)
├── frontend/
│   └── src/
│       ├── App.tsx              # Routes
│       ├── components/Layout.tsx # Sidebar nav
│       ├── pages/
│       │   ├── CollegeBasketball.tsx  # NCAAB sharp money page
│       │   ├── Dashboard.tsx
│       │   ├── Bets.tsx
│       │   ├── Analysis.tsx
│       │   ├── Agents.tsx
│       │   └── Settings.tsx
│       └── utils/api.ts         # Axios client → /api base
├── mcp-servers/
│   ├── core/                    # Our MCP servers
│   │   ├── betting-analysis/    # Betting analysis MCP server
│   │   └── sheets-reporting/    # Google Sheets MCP server
│   ├── examples/                # External: MCP examples repo (gitignored)
│   └── postgres/                # External: Postgres MCP server (gitignored)
└── docker-compose.yml           # PostgreSQL + Redis
```

---

## Running Locally

### Prerequisites
- Python 3.11+, Node.js 18+, Docker (for PostgreSQL + Redis)

### Start infrastructure
```bash
docker-compose up -d postgres redis
```

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # starts on http://localhost:5173
```

### Run NCAAB analysis
```bash
cd backend
python run_ncaab_analysis.py
```

### Run Telegram reports
```bash
cd backend
python telegram_cron.py          # scheduled cron runner
python telegram_interactive.py   # interactive bot mode
```

### Other backend scripts
```bash
cd backend
python train_nba_model.py          # train/retrain XGBoost NBA model → backend/models/nba_ml/
python run_backfill_pipeline.py    # full historical data backfill
python run_ncaab_backfill.py       # NCAAB historical data backfill
python run_model_comparison.py     # compare ML model performance
python export_to_sheets.py         # export data to Google Sheets
python run_prop_export.py          # export player props data
python send_slack_report.py        # send betting report to Slack
```

API docs available at `http://localhost:8000/docs`.

---

## Environment Variables (`.env`)

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `THE_ODDS_API_KEY` | The Odds API key for live lines | For live data |
| `ODDSAPI_API_KEY` | Fallback odds API key | Optional |
| `SPORTSRADAR_API_KEY` | SportsRadar key | Optional |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for reports | For Telegram |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel ID | For Telegram |
| `GEMINI_API_KEY` | Google Gemini for analysis | Optional |
| `SUPABASE_URL` + `SUPABASE_ANON_KEY` | Supabase for data storage | Optional |
| `TWITTER_BEARER_TOKEN` | Twitter API v2 bearer token | Optional |
| `NOTION_API_KEY` + `NOTION_DATABASE_ID` | Notion integration | Optional |
| `OPENAI_API_KEY` | OpenAI for agent reasoning | Optional |
| `HUGGINGFACE_API_KEY` | HF inference API | Optional |
| `GOOGLE_SERVICE_ACCOUNT_PATH` + `GOOGLE_SPREADSHEET_ID` | Google Sheets export | Optional |
| `SPORTS_GAME_ODDS_API_KEY` | SportsGameOdds API key | Optional |
| `QDRANT_HOST` + `QDRANT_PORT` + `QDRANT_API_KEY` | Qdrant vector DB connection | For vector search |
| `SLACK_WEBHOOK_URL` | Slack webhook for reports | Optional |

All API keys are optional – missing keys cause services to fall back to mock/demo data rather than crashing.

---

## API Routers (`/api/v1/`)

| Router | Prefix | Description |
|---|---|---|
| `bets.py` | `/bets` | Best bets (NBA ML + Bayesian) |
| `cbb_sharp.py` | `/cbb` | NCAAB sharp money + edge endpoints |
| `odds.py` | `/odds` | Live odds fetching |
| `props.py` | `/props` | Player prop analysis |
| `live_props.py` | `/live-props` | Live in-game prop engine |
| `dvp.py` | `/dvp` | Defense vs Position analysis |
| `parlays.py` | `/parlays` | Parlay builder and tracking |
| `analyze.py` | `/analyze` | General analysis endpoints |
| `predictions.py` | `/predictions` | ML predictions |
| `agents.py` | `/agents` | Multi-agent orchestration |
| `google_sheets.py` | `/sheets` | Google Sheets export |
| `sentiment.py` | `/sentiment` | Twitter sentiment analysis |
| `notion.py` | `/notion` | Notion integration |

---

## Key Services

### Betting Core
| Service | Purpose |
|---|---|
| `cbb_edge_calculator.py` | NCAAB devigging, edge calc, Kelly sizing |
| `sharp_money_tracker.py` | Sharp signal detection (RLM, book divergence) |
| `sharp_money_detector.py` | Lightweight sharp money detection |
| `ev_calculator.py` | Expected value calculations |
| `bayesian.py` | Bayesian posterior probability |
| `multivariate_kelly.py` | Multivariate Kelly criterion |

### ML & Analysis
| Service | Purpose |
|---|---|
| `nba_ml_predictor.py` | XGBoost NBA game predictions |
| `nba_dvp_analyzer.py` | NBA Defense vs Position analysis |
| `ncaab_dvp_analyzer.py` | NCAAB Defense vs Position analysis |
| `ml_service.py` | General ML inference service |
| `prop_analyzer.py` | Player prop analysis |
| `live_prop_engine.py` | Live in-game prop engine |

### Telegram Pipeline
| Service | Purpose |
|---|---|
| `telegram_service.py` | Send reports via Telegram bot API |
| `report_formatter.py` | Format betting reports for Telegram |
| `bet_tracker.py` | Track placed bets and outcomes |
| `bet_settlement.py` | Automated bet grading/settlement |

### Data & Integration
| Service | Purpose |
|---|---|
| `sports_api.py` | Sports data API client |
| `sports_game_odds.py` | SportsGameOdds API client |
| `google_sheets.py` | Google Sheets read/write |
| `supabase_service.py` | Supabase data storage |
| `gemini_service.py` | Google Gemini AI integration |
| `twitter_analyzer.py` | Twitter sentiment analysis |
| `slack_service.py` | Slack notifications |
| `web_scraper.py` | Web scraping utilities |

### Vector Search & RAG
| Service | Purpose |
|---|---|
| `vector_store.py` | Qdrant vector store operations |
| `similarity_search.py` | Find similar historical games/players |
| `rag_pipeline.py` | Retrieval-augmented generation pipeline |
| `ncaab_vector_backfill.py` | NCAAB vector embedding backfill |
| `player_vector_backfill.py` | Player vector embedding backfill |
| `feature_engineering.py` | ML feature extraction and transformation |

### Backfill & Model Training
| Service | Purpose |
|---|---|
| `nba_backfill.py` | NBA historical data backfill |
| `ncaab_backfill.py` | NCAAB historical data backfill |
| `player_backfill.py` | Player historical data backfill |
| `nba_stats_service.py` | NBA stats data fetching |
| `ncaab_stats_service.py` | NCAAB stats data fetching |
| `random_forest_model.py` | Random Forest model (alternative to XGBoost) |
| `evaluation_metrics.py` | Model evaluation and scoring |
| `game_profiler.py` | Game feature profiling |
| `player_profiler.py` | Player feature profiling |

### Agents (`backend/app/agents/`)
| Agent | Purpose |
|---|---|
| `orchestrator.py` | Coordinates multi-agent workflows |
| `base_agent.py` | Base class for all agents |
| `analysis_agent.py` | Analysis orchestration |
| `odds_agent.py` | Odds data fetching |
| `dvp_agent.py` | DvP analysis |
| `expert_agent.py` | Expert reasoning |
| `scraping_agent.py` | Web scraping |
| `twitter_agent.py` | Twitter data |
| `ncaab_dvp_agent.py` | NCAAB Defense vs Position agent |

---

## College Basketball Sharp Money Tool

### Backend endpoints (`/api/v1/cbb/`)

| Endpoint | Description |
|---|---|
| `GET /cbb/summary` | Dashboard summary: game count, EV bets, signals |
| `GET /cbb/games` | All NCAAB games with current multi-book odds |
| `GET /cbb/edge` | Positive-EV bets (devigged true prob vs best market price) |
| `GET /cbb/sharp` | Sharp money signals (RLM, book divergence, line movement) |
| `GET /cbb/line-movement` | Line movement report for all active games |
| `GET /cbb/book-divergence` | Sharp book vs square book probability gaps |
| `GET /cbb/best-bets` | Top bets ranked by composite score (edge × sharp score) |

### Key methodology

**`cbb_edge_calculator.py`**
- Devigging: multiplicative (`p_true = p_implied / sum(all_implied)`)
- Consensus probability: average across sharp books (Pinnacle, BetCris, etc.)
- Edge = `true_prob - market_implied_prob_at_best_price`
- EV = `true_prob × (decimal_odds - 1) - (1 - true_prob)`
- Kelly = fractional Kelly (25% of full Kelly), capped at 10% bankroll

**`sharp_money_tracker.py`**
- Signals: book divergence, line movement, reverse line movement (RLM), spread discrepancy
- Sharp books: `pinnacle, betcris, circa, betonlineag, bookmaker, lowvig`
- Square books: `draftkings, fanduel, betmgm, caesars, pointsbet`
- Scores signals 0–4; 3+ = strong sharp action

### Frontend

The `CollegeBasketball` page (`/college-basketball`) has three tabs:
1. **Best Bets** – Combined edge + sharp ranking table
2. **Sharp Signals** – Card grid of sharp signal details with expandable info
3. **Edge Calculator** – Raw edge calculation table per market/side

---

## Adding New Sports

1. Add a service in `backend/app/services/` following `cbb_edge_calculator.py`
2. Add a router in `backend/app/routers/` following `cbb_sharp.py`
3. Register the router in `backend/main.py`
4. Add a frontend page in `frontend/src/pages/`
5. Add the route in `frontend/src/App.tsx` and nav item in `frontend/src/components/Layout.tsx`

---

## Testing

```bash
# Backend
cd backend
pytest -v

# Frontend type-check
cd frontend
npm run build   # catches TypeScript errors
```

---

## Gotchas

- All API keys are optional — services fall back to mock/demo data when keys are missing (won't crash)
- Qdrant vector DB is required for vector search features but is **not** in the default `docker-compose.yml` — run it separately or disable RAG features
- `backend/models/nba_ml/` contains trained model artifacts — do not delete; re-run `train_nba_model.py` to regenerate
- Frontend proxies `/api` → backend — if API calls fail locally, check `vite.config.ts` proxy config
- `backend/venv/` is gitignored but required; recreate with `python -m venv venv && pip install -r requirements.txt`
- The `sports_api.py` service will use demo/mock data if no API keys are set — useful for local dev without keys

---

## Git Conventions

- Feature branches: `claude/<feature-name>-<id>`
- Commit messages: imperative mood, describe the "why" not just "what"
- Push with: `git push -u origin <branch-name>`
