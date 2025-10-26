"""
Twitter sentiment analysis endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from loguru import logger

from app.services.twitter_analyzer import TwitterAnalyzer

router = APIRouter()
twitter_analyzer = TwitterAnalyzer()


@router.get("/sentiment/{team}")
async def get_team_sentiment(team: str, days: int = 7) -> Dict[str, Any]:
    """
    Get Twitter sentiment analysis for a team
    
    Args:
        team: Team name
        days: Number of days to look back
        
    Returns:
        Sentiment analysis results
    """
    try:
        result = await twitter_analyzer.analyze_team_sentiment(team, days)
        return result
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment/analyze")
async def analyze_tweets(texts: list[str]) -> Dict[str, Any]:
    """
    Analyze sentiment of provided tweets
    
    Args:
        texts: List of tweet texts
        
    Returns:
        Sentiment analysis results
    """
    from app.services.ml_service import MLService
    
    ml_service = MLService()
    result = await ml_service.analyze_sentiment(texts)
    return result

