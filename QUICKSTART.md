# Quick Start Guide

## Current Issue: 500 Internal Server Error

The 500 error you're seeing is because **Redis is not running**. The application requires Redis for caching and background tasks.

## Solution: Start Redis

### Option 1: Using Docker (Recommended)

```bash
# Start Redis and PostgreSQL
docker-compose up -d postgres redis

# Verify services are running
docker-compose ps
```

### Option 2: Quick Start Script

```bash
# Make script executable (if not already)
chmod +x quick_start.sh

# Run the script
./quick_start.sh
```

### Option 3: Redis Only (Minimum)

```bash
# Just start Redis if you want to use SQLite for database
docker run -d -p 6379:6379 redis:alpine
```

## Complete Setup Steps

### 1. Start Required Services

```bash
cd /workspace

# Start Redis and PostgreSQL
docker-compose up -d postgres redis

# Wait for services to be healthy (about 10 seconds)
```

### 2. Start Backend

```bash
cd /workspace/backend

# Install dependencies (if needed)
pip install -r requirements.txt

# Start the server
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Start Frontend (in another terminal)

```bash
cd /workspace/frontend

# Install dependencies (if needed)
npm install

# Start development server
npm run dev
```

You should see:
```
VITE ready in XXX ms
➜  Local:   http://localhost:5173/
```

### 4. Access the Application

- **Frontend**: http://localhost:5173 (or the port shown)
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Alternative API Docs**: http://localhost:8000/redoc

## What's Already Configured

✅ **Environment Variables** - `.env` file created with:
- SQLite database (no setup needed)
- Redis connection
- Celery configuration
- All required settings

✅ **No API Keys Required** to start - The app works with:
- Sample/demo data
- Local ML predictions
- Data cleaning and storage

## Optional: Add API Keys for Live Data

See `SETUP_API_KEYS.md` for details on getting:
- **The Odds API** (free tier) - For live betting odds
- **SportsRadar** - For game statistics
- **OpenAI** - For advanced AI features
- Others...

## Troubleshooting

### Redis Connection Error
```
Error: Redis connection refused
```
**Solution**: Start Redis with Docker
```bash
docker-compose up -d redis
```

### Database Error
```
Error: DATABASE_URL not set
```
**Solution**: Check `.env` file exists in `/workspace/backend/`
```bash
ls -la /workspace/backend/.env
```

### Port Already in Use
```
Error: Address already in use
```
**Solution**: Change port in `.env` or kill existing process
```bash
# Find process using port 8000
lsof -ti:8000 | xargs kill -9
```

### Frontend Can't Connect to Backend
**Solution**: Make sure backend is running on port 8000
```bash
curl http://localhost:8000/health
```

## Verifying Everything Works

1. **Check Services**:
```bash
docker-compose ps
# Should show postgres and redis as "Up (healthy)"
```

2. **Check Backend**:
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

3. **Check API**:
```bash
curl http://localhost:8000/api/v1/bets
# Should return bet data (may be empty initially)
```

4. **Check Frontend**:
Open http://localhost:5173 in your browser
- Dashboard should load
- No 500 errors in browser console

## Next Steps After Setup

1. **View Best Bets**: Navigate to "Best Bets" page
2. **Run Analysis**: Click "Analyze Today's Games"
3. **Check Database**: Bets are automatically stored
4. **Add API Keys**: For live odds (optional)

## Services Overview

| Service | Port | Purpose | Required |
|---------|------|---------|----------|
| Redis | 6379 | Caching & tasks | ✅ Yes |
| PostgreSQL | 5433 | Database | ⚠️ Optional (can use SQLite) |
| Backend | 8000 | API server | ✅ Yes |
| Frontend | 5173 | Web interface | ✅ Yes |

## Minimum to Start

The **absolute minimum** you need:
1. Redis running (via Docker)
2. Backend server running
3. Frontend server running

That's it! No API keys, no PostgreSQL if using SQLite.

## Quick Commands

```bash
# Start everything
docker-compose up -d postgres redis
cd backend && python main.py &
cd frontend && npm run dev

# Stop everything
docker-compose down
pkill -f "python main.py"

# View logs
docker-compose logs redis
docker-compose logs postgres

# Reset database
rm backend/sports_betting.db
# Restart backend to recreate
```

## Getting Help

If you're still seeing errors:

1. Check backend logs for specific error messages
2. Check Redis is running: `docker ps | grep redis`
3. Verify .env file: `cat backend/.env`
4. Check browser console for frontend errors
5. Review API docs: http://localhost:8000/docs

The most common issue is Redis not running - make sure to start it with Docker!
