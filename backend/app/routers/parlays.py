"""
Parlay management and posting endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger
import uuid

from app.services.twitter_analyzer import TwitterAnalyzer
from app.services.rag_pipeline import RAGPipeline
from app.database import SessionLocal
from app.models.parlay import Parlay, ParlayLeg

router = APIRouter()
twitter_analyzer = TwitterAnalyzer()
rag_pipeline = RAGPipeline()


# Pydantic models for request/response
class ParlayLegCreate(BaseModel):
    game: str
    pick: str
    odds: float
    reasoning: str
    team: str
    opponent: Optional[str] = None
    market: str = Field(..., description="moneyline, spread, total, player_prop")
    line: Optional[float] = None
    supporting_factors: Optional[List[str]] = []
    confidence: Optional[float] = 0.7
    game_time: Optional[datetime] = None


class ParlayCreate(BaseModel):
    title: str
    sport: str = Field(..., description="NBA, NFL, MLB, NHL, Soccer")
    confidence_level: str = Field(..., description="HIGH, MEDIUM, LOW")
    confidence_score: float = Field(..., ge=0, le=100)
    legs: List[ParlayLegCreate]
    analysis: str
    key_factors: List[str] = []
    risks: List[str] = []
    tags: List[str] = []
    suggested_unit_size: Optional[float] = 1.0
    event_date: Optional[datetime] = None


class ParlayUpdate(BaseModel):
    status: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    actual_return: Optional[float] = None


@router.post("/parlays", response_model=Dict[str, Any])
async def create_parlay(parlay: ParlayCreate) -> Dict[str, Any]:
    """
    Create a new parlay (Dan's AI Sports Picks style)
    
    Args:
        parlay: Parlay data
        
    Returns:
        Created parlay with ID
    """
    try:
        # Generate unique ID
        parlay_id = f"parlay_{uuid.uuid4().hex[:12]}"
        
        # Calculate total odds and payout multiplier
        total_odds, payout_multiplier = calculate_parlay_odds([leg.odds for leg in parlay.legs])
        
        # Prepare parlay data
        parlay_data = {
            'parlay_id': parlay_id,
            'title': parlay.title,
            'sport': parlay.sport,
            'confidence_level': parlay.confidence_level,
            'confidence_score': parlay.confidence_score,
            'legs': [leg.dict() for leg in parlay.legs],
            'total_odds': total_odds,
            'potential_payout_multiplier': payout_multiplier,
            'suggested_unit_size': parlay.suggested_unit_size,
            'analysis': parlay.analysis,
            'key_factors': parlay.key_factors,
            'risks': parlay.risks,
            'tags': parlay.tags,
            'event_date': parlay.event_date or datetime.now(),
            'status': 'pending'
        }
        
        # Store in RAG pipeline (with embeddings)
        result = await rag_pipeline.store_parlay(parlay_id, parlay_data, generate_embedding=True)
        
        # Get insights from similar parlays
        insights = await rag_pipeline.get_parlay_insights(parlay_id)
        
        logger.info(f"Created parlay {parlay_id}")
        
        return {
            'parlay_id': parlay_id,
            'parlay_data': parlay_data,
            'insights': insights,
            'message': 'Parlay created successfully'
        }
        
    except Exception as e:
        logger.error(f"Failed to create parlay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parlays/{parlay_id}", response_model=Dict[str, Any])
async def get_parlay(parlay_id: str) -> Dict[str, Any]:
    """
    Get parlay by ID
    
    Args:
        parlay_id: Parlay identifier
        
    Returns:
        Parlay data
    """
    parlay = await rag_pipeline.retrieve_parlay(parlay_id)
    
    if not parlay:
        raise HTTPException(status_code=404, detail="Parlay not found")
    
    return parlay


@router.get("/parlays", response_model=List[Dict[str, Any]])
async def list_parlays(
    sport: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, le=100)
) -> List[Dict[str, Any]]:
    """
    List parlays with optional filters
    
    Args:
        sport: Filter by sport
        status: Filter by status (pending, won, lost)
        limit: Maximum number of results
        
    Returns:
        List of parlays
    """
    db = SessionLocal()
    
    try:
        query = db.query(Parlay)
        
        if sport:
            query = query.filter(Parlay.sport == sport)
        
        if status:
            query = query.filter(Parlay.status == status)
        
        parlays = query.order_by(Parlay.created_at.desc()).limit(limit).all()
        
        return [
            {
                'parlay_id': p.parlay_id,
                'title': p.title,
                'sport': p.sport,
                'confidence_level': p.confidence_level,
                'total_odds': p.total_odds,
                'status': p.status,
                'created_at': p.created_at.isoformat(),
                'twitter_post_id': p.twitter_post_id
            }
            for p in parlays
        ]
        
    finally:
        db.close()


@router.post("/parlays/{parlay_id}/post-twitter", response_model=Dict[str, Any])
async def post_parlay_to_twitter(
    parlay_id: str,
    as_thread: bool = Query(False, description="Post as thread with detailed analysis")
) -> Dict[str, Any]:
    """
    Post a parlay to Twitter in Dan's AI Sports Picks style
    
    Args:
        parlay_id: Parlay identifier
        as_thread: Post as thread vs single tweet
        
    Returns:
        Twitter post details
    """
    # Retrieve parlay
    parlay = await rag_pipeline.retrieve_parlay(parlay_id)
    
    if not parlay:
        raise HTTPException(status_code=404, detail="Parlay not found")
    
    try:
        if as_thread:
            # Post as thread
            tweets = twitter_analyzer.post_parlay_thread(parlay, include_detailed_analysis=True)
            
            if not tweets:
                raise HTTPException(status_code=500, detail="Failed to post Twitter thread")
            
            main_tweet = tweets[0]
            tweet_id = main_tweet['tweet_id']
            
            result = {
                'parlay_id': parlay_id,
                'tweet_id': tweet_id,
                'thread': tweets,
                'url': f"https://twitter.com/i/web/status/{tweet_id}",
                'posted_at': datetime.now().isoformat()
            }
        else:
            # Post single tweet
            tweet_data = twitter_analyzer.post_parlay_tweet(parlay)
            
            if not tweet_data:
                raise HTTPException(status_code=500, detail="Failed to post tweet")
            
            result = {
                'parlay_id': parlay_id,
                **tweet_data
            }
        
        # Update parlay with Twitter info
        db = SessionLocal()
        try:
            db_parlay = db.query(Parlay).filter(Parlay.parlay_id == parlay_id).first()
            if db_parlay:
                db_parlay.twitter_post_id = result['tweet_id']
                db_parlay.twitter_posted_at = datetime.now()
                db_parlay.tweet_text = result.get('tweet_text', '')
                db.commit()
        finally:
            db.close()
        
        logger.info(f"Posted parlay {parlay_id} to Twitter")
        return result
        
    except Exception as e:
        logger.error(f"Failed to post parlay to Twitter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parlays/{parlay_id}/format", response_model=Dict[str, Any])
async def preview_parlay_tweet(parlay_id: str) -> Dict[str, Any]:
    """
    Preview how a parlay will look as a tweet (without posting)
    
    Args:
        parlay_id: Parlay identifier
        
    Returns:
        Formatted tweet text
    """
    parlay = await rag_pipeline.retrieve_parlay(parlay_id)
    
    if not parlay:
        raise HTTPException(status_code=404, detail="Parlay not found")
    
    tweet_text = twitter_analyzer.format_dan_style_parlay(parlay)
    
    return {
        'parlay_id': parlay_id,
        'tweet_text': tweet_text,
        'character_count': len(tweet_text),
        'within_limit': len(tweet_text) <= 280
    }


@router.post("/parlays/{parlay_id}/update", response_model=Dict[str, Any])
async def update_parlay_result(
    parlay_id: str,
    update: ParlayUpdate
) -> Dict[str, Any]:
    """
    Update parlay result after games complete
    
    Args:
        parlay_id: Parlay identifier
        update: Update data (status, results)
        
    Returns:
        Updated parlay
    """
    db = SessionLocal()
    
    try:
        parlay = db.query(Parlay).filter(Parlay.parlay_id == parlay_id).first()
        
        if not parlay:
            raise HTTPException(status_code=404, detail="Parlay not found")
        
        if update.status:
            parlay.status = update.status
        
        if update.result:
            parlay.result = update.result
        
        if update.actual_return is not None:
            parlay.actual_return = update.actual_return
            # Calculate ROI
            if parlay.suggested_unit_size > 0:
                parlay.roi = ((update.actual_return - parlay.suggested_unit_size) / 
                             parlay.suggested_unit_size * 100)
                parlay.profit_loss = update.actual_return - parlay.suggested_unit_size
        
        db.commit()
        db.refresh(parlay)
        
        logger.info(f"Updated parlay {parlay_id} with result: {update.status}")
        
        return {
            'parlay_id': parlay_id,
            'status': parlay.status,
            'result': parlay.result,
            'roi': parlay.roi,
            'profit_loss': parlay.profit_loss
        }
        
    finally:
        db.close()


@router.get("/parlays/{parlay_id}/insights", response_model=Dict[str, Any])
async def get_parlay_insights(parlay_id: str) -> Dict[str, Any]:
    """
    Get insights about a parlay based on similar historical parlays
    
    Args:
        parlay_id: Parlay identifier
        
    Returns:
        Insights and recommendations
    """
    insights = await rag_pipeline.get_parlay_insights(parlay_id)
    
    if 'error' in insights:
        raise HTTPException(status_code=404, detail=insights['error'])
    
    return insights


@router.post("/parlays/search", response_model=List[Dict[str, Any]])
async def search_parlays(
    query: str,
    limit: int = Query(10, le=50),
    sport: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search parlays using natural language
    
    Args:
        query: Natural language search query
        limit: Maximum number of results
        sport: Filter by sport
        
    Returns:
        Matching parlays
    """
    filters = {}
    if sport:
        filters['sport'] = sport
    
    results = await rag_pipeline.search_parlays_by_text(query, limit=limit, filters=filters)
    
    return results


@router.get("/parlays/{parlay_id}/engagement", response_model=Dict[str, Any])
async def get_parlay_twitter_engagement(parlay_id: str) -> Dict[str, Any]:
    """
    Get Twitter engagement metrics for a posted parlay
    
    Args:
        parlay_id: Parlay identifier
        
    Returns:
        Engagement metrics
    """
    # Get parlay
    db = SessionLocal()
    
    try:
        parlay = db.query(Parlay).filter(Parlay.parlay_id == parlay_id).first()
        
        if not parlay:
            raise HTTPException(status_code=404, detail="Parlay not found")
        
        if not parlay.twitter_post_id:
            raise HTTPException(status_code=400, detail="Parlay not posted to Twitter")
        
        # Get engagement metrics
        engagement = twitter_analyzer.get_parlay_engagement(parlay.twitter_post_id)
        
        return {
            'parlay_id': parlay_id,
            'twitter_post_id': parlay.twitter_post_id,
            'posted_at': parlay.twitter_posted_at.isoformat() if parlay.twitter_posted_at else None,
            'engagement': engagement
        }
        
    finally:
        db.close()


@router.get("/parlays/stats/performance", response_model=Dict[str, Any])
async def get_parlay_performance_stats() -> Dict[str, Any]:
    """
    Get overall parlay performance statistics
    
    Returns:
        Performance metrics
    """
    db = SessionLocal()
    
    try:
        # Get all completed parlays
        completed = db.query(Parlay).filter(
            Parlay.status.in_(['won', 'lost'])
        ).all()
        
        if not completed:
            return {
                'total_parlays': 0,
                'message': 'No completed parlays yet'
            }
        
        won = [p for p in completed if p.status == 'won']
        lost = [p for p in completed if p.status == 'lost']
        
        total_invested = sum(p.suggested_unit_size or 0 for p in completed)
        total_return = sum(p.actual_return or 0 for p in completed)
        
        # Performance by sport
        sports_stats = {}
        for parlay in completed:
            sport = parlay.sport
            if sport not in sports_stats:
                sports_stats[sport] = {'won': 0, 'lost': 0, 'roi': 0}
            
            sports_stats[sport]['won' if parlay.status == 'won' else 'lost'] += 1
            if parlay.roi:
                sports_stats[sport]['roi'] += parlay.roi
        
        return {
            'total_parlays': len(completed),
            'won': len(won),
            'lost': len(lost),
            'win_rate': len(won) / len(completed) * 100,
            'total_invested': total_invested,
            'total_return': total_return,
            'net_profit': total_return - total_invested,
            'overall_roi': ((total_return - total_invested) / total_invested * 100) if total_invested > 0 else 0,
            'by_sport': sports_stats,
            'avg_odds': sum(p.total_odds for p in completed) / len(completed)
        }
        
    finally:
        db.close()


# Helper functions
def calculate_parlay_odds(leg_odds: List[float]) -> tuple[float, float]:
    """
    Calculate total parlay odds and payout multiplier
    
    Args:
        leg_odds: List of American odds for each leg
        
    Returns:
        (total_american_odds, payout_multiplier)
    """
    # Convert American odds to decimal
    decimal_odds = []
    for odds in leg_odds:
        if odds >= 0:
            decimal = 1 + (odds / 100)
        else:
            decimal = 1 + (100 / abs(odds))
        decimal_odds.append(decimal)
    
    # Calculate combined odds
    combined_decimal = 1.0
    for decimal in decimal_odds:
        combined_decimal *= decimal
    
    # Convert back to American odds
    if combined_decimal >= 2.0:
        total_american = (combined_decimal - 1) * 100
    else:
        total_american = -100 / (combined_decimal - 1)
    
    return total_american, combined_decimal
