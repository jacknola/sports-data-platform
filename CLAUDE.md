# Sports Data Intelligence Platform – CLAUDE.md

This file documents the codebase for Claude Code and AI assistants working in this repo.

---

## Project Overview

Full-stack sports betting intelligence platform with:
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, Redis
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Recharts
- **ML/Analysis**: XGBoost, PyMC (Bayesian), Hugging Face Transformers
- **College Basketball Tool**: Sharp money detection + edge calculator for NCAAB

---

## Repo Structure

```
sports-data-platform/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── run_server.py            # Uvicorn runner
│   ├── requirements.txt
│   └── app/
│       ├── config.py            # Pydantic Settings (env vars)
│       ├── database.py          # SQLAlchemy async setup
│       ├── models/              # SQLAlchemy ORM models
│       ├── routers/             # FastAPI route handlers
│       │   ├── cbb_sharp.py     # NCAAB sharp money + edge endpoints
│       │   ├── bets.py          # Best bets (NBA ML + Bayesian)
│       │   └── ...
│       ├── services/            # Business logic
│       │   ├── cbb_edge_calculator.py  # NCAAB edge calc
│       │   ├── sharp_money_tracker.py  # Sharp signal detection
│       │   ├── bayesian.py      # Bayesian posterior probability
│       │   ├── nba_ml_predictor.py     # XGBoost NBA predictions
│       │   └── ...
│       └── agents/              # Multi-agent system
└── frontend/
    └── src/
        ├── App.tsx              # Routes
        ├── components/Layout.tsx # Sidebar nav
        ├── pages/
        │   ├── CollegeBasketball.tsx  # NCAAB sharp money page
        │   ├── Dashboard.tsx
        │   ├── Bets.tsx
        │   └── ...
        └── utils/api.ts         # Axios client → /api base
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
| `TWITTER_BEARER_TOKEN` | Twitter API v2 bearer token | Optional |
| `NOTION_API_KEY` + `NOTION_DATABASE_ID` | Notion integration | Optional |
| `OPENAI_API_KEY` | OpenAI for agent reasoning | Optional |
| `HUGGINGFACE_API_KEY` | HF inference API | Optional |

All API keys are optional – missing keys cause services to fall back to mock/demo data rather than crashing.

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

### Key services

**`cbb_edge_calculator.py`**
- Fetches odds from `basketball_ncaab` via The Odds API
- Devigging method: multiplicative (`p_true = p_implied / sum(all_implied)`)
- Consensus probability: average across sharp books (Pinnacle, BetCris, etc.)
- Edge = `true_prob - market_implied_prob_at_best_price`
- EV = `true_prob × (decimal_odds - 1) - (1 - true_prob)`
- Kelly = fractional Kelly (25% of full Kelly), capped at 10% bankroll

**`sharp_money_tracker.py`**
- Detects: book divergence, line movement, reverse line movement (RLM), spread discrepancy
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

## Git Conventions

- Feature branches: `claude/<feature-name>-<id>`
- Commit messages: imperative mood, describe the "why" not just "what"
- Push with: `git push -u origin <branch-name>`
