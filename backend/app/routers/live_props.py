"""
Live In-Game Prop endpoints

Wraps LivePropEngine for real-time prop analysis during a game.

Endpoints:
  POST /props/live/analyze      — Single live prop analysis
  POST /props/live/slate        — Analyze a full slate of live props
  POST /props/live/pace         — Estimate current game pace from live score/time
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List
from loguru import logger

from app.services.live_prop_engine import (
    LivePropEngine,
    LiveGameState,
    LivePlayerState,
    LivePropLine,
    estimate_live_pace,
)

router = APIRouter()
_engine = LivePropEngine()


def _parse_game_state(data: Dict) -> LiveGameState:
    return LiveGameState(
        game_id=data.get('game_id', ''),
        sport=data.get('sport', 'nba').lower(),
        period=data.get('period', 2),
        minutes_remaining=float(data['minutes_remaining']),
        home_team=data.get('home_team', ''),
        away_team=data.get('away_team', ''),
        home_score=int(data.get('home_score', 0)),
        away_score=int(data.get('away_score', 0)),
        actual_pace=float(data.get('actual_pace', 100.0)),
        is_overtime=bool(data.get('is_overtime', False)),
    )


def _parse_player_state(data: Dict) -> LivePlayerState:
    return LivePlayerState(
        player_id=data['player_id'],
        player_name=data['player_name'],
        team=data.get('team', ''),
        stat_type=data['stat_type'],
        current_stat=float(data['current_stat']),
        minutes_played=float(data.get('minutes_played', 0.0)),
        fouls=int(data.get('fouls', 0)),
        is_star=bool(data.get('is_star', True)),
    )


def _parse_live_line(data: Dict) -> LivePropLine:
    return LivePropLine(
        threshold=float(data['threshold']),
        over_odds=float(data['over_odds']),
        under_odds=float(data['under_odds']),
    )


@router.post("/props/live/analyze")
async def analyze_live_prop(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a single live player prop given current game state.

    Computes residual probability — P(player hits threshold | current stat, minutes left) —
    and compares against the live line implied probability to surface edge.

    Expected input:
    {
        "player": {
            "player_id": "ty_jerome",
            "player_name": "Ty Jerome",
            "team": "MEM",
            "stat_type": "threes",
            "current_stat": 2,
            "minutes_played": 14.5,
            "fouls": 1,
            "is_star": false
        },
        "game_state": {
            "game_id": "nba_mem_mia_20260222",
            "sport": "nba",
            "period": 2,
            "minutes_remaining": 33.5,
            "home_team": "MEM",
            "away_team": "MIA",
            "home_score": 38,
            "away_score": 35,
            "actual_pace": 108.2
        },
        "player_season_data": {
            "season_avg": 2.1,
            "avg_minutes": 28.0,
            "expected_pace": 102.0
        },
        "live_line": {
            "threshold": 3.5,
            "over_odds": 154,
            "under_odds": -200
        }
    }
    """
    required_keys = ['player', 'game_state', 'player_season_data', 'live_line']
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required keys: {missing}")

    player_required = ['player_id', 'player_name', 'stat_type', 'current_stat']
    missing_player = [k for k in player_required if k not in data['player']]
    if missing_player:
        raise HTTPException(status_code=422, detail=f"Missing player fields: {missing_player}")

    if 'minutes_remaining' not in data['game_state']:
        raise HTTPException(status_code=422, detail="game_state.minutes_remaining is required")

    line_required = ['threshold', 'over_odds', 'under_odds']
    missing_line = [k for k in line_required if k not in data['live_line']]
    if missing_line:
        raise HTTPException(status_code=422, detail=f"Missing live_line fields: {missing_line}")

    try:
        player = _parse_player_state(data['player'])
        game_state = _parse_game_state(data['game_state'])
        player_season_data = data['player_season_data']
        live_line = _parse_live_line(data['live_line'])

        projection = _engine.analyze(player, game_state, player_season_data, live_line)
        return projection.to_dict()

    except Exception as e:
        logger.error(f"Live prop analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/props/live/slate")
async def analyze_live_slate(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a full slate of live props for an in-progress game.

    Returns all projections sorted by edge descending. Positive EV props
    (edge >= 5%) are flagged with is_positive_ev=true.

    Expected input:
    {
        "props": [
            {
                "player": { ... },
                "game_state": { ... },
                "player_season_data": { ... },
                "live_line": { ... }
            },
            ...
        ],
        "min_edge": 0.05
    }
    """
    props = data.get('props', [])
    if not props:
        raise HTTPException(status_code=422, detail="props list is required and cannot be empty")

    min_edge = float(data.get('min_edge', 0.05))

    try:
        parsed = []
        for entry in props:
            parsed.append({
                'player': _parse_player_state(entry['player']),
                'game_state': _parse_game_state(entry['game_state']),
                'player_season_data': entry['player_season_data'],
                'live_line': _parse_live_line(entry['live_line']),
            })

        all_projections = _engine.analyze_slate(parsed)
        positive_ev = [p for p in all_projections if p['best_edge'] >= min_edge]

        return {
            'total_analyzed': len(all_projections),
            'positive_ev_count': len(positive_ev),
            'min_edge_threshold': min_edge,
            'props': all_projections,
            'best_plays': positive_ev,
        }

    except Exception as e:
        logger.error(f"Live slate analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/props/live/pace")
async def estimate_pace(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate current game pace from live score and elapsed time.

    Useful for populating actual_pace in game_state when the data feed
    does not provide a direct possession count.

    Expected input:
    {
        "home_score": 38,
        "away_score": 35,
        "minutes_played": 14.5,
        "sport": "nba"
    }
    """
    required = ['home_score', 'away_score', 'minutes_played']
    missing = [k for k in required if k not in data]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")

    try:
        pace = estimate_live_pace(
            home_score=int(data['home_score']),
            away_score=int(data['away_score']),
            minutes_played=float(data['minutes_played']),
            sport=data.get('sport', 'nba').lower(),
        )
        return {
            'estimated_pace': pace,
            'minutes_played': data['minutes_played'],
            'total_points': int(data['home_score']) + int(data['away_score']),
            'note': 'Possessions estimated as total_points / 1.1 (league avg efficiency)',
        }

    except Exception as e:
        logger.error(f"Pace estimation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
