# API Keys Setup Guide

## Required Environment Variables (Must Have)

These are **required** for the application to run:

### 1. Database
```bash
DATABASE_URL=sqlite:///./sports_betting.db
```
- **Already configured** in `.env` file
- Uses SQLite for local development
- No API key needed

### 2. Redis & Celery
```bash
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```
- **Already configured** in `.env` file
- Requires Redis running locally or via Docker
- No API key needed

**To start Redis:**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or using Docker Compose
docker-compose up -d
```

## Optional API Keys (For Enhanced Features)

These are **optional** - the app will work without them but with limited features:

### 1. The Odds API (Recommended for Live Odds)

**What it does**: Fetches real-time betting odds from multiple sportsbooks

**How to get it**:
1. Go to https://the-odds-api.com/
2. Sign up for a free account
3. You get 500 requests/month for free
4. Copy your API key

**Add to `.env`**:
```bash
ODDSAPI_API_KEY=your_key_here
THE_ODDS_API_KEY=your_key_here
```

### 2. SportsRadar API (Optional)

**What it does**: Provides detailed game statistics and player data

**How to get it**:
1. Go to https://developer.sportradar.com/
2. Sign up for a trial account
3. Copy your API key

**Add to `.env`**:
```bash
SPORTSRADAR_API_KEY=your_key_here
```

### 3. Twitter API (Optional - For Sentiment Analysis)

**What it does**: Analyzes social media sentiment around games

**How to get it**:
1. Go to https://developer.twitter.com/
2. Apply for a developer account
3. Create an app and get your credentials

**Add to `.env`**:
```bash
TWITTER_BEARER_TOKEN=your_token_here
TWITTER_CONSUMER_KEY=your_key_here
TWITTER_CONSUMER_SECRET=your_secret_here
```

### 4. OpenAI API (Optional - For AI Analysis)

**What it does**: Enhanced AI-powered analysis and predictions

**How to get it**:
1. Go to https://platform.openai.com/
2. Sign up and add payment method
3. Create an API key

**Add to `.env`**:
```bash
OPENAI_API_KEY=sk-your_key_here
```

### 5. Hugging Face (Optional - For Sentiment Analysis)

**What it does**: Local sentiment analysis without external API calls

**How to get it**:
1. Go to https://huggingface.co/
2. Sign up for a free account
3. Go to Settings → Access Tokens
4. Create a new token

**Add to `.env`**:
```bash
HUGGINGFACE_API_KEY=hf_your_key_here
```

### 6. Notion (Optional - For Bet Tracking)

**What it does**: Automatically logs your bets to a Notion database

**How to get it**:
1. Go to https://www.notion.so/my-integrations
2. Create a new integration
3. Copy the Internal Integration Token
4. Create a database and share it with your integration
5. Copy the database ID from the URL

**Add to `.env`**:
```bash
NOTION_API_KEY=secret_your_key_here
NOTION_DATABASE_ID=your_database_id_here
```

## Current Setup Status

✅ **Working without any API keys:**
- Database (SQLite)
- Data cleaning and storage
- ML predictions (using local models)
- Basic bet analysis

⚠️ **Requires API keys for:**
- Live odds fetching → Need `ODDSAPI_API_KEY`
- Real-time game data → Need `SPORTSRADAR_API_KEY`
- Twitter sentiment → Need Twitter API keys
- Advanced AI features → Need `OPENAI_API_KEY`

## Quick Start (Minimum Setup)

1. **Create `.env` file** (already done):
```bash
cd /workspace/backend
# The .env file is already created with required values
```

2. **Start Redis** (required):
```bash
docker run -d -p 6379:6379 redis:alpine
```

3. **Start the backend**:
```bash
cd /workspace/backend
python main.py
```

4. **Start the frontend**:
```bash
cd /workspace/frontend
npm install
npm run dev
```

## Testing Without API Keys

The application will work in "demo mode" with:
- ✅ Sample prediction data
- ✅ Data cleaning and validation
- ✅ Database storage
- ✅ Dashboard and UI
- ❌ No live odds (will use sample data)
- ❌ No real-time updates

## Adding API Keys Later

You can add API keys anytime by:
1. Editing `/workspace/backend/.env`
2. Adding your API key
3. Restarting the backend server

No code changes needed!

## Troubleshooting

### Error: "REDIS_URL not set"
**Solution**: Start Redis or use Docker Compose:
```bash
docker-compose up -d
```

### Error: "DATABASE_URL not set"
**Solution**: Check that `.env` file exists in `/workspace/backend/`

### Error: "Odds API key not configured"
**Status**: This is just a warning - the app will use sample data instead

## Priority for API Keys

If you want to get real betting data, get these in order:

1. **The Odds API** (Free tier available) - For live odds
2. **SportsRadar** (Trial available) - For game details
3. **OpenAI** (Paid) - For advanced AI analysis
4. **Twitter API** (Free with limitations) - For sentiment
5. **Others** - Nice to have

## Free Tier Limits

- **The Odds API**: 500 requests/month free
- **SportsRadar**: Trial period available
- **Twitter API**: Limited access on free tier
- **OpenAI**: Pay per use (~$0.002 per request)
- **Hugging Face**: Free for open models

## Current Configuration

Check your current setup:
```bash
cd /workspace/backend
cat .env
```

All required environment variables are already configured in your `.env` file!
