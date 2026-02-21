"""
Player Prop endpoints

Three endpoints wired to the full prop analysis pipeline:
  GET  /props/{sport}        — All props with sharp signal analysis
  GET  /props/{sport}/best   — Top props by EV, filtered by min_edge
  POST /props/analyze        — Full pipeline on a single prop

Consistent with bets.py / odds.py patterns.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger

from app.services.bayesian import BayesianAnalyzer
from app.services.prop_analyzer import PropAnalyzer
from app.services.prop_probability import PropProbabilityModel
from app.services.multivariate_kelly import (
    BettingOpportunity,
    MultivariateKellyOptimizer,
    american_to_decimal,
)

router = APIRouter()

_bayesian = BayesianAnalyzer()
_prop_analyzer = PropAnalyzer()
_prop_model = PropProbabilityModel()
_kelly_optimizer = MultivariateKellyOptimizer(kelly_scale=0.5, min_edge=0.03)


# ---------------------------------------------------------------------------
# Sample slate — mirrors the stub in odds.py; replace with Odds API call
# ---------------------------------------------------------------------------

def _get_sample_props(sport: str) -> List[Dict]:
    """
    Placeholder prop slate. Structure matches what a real Odds API response
    would be normalized to. Replace the body with an actual API call.
    """
    if sport.lower() != 'nba':
        return []

    return [
        {
            'player_id': 'lebron_james',
            'player_name': 'LeBron James',
            'team': 'LAL',
            'opponent': 'PHX',
            'game_id': 'nba_lal_phx_20260221',
            'stat_type': 'points',
            'line': 25.5,
            'over_odds': -115,
            'under_odds': -105,
            'open_over_odds': -110,
            'open_under_odds': -110,
            'open_line': 25.5,
            'over_ticket_pct': 0.71,
            'over_money_pct': 0.55,
            'season_avg': 24.8,
            'last_5_avg': 27.2,
            'usage_rate': 0.31,
            'usage_trend': 0.02,
            'injury_status': 'ACTIVE',
            'rest_days': 2,
            'is_home': True,
            'team_pace': 101.5,
            'opponent_pace': 99.0,
            'opponent_def_rating': 115.2,
        },
        {
            'player_id': 'nikola_jokic',
            'player_name': 'Nikola Jokic',
            'team': 'DEN',
            'opponent': 'GSW',
            'game_id': 'nba_den_gsw_20260221',
            'stat_type': 'pra',
            'line': 52.5,
            'over_odds': -110,
            'under_odds': -110,
            'open_over_odds': -108,
            'open_under_odds': -112,
            'open_line': 52.5,
            'over_ticket_pct': 0.58,
            'over_money_pct': 0.62,
            'season_avg': 51.3,
            'last_5_avg': 54.6,
            'usage_rate': 0.33,
            'usage_trend': 0.01,
            'injury_status': 'ACTIVE',
            'rest_days': 1,
            'is_home': False,
            'team_pace': 98.8,
            'opponent_pace': 102.1,
            'opponent_def_rating': 112.0,
        },
        {
            'player_id': 'tyrese_haliburton',
            'player_name': 'Tyrese Haliburton',
            'team': 'IND',
            'opponent': 'MIA',
            'game_id': 'nba_ind_mia_20260221',
            'stat_type': 'assists',
            'line': 9.5,
            'over_odds': -120,
            'under_odds': 100,
            'open_over_odds': -110,
            'open_under_odds': -110,
            'open_line': 9.5,
            'over_ticket_pct': 0.68,
            'over_money_pct': 0.49,
            'season_avg': 9.1,
            'last_5_avg': 8.4,
            'usage_rate': 0.25,
            'usage_trend': -0.02,
            'injury_status': 'QUESTIONABLE',
            'rest_days': 0,
            'is_home': False,
            'team_pace': 100.2,
            'opponent_pace': 97.5,
            'opponent_def_rating': 110.8,
        },
        {
            'player_id': 'jayson_tatum',
            'player_name': 'Jayson Tatum',
            'team': 'BOS',
            'opponent': 'MIL',
            'game_id': 'nba_bos_mil_20260221',
            'stat_type': 'points',
            'line': 27.5,
            'over_odds': -108,
            'under_odds': -112,
            'open_over_odds': -115,
            'open_under_odds': -105,
            'open_line': 27.5,
            'over_ticket_pct': 0.82,
            'over_money_pct': 0.80,
            'season_avg': 26.9,
            'last_5_avg': 25.1,
            'usage_rate': 0.34,
            'usage_trend': -0.01,
            'injury_status': 'ACTIVE',
            'rest_days': 3,
            'is_home': True,
            'team_pace': 99.1,
            'opponent_pace': 100.4,
            'opponent_def_rating': 111.5,
        },
    ]


def _build_prop_analysis(prop: Dict) -> Dict:
    """
    Run the full prop analysis pipeline on a single prop dict.

    Pipeline:
      1. PropProbabilityModel.project()      — distribution + edge
      2. PropAnalyzer.analyze_prop()         — sharp signal detection
      3. BayesianAnalyzer.compute_posterior() — Bayesian posterior + Kelly
    """
    player_data = {
        'player_id':     prop['player_id'],
        'player_name':   prop['player_name'],
        'stat_type':     prop['stat_type'],
        'line':          prop['line'],
        'season_avg':    prop['season_avg'],
        'last_5_avg':    prop['last_5_avg'],
        'usage_rate':    prop['usage_rate'],
        'usage_trend':   prop['usage_trend'],
        'injury_status': prop['injury_status'],
        'rest_days':     prop['rest_days'],
    }
    game_context = {
        'team_pace':            prop['team_pace'],
        'opponent_pace':        prop['opponent_pace'],
        'opponent_def_rating':  prop['opponent_def_rating'],
        'is_home':              prop['is_home'],
    }

    # 1. Projection
    projection = _prop_model.project(
        player_data, game_context,
        over_odds=prop['over_odds'],
        under_odds=prop['under_odds'],
    )

    # 2. Sharp signal analysis (static one-shot)
    sharp = PropAnalyzer.analyze_prop(
        prop_id=f"{prop['player_id']}:{prop['stat_type']}",
        player_name=prop['player_name'],
        stat_type=prop['stat_type'],
        open_line=prop['open_line'],
        current_line=prop['line'],
        over_ticket_pct=prop['over_ticket_pct'],
        over_money_pct=prop['over_money_pct'],
        open_over_odds=prop['open_over_odds'],
        current_over_odds=prop['over_odds'],
        open_under_odds=prop['open_under_odds'],
        current_under_odds=prop['under_odds'],
    )

    # 3. Bayesian posterior
    bayesian_input = projection.to_bayesian_input()
    bayesian_input['features']['injury_status'] = prop['injury_status']
    bayesian_input['features']['is_home'] = prop['is_home']
    bayesian_input['current_american_odds'] = (
        prop['over_odds'] if projection.best_side == 'over' else prop['under_odds']
    )
    posterior = _bayesian.compute_posterior(bayesian_input)

    # Sharp signal boost on Kelly (mirrors BettingOpportunity.sharp_signal_boost)
    signal_boost = posterior['edge'] * 0.1 if sharp['sharp_signals'] else 0.0
    decimal_odds = american_to_decimal(bayesian_input['current_american_odds'])
    kelly = _bayesian.calculate_kelly_criterion(posterior['posterior_p'], decimal_odds)

    return {
        'player_name':      prop['player_name'],
        'team':             prop['team'],
        'opponent':         prop['opponent'],
        'game_id':          prop['game_id'],
        'stat_type':        prop['stat_type'],
        'line':             prop['line'],
        'best_side':        projection.best_side,
        'over_odds':        prop['over_odds'],
        'under_odds':       prop['under_odds'],
        # Model
        'projected_mean':   projection.projected_mean,
        'projected_std':    projection.projected_std,
        'model_p_over':     projection.model_p_over,
        'model_p_under':    projection.model_p_under,
        'model_edge_over':  projection.model_edge_over,
        'model_edge_under': projection.model_edge_under,
        # Sharp signals
        'sharp_signals':    sharp['sharp_signals'],
        'sharp_side':       sharp['sharp_side'],
        'signal_confidence': sharp['signal_confidence'],
        'true_over_prob':   sharp['true_over_prob'],
        'true_under_prob':  sharp['true_under_prob'],
        'ev_edge_pct':      sharp['ev_edge_pct'],
        'is_positive_ev':   sharp['is_positive_ev'],
        # Bayesian
        'posterior_p':      posterior['posterior_p'],
        'fair_american_odds': posterior['fair_american_odds'],
        'bayesian_edge':    posterior['edge'],
        'confidence_interval': posterior['confidence_interval'],
        'adjustments':      posterior['adjustments'],
        # Sizing
        'kelly_fraction':   round(kelly, 4),
        'sharp_signal_boost': round(signal_boost, 4),
        'method':           'prop_model_bayesian',
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/props/{sport}")
async def get_props(sport: str) -> Dict[str, Any]:
    """
    Get all props for a sport with sharp signal analysis applied.

    Returns the full slate including model projection, sharp signals,
    and Bayesian posterior for each prop line.
    """
    logger.info(f"Fetching props for {sport}")
    try:
        raw_props = _get_sample_props(sport)

        if not raw_props:
            return {
                'sport': sport,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'total_props': 0,
                'props': [],
            }

        analyzed = [_build_prop_analysis(p) for p in raw_props]

        return {
            'sport': sport.upper(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_props': len(analyzed),
            'props': analyzed,
        }

    except Exception as e:
        logger.error(f"Error fetching props for {sport}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/props/{sport}/best")
async def get_best_props(
    sport: str,
    min_edge: float = Query(default=0.03, description="Minimum Bayesian edge threshold"),
    limit: int = Query(default=10, description="Maximum props to return"),
    require_sharp: bool = Query(default=False, description="Only return props with sharp signals"),
) -> List[Dict[str, Any]]:
    """
    Get best player props by EV + sharp signal, filtered by min_edge.

    Mirrors GET /bets endpoint — same filtering and sorting logic.
    Optional require_sharp=true restricts to props with detected RLM/STEAM/FREEZE/JUICE_SHIFT.
    """
    logger.info(f"Getting best props: sport={sport} min_edge={min_edge} require_sharp={require_sharp}")
    try:
        raw_props = _get_sample_props(sport)

        if not raw_props:
            return []

        analyzed = [_build_prop_analysis(p) for p in raw_props]

        # Filter
        filtered = [
            p for p in analyzed
            if p['bayesian_edge'] >= min_edge
            and p['is_positive_ev']
            and (not require_sharp or p['sharp_signals'])
        ]

        # Sort by Bayesian edge descending (consistent with bets.py)
        filtered.sort(key=lambda x: x['bayesian_edge'], reverse=True)

        return filtered[:limit]

    except Exception as e:
        logger.error(f"Error getting best props for {sport}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/props/analyze")
async def analyze_prop(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full prop analysis pipeline on a single submitted prop.

    Mirrors POST /bayesian — same input style, returns full prop analysis
    including projection, sharp signals, Bayesian posterior, and Kelly sizing.

    Expected input:
    {
        "player_id": "jayson_tatum",
        "player_name": "Jayson Tatum",
        "team": "BOS",
        "opponent": "MIL",
        "game_id": "nba_bos_mil_20260221",
        "stat_type": "points",
        "line": 27.5,
        "over_odds": -108,
        "under_odds": -112,
        "open_over_odds": -115,
        "open_under_odds": -105,
        "open_line": 27.5,
        "over_ticket_pct": 0.82,
        "over_money_pct": 0.80,
        "season_avg": 26.9,
        "last_5_avg": 25.1,
        "usage_rate": 0.34,
        "usage_trend": -0.01,
        "injury_status": "ACTIVE",
        "rest_days": 3,
        "is_home": true,
        "team_pace": 99.1,
        "opponent_pace": 100.4,
        "opponent_def_rating": 111.5
    }
    """
    required = [
        'player_id', 'player_name', 'stat_type', 'line',
        'over_odds', 'under_odds', 'season_avg',
    ]
    missing = [f for f in required if f not in data]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required fields: {missing}"
        )

    # Apply defaults for optional fields so _build_prop_analysis always has them
    defaults = {
        'team': '',
        'opponent': '',
        'game_id': f"{data['player_id']}:{data['stat_type']}",
        'open_line': data['line'],
        'open_over_odds': data['over_odds'],
        'open_under_odds': data['under_odds'],
        'over_ticket_pct': 0.50,
        'over_money_pct': 0.50,
        'last_5_avg': data['season_avg'],
        'usage_rate': 0.25,
        'usage_trend': 0.0,
        'injury_status': 'ACTIVE',
        'rest_days': 2,
        'is_home': False,
        'team_pace': 100.0,
        'opponent_pace': 100.0,
        'opponent_def_rating': 113.5,
    }
    prop = {**defaults, **data}

    try:
        result = _build_prop_analysis(prop)
        return result
    except Exception as e:
        logger.error(f"Prop analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
