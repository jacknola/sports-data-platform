"""
Historical Data API Router

Provides endpoints for querying historical game lines and player props,
including vector similarity search.
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.historical_game_line import HistoricalGameLine
from app.models.historical_player_prop import HistoricalPlayerProp

router = APIRouter(tags=["historical"])


@router.get("/games")
async def get_historical_games(
    season: Optional[int] = Query(None, description="Filter by season year"),
    home_team: Optional[str] = Query(None, description="Filter by home team"),
    away_team: Optional[str] = Query(None, description="Filter by away team"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """Query historical game lines."""
    query = db.query(HistoricalGameLine)

    if season:
        query = query.filter(HistoricalGameLine.season == season)

    if home_team:
        query = query.filter(HistoricalGameLine.home_team.ilike(f"%{home_team}%"))

    if away_team:
        query = query.filter(HistoricalGameLine.away_team.ilike(f"%{away_team}%"))

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(HistoricalGameLine.game_date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(HistoricalGameLine.game_date <= end)
        except ValueError:
            pass

    total = query.count()
    games = (
        query.order_by(HistoricalGameLine.game_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "games": [
            {
                "id": g.id,
                "game_date": g.game_date.isoformat() if g.game_date else None,
                "season": g.season,
                "home_team": g.home_team,
                "away_team": g.away_team,
                "home_score": g.home_score,
                "away_score": g.away_score,
                "total_score": g.total_score,
                "margin": g.margin,
                "home_spread": g.home_spread,
                "over_under": g.over_under,
                "home_ml": g.home_ml,
                "away_ml": g.away_ml,
                "clv_spread": g.clv_spread,
                "clv_total": g.clv_total,
                "source": g.source,
            }
            for g in games
        ],
    }


@router.get("/games/{game_id}")
async def get_game_by_id(game_id: int, db: Session = Depends(get_db)):
    """Get a specific historical game by ID."""
    game = db.query(HistoricalGameLine).filter(HistoricalGameLine.id == game_id).first()

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return {
        "id": game.id,
        "game_date": game.game_date.isoformat() if game.game_date else None,
        "season": game.season,
        "home_team": game.home_team,
        "away_team": game.away_team,
        "home_score": game.home_score,
        "away_score": game.away_score,
        "total_score": game.total_score,
        "margin": game.margin,
        "home_spread": game.home_spread,
        "away_spread": game.away_spread,
        "spread_odds": game.spread_odds,
        "over_under": game.over_under,
        "over_odds": game.over_odds,
        "under_odds": game.under_odds,
        "home_ml": game.home_ml,
        "away_ml": game.away_ml,
        "clv_spread": game.clv_spread,
        "clv_total": game.clv_total,
        "source": game.source,
        "external_game_id": game.external_game_id,
        "raw_data": game.raw_data,
    }


@router.get("/props")
async def get_historical_props(
    season: Optional[int] = Query(None, description="Filter by season year"),
    player_name: Optional[str] = Query(None, description="Filter by player name"),
    team: Optional[str] = Query(None, description="Filter by team"),
    prop_type: Optional[str] = Query(
        None, description="Prop type (points, rebounds, assists, etc.)"
    ),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    sportsbook: Optional[str] = Query(None, description="Sportsbook"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """Query historical player props."""
    query = db.query(HistoricalPlayerProp)

    if season:
        query = query.filter(HistoricalPlayerProp.season == season)

    if player_name:
        query = query.filter(HistoricalPlayerProp.player_name.ilike(f"%{player_name}%"))

    if team:
        query = query.filter(HistoricalPlayerProp.team.ilike(f"%{team}%"))

    if prop_type:
        query = query.filter(HistoricalPlayerProp.prop_type == prop_type)

    if sportsbook:
        query = query.filter(HistoricalPlayerProp.sportsbook.ilike(f"%{sportsbook}%"))

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(HistoricalPlayerProp.game_date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(HistoricalPlayerProp.game_date <= end)
        except ValueError:
            pass

    total = query.count()
    props = (
        query.order_by(HistoricalPlayerProp.game_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "props": [
            {
                "id": p.id,
                "player_name": p.player_name,
                "team": p.team,
                "opponent": p.opponent,
                "game_date": p.game_date.isoformat() if p.game_date else None,
                "season": p.season,
                "prop_type": p.prop_type,
                "line": p.line,
                "over_odds": p.over_odds,
                "under_odds": p.under_odds,
                "actual": p.actual,
                "result": p.result,
                "clv": p.clv,
                "sportsbook": p.sportsbook,
                "source": p.source,
            }
            for p in props
        ],
    }


@router.get("/props/{prop_id}")
async def get_prop_by_id(prop_id: int, db: Session = Depends(get_db)):
    """Get a specific historical player prop by ID."""
    prop = (
        db.query(HistoricalPlayerProp)
        .filter(HistoricalPlayerProp.id == prop_id)
        .first()
    )

    if not prop:
        raise HTTPException(status_code=404, detail="Prop not found")

    return {
        "id": prop.id,
        "player_name": prop.player_name,
        "player_id": prop.player_id,
        "team": prop.team,
        "opponent": prop.opponent,
        "game_date": prop.game_date.isoformat() if prop.game_date else None,
        "season": prop.season,
        "prop_type": prop.prop_type,
        "stat_type": prop.stat_type,
        "line": prop.line,
        "over_odds": prop.over_odds,
        "under_odds": prop.under_odds,
        "over_price": prop.over_price,
        "under_price": prop.under_price,
        "actual": prop.actual,
        "result": prop.result,
        "predicted": prop.predicted,
        "model_edge": prop.model_edge,
        "clv": prop.clv,
        "clv_pct": prop.clv_pct,
        "open_line": prop.open_line,
        "sportsbook": prop.sportsbook,
        "source": prop.source,
        "external_prop_id": prop.external_prop_id,
        "raw_data": prop.raw_data,
    }


@router.get("/stats")
async def get_historical_stats(db: Session = Depends(get_db)):
    """Get summary statistics for historical data."""
    game_count = db.query(HistoricalGameLine).count()
    prop_count = db.query(HistoricalPlayerProp).count()

    # Get season range
    earliest_game = (
        db.query(HistoricalGameLine)
        .order_by(HistoricalGameLine.game_date.asc())
        .first()
    )
    latest_game = (
        db.query(HistoricalGameLine)
        .order_by(HistoricalGameLine.game_date.desc())
        .first()
    )

    # Get source breakdown
    from sqlalchemy import func

    game_sources = (
        db.query(HistoricalGameLine.source, func.count(HistoricalGameLine.id))
        .group_by(HistoricalGameLine.source)
        .all()
    )

    prop_sources = (
        db.query(HistoricalPlayerProp.source, func.count(HistoricalPlayerProp.id))
        .group_by(HistoricalPlayerProp.source)
        .all()
    )

    return {
        "games": {
            "total": game_count,
            "earliest_date": earliest_game.game_date.isoformat()
            if earliest_game and earliest_game.game_date
            else None,
            "latest_date": latest_game.game_date.isoformat()
            if latest_game and latest_game.game_date
            else None,
            "sources": {s: c for s, c in game_sources},
        },
        "props": {
            "total": prop_count,
            "sources": {s: c for s, c in prop_sources},
        },
    }
