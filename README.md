# Sports Data Intelligence Platform

A comprehensive sports betting intelligence application that aggregates data from multiple sources, runs Bayesian models, performs ML analysis, and automatically updates your Notion database.

## Features

- 🎯 **Best Bets Analysis**: Aggregates odds from multiple sportsbooks and identifies value bets
- 🧠 **Sequential Thinking**: Expert-level reasoning like a professional sports bettor
- 🤖 **Multi-Agent System**: Specialized agents that learn from past mistakes
- 🕷️ **AI Web Scraping**: Crawl4AI-powered intelligent data extraction
- 🐦 **Twitter Sentiment Analysis**: Monitors and analyzes Twitter discussions about teams/players
- 📊 **Bayesian Models**: Runs sophisticated betting probability calculations
- 🤖 **Hugging Face ML**: Sentiment analysis and prediction models
- 📝 **Notion Integration**: Automatically updates your Notion database with insights
- 📱 **Modern Dashboard**: Beautiful React frontend with real-time updates

## Tech Stack

### Backend
- **FastAPI** - Modern Python API framework
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** - Primary database
- **Redis** - Caching layer
- **Celery** - Task queue for async operations
- **Hugging Face Transformers** - ML models
- **PyMC3** - Bayesian modeling
- **Selenium/Playwright** - Web scraping

### Frontend
- **React** - UI framework
- **TailwindCSS** - Styling
- **TypeScript** - Type safety
- **Recharts** - Data visualization
- **React Query** - Data fetching

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis
- Docker (optional)

### Installation

1. **Clone the project:**
```bash
cd /Users/jackcurran/sports-data-platform
```

2. **Set up backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. **Set up database:**
```bash
alembic upgrade head
```

5. **Set up frontend:**
```bash
cd ../frontend
npm install
```

6. **Run the application:**
```bash
# Terminal 1 - Backend
cd backend
python run_server.py

# Terminal 2 - Frontend
cd frontend
npm start

# Terminal 3 - Celery Worker (for async tasks)
cd backend
celery -A app.celery_app worker --loglevel=info
```

## Required API Keys

Add these to your `.env` file:

```bash
# Sports APIs
SPORTSRADAR_API_KEY=your_key
ODDSAPI_API_KEY=your_key
THE_ODDS_API_KEY=your_key

# Twitter
TWITTER_BEARER_TOKEN=your_token

# Hugging Face
HUGGINGFACE_API_KEY=your_token

# Notion
NOTION_API_KEY=secret_your_integration_key
NOTION_DATABASE_ID=your_database_id

# OpenAI
OPENAI_API_KEY=your_key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/sports_data
REDIS_URL=redis://localhost:6379/0
```

## Usage

### 1. View Dashboard
Navigate to `http://localhost:3000` to see the dashboard

### 2. Trigger Analysis
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"sport": "nfl", "target_date": "2024-01-15"}'
```

### 3. View Notion Updates
Your Notion database will be automatically updated with:
- Best bets with edge calculations
- Twitter sentiment scores
- Historical performance metrics

## API Endpoints

- `GET /api/v1/bets` - Get best bets
- `POST /api/v1/analyze` - Trigger full analysis
- `GET /api/v1/odds/{sport}` - Get current odds
- `GET /api/v1/sentiment/{team}` - Get Twitter sentiment
- `POST /api/v1/bayesian` - Run Bayesian model
- `GET /api/v1/predictions` - Get ML predictions
- `POST /api/v1/agents/analyze` - Multi-agent analysis with sequential thinking
- `GET /api/v1/agents/status` - Agent status and performance
- `POST /api/v1/agents/learn` - Submit outcomes for learning
- `POST /api/v1/notion/sync` - Manually sync to Notion

## Architecture

```
┌─────────────────┐
│  React Frontend │
└────────┬────────┘
         │
    ┌────┴────┐
    │ FastAPI │
    └────┬────┘
         │
    ┌────┴────────────────────┐
    │                          │
┌───┴───┐  ┌─────────────────┐  ┌──────────────┐
│ Celery│  │  ML Services     │  │  Bayesian    │
│ Tasks │  │  (Hugging Face)  │  │  Models      │
└───┬───┘  └─────────────────┘  └──────────────┘
    │
┌───┴────────────────────────────────────────┐
│  PostgreSQL  │  Redis  │  Notion  │  APIs  │
└─────────────────────────────────────────────┘
```

## Services

1. **Sports Data API** - Aggregates odds from multiple sources
2. **Twitter Analyzer** - Collects tweets and analyzes sentiment
3. **Web Scraper** - Scrapes sports data from websites
4. **Bayesian Models** - Computes probabilities and edges
5. **ML Service** - Uses Hugging Face for predictions
6. **Notion Integration** - Syncs data to Notion database

## Development

### Adding New Data Sources

1. Create a new service in `backend/app/services/`
2. Add API endpoint in `backend/app/routers/`
3. Update frontend components in `frontend/src/components/`

### Running Bayesian Models

```python
from app.services.bayesian import BayesianAnalyzer

analyzer = BayesianAnalyzer()
result = analyzer.compute_posterior({
    'devig_prob': 0.52,
    'implied_prob': 0.48,
    'features': {
        'injury_status': 'ACTIVE',
        'team_pace': 104.2
    }
})
```

### Using Hugging Face Models

```python
from app.services.ml_analyzer import MLService

ml_service = MLService()
sentiment = ml_service.analyze_sentiment(
    tweets=['Great game!', 'That was terrible']
)
```

## Monitoring

- API Docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:3000`
- Flower (Celery): `http://localhost:5555`

## License

MIT

