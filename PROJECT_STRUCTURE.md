# Sports Data Intelligence Platform - Project Structure

## Overview
A comprehensive sports betting intelligence application with ML, Bayesian models, Twitter analysis, and Notion integration.

## Directory Structure

```
sports-data-platform/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── config.py          # Application configuration
│   │   ├── database.py         # Database setup
│   │   ├── models/             # SQLAlchemy models
│   │   │   ├── bet.py         # Bet model
│   │   │   ├── game.py        # Game model
│   │   │   ├── player.py      # Player model
│   │   │   └── team.py        # Team model
│   │   ├── routers/            # API endpoints
│   │   │   ├── bets.py        # Best bets endpoints
│   │   │   ├── analyze.py     # Analysis orchestration
│   │   │   ├── odds.py        # Odds data endpoints
│   │   │   ├── sentiment.py   # Twitter sentiment endpoints
│   │   │   ├── predictions.py # ML prediction endpoints
│   │   │   └── notion.py      # Notion integration endpoints
│   │   └── services/           # Business logic
│   │       ├── bayesian.py    # Bayesian probability models
│   │       ├── ml_service.py  # Hugging Face ML service
│   │       ├── twitter_analyzer.py  # Twitter data collection
│   │       ├── sports_api.py  # Sports data API
│   │       ├── notion_integration.py  # Notion sync
│   │       ├── web_scraper.py # Web scraping
│   │       └── cache.py       # Redis cache
│   ├── main.py                 # FastAPI application
│   ├── run_server.py           # Server entry point
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Docker configuration
├── frontend/                   # React frontend
│   ├── Dockerfile
│   └── package.json
├── notebooks/                  # Jupyter notebooks for analysis
├── scripts/                    # Utility scripts
├── docker-compose.yml          # Docker compose configuration
├── setup.sh                    # Setup script
├── README.md                   # Main documentation
└── .gitignore                  # Git ignore rules

```

## Key Features

### 1. Bayesian Analysis
- **File**: `backend/app/services/bayesian.py`
- Monte Carlo simulations for probability calculations
- Feature-based adjustments (injuries, pace, weather, etc.)
- Kelly Criterion for bet sizing
- Returns: posterior probability, edge, confidence intervals

### 2. ML Service (Hugging Face)
- **File**: `backend/app/services/ml_service.py`
- Twitter sentiment analysis using RoBERTa
- Sentiment classification
- Prediction models (placeholder)

### 3. Twitter Analysis
- **File**: `backend/app/services/twitter_analyzer.py`
- Tweet collection using Tweepy
- Team sentiment analysis
- Engagement metrics
- Real-time sentiment tracking

### 4. API Endpoints
- `GET /api/v1/bets` - Best betting opportunities
- `POST /api/v1/analyze` - Full analysis workflow
- `GET /api/v1/odds/{sport}` - Current odds
- `GET /api/v1/sentiment/{team}` - Twitter sentiment
- `POST /api/v1/bayesian` - Run Bayesian model
- `GET /api/v1/predictions` - ML predictions
- `POST /api/v1/notion/sync` - Sync to Notion

### 5. Database Models
- **Bet**: Betting selections with odds and probabilities
- **Game**: Game information and results
- **Team**: Team data and statistics
- **Player**: Player stats and injury status

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis

### Quick Start
```bash
# Run setup script
./setup.sh

# Update environment variables
cd backend
cp .env.example .env
# Edit .env with your API keys

# Start services with Docker
docker-compose up -d

# Or run manually
cd backend
python run_server.py
```

## Next Steps

1. **Implement web scraping service** (`backend/app/services/web_scraper.py`)
2. **Complete Notion integration** (`backend/app/services/notion_integration.py`)
3. **Build React frontend** in `frontend/`
4. **Add real sports API integrations**
5. **Deploy with Docker**

## API Keys Required

- Sports APIs (SportsRadar, The Odds API)
- Twitter API
- Hugging Face API
- Notion API
- OpenAI API (for embeddings)

See `backend/.env.example` for full list.

