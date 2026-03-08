# Sports Data Intelligence Platform

A quantitative sports betting intelligence platform that identifies +EV wagers by comparing devigged market-maker odds (Pinnacle) against the primary retail book (FanDuel). Uses Bayesian modeling, XGBoost ML, and sharp money signals. Bet sizing via Fractional Kelly Criterion with a focus on win probability over raw odds hunting.

## Features

- 🎯 **+EV Prop Analysis**: Identifies positive-EV player props using Bayesian posteriors, PropProbabilityModel projections, and EVCalculator hit-rate modeling
- 📐 **Win Probability First**: All picks display the model's true win probability — the primary decision metric when betting a single book (FanDuel)
- 🧠 **Sharp Signal Detection**: Line movement, juice shift, and CLV tracking via `LineMovementAnalyzer`
- 🤖 **XGBoost ML Predictions**: NBA and NCAAB game outcome predictions using `NBAMLPredictor` / `NCAABMLPredictor`
- 📊 **Bayesian Models**: Posterior probability computation with Fractional Kelly sizing (Quarter/Half Kelly)
- 🎲 **Parlay Engine**: Generates SGP and cross-game parlays from today's +EV picks with team-diversity enforcement and a −200 odds floor
- 📑 **Google Sheets Export**: Daily prop picks, game bets, parlays, and bet-slip — all auto-formatted and pushed to Sheets
- 📱 **React Dashboard**: Real-time frontend with bet tracking, win probability display, and parlay RAG insights
- 📲 **Telegram Reports**: 3× daily automated reports via Telegram bot

## Architecture

```
The Odds API + ESPN
  ↓
PropProbabilityModel + Bayesian Posterior
  ↓
EVCalculator (L5/L10/L20 game logs)
  ↓
Parlay Engine (team-diverse, ≥ −200 odds)
  ↓
FractionalKelly sizing → Google Sheets / Bet Tracker
```

## Tech Stack

### Backend
- **FastAPI** (Python 3.9+) — REST API
- **SQLAlchemy** — ORM; PostgreSQL primary, SQLite fallback for local dev
- **Supabase** — hosted Postgres + realtime (with automatic SQLite fallback)
- **Redis** — odds/stat caching; Celery task broker
- **Celery** — async task queue (odds refresh, sheet export)
- **XGBoost** — NBA/NCAAB ML prediction models
- **Loguru** — structured logging throughout

### Frontend
- **React 18** + **TypeScript** + **Vite**
- **Tailwind CSS** — utility-first styling
- **@tanstack/react-query** — server state management
- **Axios** — API client (auto-unwraps `response.data`)

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker (optional — full-stack via `docker-compose up --build`)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
python run_server.py   # FastAPI on port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # Vite dev server on port 3000
```

### Docker (full stack)

```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Standalone Prediction Script (no server required)

Run the ML prop prediction engine directly — no API keys, no Docker, no server:

```bash
# 1. Install only the 3 required packages
pip install -r scripts/requirements-predict.txt

# 2a. Single prop
python3 scripts/predict_props_v2.py \
  --player "Jayson Tatum" --prop points --line 23.5 --odds -120 --dvp 14 --minutes 37

# 2b. Batch — tonight's full slate (30 props)
python3 scripts/predict_props_v2.py \
  --batch scripts/tonight_march8.json --top-n 30 --output top30.json
```

See **[scripts/README.md](scripts/README.md)** for the full argument reference,
batch JSON format, and example output.

## Required Environment Variables

```bash
# Odds
THE_ODDS_API_KEY=your_key          # Primary odds source (props + game lines)

# Database
DATABASE_URL=postgresql://...       # PostgreSQL; falls back to SQLite if unset
SUPABASE_URL=https://...
SUPABASE_KEY=your_anon_key

# Cache
REDIS_URL=redis://localhost:6379/0

# Reporting
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/sa.json
GOOGLE_SPREADSHEET_ID=your_sheet_id

# Optional
OPENAI_API_KEY=your_key            # ExpertAgent sequential reasoning
QDRANT_URL=http://localhost:6333   # Vector store for parlay RAG
```

## Key Commands

```bash
# Run daily NBA analysis + export
python backend/run_nba_analysis.py

# Run NCAAB sharp money analysis
python backend/run_ncaab_analysis.py

# Send Telegram report immediately
python backend/telegram_cron.py --send-now

# Run all unit tests
PYTHONPATH=$(pwd)/backend python3 -m pytest backend/tests/unit/ --tb=short -q
```

## Core API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/props/{sport}` | Live props with full analysis |
| `GET`  | `/api/v1/bets/tracked` | All tracked bets (win/loss) |
| `POST` | `/api/v1/bets/{id}/settle` | Mark a bet won/lost/push |
| `GET`  | `/api/v1/bets/performance` | Win rate, ROI, CLV metrics |
| `GET`  | `/api/v1/parlays` | Saved parlays list |
| `GET`  | `/api/v1/cbb/games` | NCAAB game edges + sharp signals |
| `POST` | `/api/v1/sheets/{id}/export-all` | Full daily Google Sheets export |
| `GET`  | `/api/v1/agents/analyze` | Multi-agent expert analysis |

## Betting Logic Summary

- **Primary book**: FanDuel (`PRIMARY_BOOK=fanduel`). FD odds are shown alongside best-market odds on every prop.
- **Odds floor**: Individual parlay legs must have odds ≥ −200. Anything heavier than −200 is excluded.
- **Win probability**: The model's `posterior_p` (Bayesian win probability) is the primary metric — not raw odds or edge %. Displayed on every bet card and in the HighValueProps sheet.
- **Kelly sizing**: Always Fractional Kelly (Quarter or Half). Hard cap at 5% of bankroll per bet.
- **Parlay diversity**: The parlay engine limits each team to ≤ 3 legs in the cross-game pool and caps SGPs from any single game at 3 suggestions, preventing one team from dominating the output.
- **EV thresholds**: Low confidence ≥ 3% edge (Quarter Kelly), Medium ≥ 5%, High ≥ 7%, Max ≥ 10%.

## Database Architecture

See [`DATABASE_SERVICES.md`](DATABASE_SERVICES.md) for full schema documentation.

**Bet tracking** (`bet_tracker.py`):
- Dual-write: operational record to Supabase/SQLite + analytical record to PostgreSQL `bets` table
- `win_probability` (model's true probability) stored alongside each bet for post-hoc calibration analysis
- Automatic SQLite fallback when Supabase is unavailable

## Development

### Adding New Data Sources

1. Create a service in `backend/app/services/`
2. Add an endpoint in `backend/app/routers/`
3. Register the router in `backend/app/main.py`

### Running Bayesian Models

```python
from app.services.bayesian import BayesianAnalyzer

analyzer = BayesianAnalyzer()
result = analyzer.compute_posterior({
    'devig_prob': 0.56,
    'implied_prob': 0.52,
    'current_american_odds': -115,
    'features': {'injury_status': 'ACTIVE', 'is_home': True}
})
# result: {'posterior_p': 0.57, 'edge': 0.048, 'kelly_fraction': 0.096, ...}
```

## Monitoring

- API Docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:3000`

## License

MIT
