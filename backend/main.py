"""
Sports Data Intelligence Platform - Main API Server
"""
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.database import init_db
from app.routers import bets, analyze, odds, sentiment, predictions, notion, agents, google_sheets
from app.routers import parlays
from app.services.cache import RedisCache


# Configure logger
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("🚀 Starting Sports Data Intelligence Platform...")
    
    # Initialize database
    await init_db()
    
    # Initialize cache
    await RedisCache.get_instance()
    
    logger.info("✅ Startup complete!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Sports Data Intelligence Platform",
    description="Comprehensive sports betting intelligence API with ML, Bayesian models, and Notion integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/")
async def root():
    return {
        "name": "Sports Data Intelligence Platform",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Include routers
app.include_router(bets.router, prefix="/api/v1", tags=["bets"])
app.include_router(analyze.router, prefix="/api/v1", tags=["analyze"])
app.include_router(odds.router, prefix="/api/v1", tags=["odds"])
app.include_router(sentiment.router, prefix="/api/v1", tags=["sentiment"])
app.include_router(predictions.router, prefix="/api/v1", tags=["predictions"])
app.include_router(notion.router, prefix="/api/v1", tags=["notion"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(google_sheets.router, prefix="/api/v1", tags=["google-sheets"])
app.include_router(parlays.router, prefix="/api/v1", tags=["parlays"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )

