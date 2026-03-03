"""
Best bets endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from app.services.bayesian import BayesianAnalyzer
from app.services.nba_ml_predictor import NBAMLPredictor
from app.services.bet_tracker import BetTracker

router = APIRouter()
bayesian_analyzer = BayesianAnalyzer()
nba_predictor = NBAMLPredictor()
_bet_tracker = BetTracker()


@router.get("/bets")
async def get_best_bets(
    sport: str = Query(default="nba", description="Sport to analyze"),
    min_edge: float = Query(default=0.05, description="Minimum edge threshold"),
    limit: int = Query(default=10, description="Maximum number of bets to return"),
) -> List[Dict[str, Any]]:
    """
    Get best betting opportunities with ML predictions

    Args:
        sport: Sport to analyze (nba, nfl, etc.)
        min_edge: Minimum edge required
        limit: Maximum bets to return

    Returns:
        List of best bet opportunities with EV and Kelly Criterion
    """
    logger.info(f"Getting best bets for {sport} with min edge {min_edge}")

    try:
        if sport.lower() == "nba":
            return await _get_nba_best_bets(min_edge, limit)
        else:
            # Fallback for other sports
            return [
                {
                    "sport": sport,
                    "selection_id": "bet_1",
                    "description": "Example bet",
                    "edge": 0.05,
                    "probability": 0.55,
                    "current_odds": -110,
                }
            ]

    except Exception as e:
        logger.error(f"Error getting best bets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bayesian")
async def run_bayesian_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Bayesian analysis on a betting selection

    Args:
        data: Selection data with devig_prob, implied_prob, features

    Returns:
        Bayesian analysis results
    """
    try:
        result = bayesian_analyzer.compute_posterior(data)
        return result
    except Exception as e:
        logger.error(f"Bayesian analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions/nba/today")
async def get_nba_predictions_today() -> Dict[str, Any]:
    """
    Get NBA predictions for today's games using ML models

    Returns:
        Predictions with probabilities and recommendations
    """
    try:
        predictions = await nba_predictor.predict_today_games("nba")

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sport": "NBA",
            "total_games": len(predictions),
            "predictions": predictions,
            "method": "xgboost",
        }
    except Exception as e:
        logger.error(f"NBA prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_nba_best_bets(min_edge: float, limit: int) -> List[Dict[str, Any]]:
    """
    Process NBA predictions and return best bets sorted by edge.
    """
    game_predictions = await nba_predictor.predict_today_games("nba")
    best_bets = []

    for pred in game_predictions:
        # Process Moneyline
        ml_bet = _process_nba_moneyline(pred, min_edge)
        if ml_bet:
            best_bets.append(ml_bet)

        # Process Total (Over/Under)
        total_bet = _process_nba_total(pred)
        if total_bet:
            best_bets.append(total_bet)

    # Sort by edge and limit
    return sorted(best_bets, key=lambda x: x["edge"], reverse=True)[:limit]


def _process_nba_moneyline(
    pred: Dict[str, Any], min_edge: float
) -> Optional[Dict[str, Any]]:
    """Extract moneyline bet from prediction if it meets the edge criteria."""
    ev_data = pred.get("expected_value", {})
    home_ev = ev_data.get("home_ev", 0)

    if home_ev <= min_edge:
        return None

    best_bet_selection = ev_data.get("best_bet")
    if not best_bet_selection:
        return None

    return {
        "sport": "NBA",
        "game": f"{pred['away_team']} @ {pred['home_team']}",
        "market": "Moneyline",
        "selection": best_bet_selection,
        "edge": ev_data.get(f"{best_bet_selection}_ev"),
        "probability": pred.get("moneyline_prediction", {}).get("home_win_prob", 0),
        "confidence": pred.get("confidence", 0),
        "current_odds": ev_data.get(f"{best_bet_selection}_odds"),
        "kelly_fraction": pred.get("kelly_criterion", 0),
        "method": "ml_xgboost",
        "ml_prediction": pred,
    }


def _process_nba_total(pred: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract total (over/under) bet from prediction if available."""
    uo_pred = pred.get("underover_prediction")
    if not uo_pred:
        return None

    over_prob = uo_pred.get("over_prob", 0.5)
    # Strong prediction threshold check (hardcoded 0.1 delta from 0.5 as per original code)
    if abs(over_prob - 0.5) <= 0.1:
        return None

    recommendation = uo_pred.get("recommendation")
    probability = over_prob if recommendation == "over" else uo_pred.get("under_prob")

    return {
        "sport": "NBA",
        "game": f"{pred['away_team']} @ {pred['home_team']}",
        "market": f"Total {uo_pred.get('total_points')}",
        "selection": recommendation,
        "edge": abs(over_prob - 0.5),
        "probability": probability,
        "confidence": abs(over_prob - 0.5) * 2,
        "method": "ml_xgboost",
        "ml_prediction": pred,
    }


# ---------------------------------------------------------------------------
# Bet result tracking endpoints
# ---------------------------------------------------------------------------


@router.get("/bets/tracked")
async def get_tracked_bets(
    sport: Optional[str] = Query(None, description="Filter by sport (ncaab, nba, all)"),
    status: Optional[str] = Query(None, description="Filter by status: pending, won, lost, push, void"),
) -> List[Dict[str, Any]]:
    """Return all bets saved by the portfolio optimizer for win/loss tracking.

    Supports filtering by sport and status. Returns all bets sorted newest-first.
    """
    try:
        import sqlite3

        db_path = _bet_tracker.LOCAL_DB_PATH
        _bet_tracker._init_sqlite()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM bets WHERE 1=1"
            params: List[Any] = []
            if sport and sport.lower() != "all":
                query += " AND sport = ?"
                params.append(sport.lower())
            if status:
                query += " AND status = ?"
                params.append(status.lower())
            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to fetch tracked bets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bets/tracked")
async def save_tracked_bet(data: Dict[str, Any]) -> Dict[str, Any]:
    """Manually save a bet for tracking.

    Required: sport, side, market, odds, bet_size. Optional: game_id, line, edge, book, date.
    """
    try:
        bet_id = _bet_tracker.save_bet(data)
        return {"bet_id": bet_id, "status": "saved"}
    except Exception as e:
        logger.error(f"Failed to save tracked bet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bets/{bet_id}/settle")
async def settle_bet(bet_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Mark a pending bet as won, lost, push, or void.

    Body: { "status": "won" | "lost" | "push" | "void", "clv": float (optional) }
    """
    valid_statuses = ("won", "lost", "push", "void")
    status = data.get("status", "").lower()
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of: {', '.join(valid_statuses)}",
        )
    clv = data.get("clv")
    try:
        _bet_tracker.update_bet_result(bet_id, status, clv=clv)
        logger.info(f"Settled bet {bet_id}: {status}")
        return {"bet_id": bet_id, "status": status}
    except Exception as e:
        logger.error(f"Failed to settle bet {bet_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bets/performance")
async def get_performance_metrics(
    sport: Optional[str] = Query(None, description="Filter by sport or 'all'"),
) -> Dict[str, Any]:
    """Win/loss performance metrics for all settled bets.

    Returns: wins, losses, pushes, win_rate, ROI, units, avg_clv, pending_bets.
    """
    try:
        import sqlite3

        db_path = _bet_tracker.LOCAL_DB_PATH
        _bet_tracker._init_sqlite()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM bets WHERE status != 'pending'"
            params: List[Any] = []
            if sport and sport.lower() != "all":
                query += " AND sport = ?"
                params.append(sport.lower())
            cursor.execute(query, params)
            rows = [dict(r) for r in cursor.fetchall()]

        metrics = _bet_tracker._calculate_metrics(rows)

        # Count pending separately
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            pq = "SELECT COUNT(*) FROM bets WHERE status = 'pending'"
            pp: List[Any] = []
            if sport and sport.lower() != "all":
                pq += " AND sport = ?"
                pp.append(sport.lower())
            cursor.execute(pq, pp)
            metrics["pending_bets"] = cursor.fetchone()[0]

        return metrics
    except Exception as e:
        logger.error(f"Failed to fetch performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
