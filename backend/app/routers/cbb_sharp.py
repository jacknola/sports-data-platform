"""
College Basketball Sharp Money & Edge Router

Endpoints:
  GET /api/v1/cbb/games          - All NCAAB games with current odds
  GET /api/v1/cbb/edge           - Edge calculations (devigged true prob vs market)
  GET /api/v1/cbb/sharp          - Sharp money signals (RLM, steam, book divergence)
  GET /api/v1/cbb/line-movement  - Line movement report across all games
  GET /api/v1/cbb/book-divergence- Sharp book vs square book probability gaps
  GET /api/v1/cbb/best-bets      - Top positive-EV CBB bets sorted by edge
  GET /api/v1/cbb/summary        - Dashboard summary combining all signals
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.services.cbb_edge_calculator import CBBEdgeCalculator
from app.services.sharp_money_tracker import SharpMoneyTracker

router = APIRouter()
edge_calc = CBBEdgeCalculator()
sharp_tracker = SharpMoneyTracker()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/cbb/games")
async def get_cbb_games(
    min_bookmakers: int = Query(default=2, description="Minimum number of bookmakers required"),
) -> Dict[str, Any]:
    """
    Return all active NCAAB games with current odds from multiple bookmakers.
    Uses The Odds API (basketball_ncaab) or falls back to mock data.
    """
    try:
        games = await edge_calc.get_games_with_edge(min_edge=0.0)
        if min_bookmakers > 1:
            games = [g for g in games if g.get("bookmaker_count", 0) >= min_bookmakers]
        return {
            "sport": "NCAAB",
            "total_games": len(games),
            "data_source": "the_odds_api" if edge_calc.api_key else "mock_data",
            "games": games,
        }
    except Exception as exc:
        logger.error(f"CBB games error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cbb/edge")
async def get_cbb_edge(
    min_edge: float = Query(default=0.02, description="Minimum edge (0.02 = 2%)"),
    market: Optional[str] = Query(default=None, description="Filter by market: h2h, spreads, totals"),
) -> Dict[str, Any]:
    """
    Return NCAAB bets with positive edge.

    Edge is calculated by:
    1. Devigging bookmaker lines using the multiplicative method
    2. Averaging across sharp books to derive a consensus true probability
    3. Comparing that true probability to the best available market price
    4. Edge = true_prob - market_implied_prob

    Positive edge bets are worth considering.
    """
    try:
        markets = [market] if market else ["h2h", "spreads", "totals"]
        games = await edge_calc.get_games_with_edge(min_edge=min_edge, markets=markets)

        # Flatten all bets with positive edge
        positive_ev_bets = []
        for game in games:
            for market_type, market_data in game.get("markets", {}).items():
                for bet in market_data.get("bets", []):
                    if bet.get("edge", 0) >= min_edge and bet.get("is_positive_ev"):
                        positive_ev_bets.append({
                            "game_id": game["game_id"],
                            "home_team": game["home_team"],
                            "away_team": game["away_team"],
                            "commence_time": game["commence_time"],
                            "market": market_type,
                            **bet,
                        })

        positive_ev_bets.sort(key=lambda b: b["edge"], reverse=True)

        return {
            "sport": "NCAAB",
            "min_edge_filter": min_edge,
            "total_positive_ev_bets": len(positive_ev_bets),
            "methodology": {
                "devig_method": "multiplicative",
                "consensus_source": "sharp_books_preferred",
                "sharp_books": ["pinnacle", "betcris", "circa", "betonlineag"],
            },
            "bets": positive_ev_bets,
        }
    except Exception as exc:
        logger.error(f"CBB edge error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cbb/sharp")
async def get_sharp_money_signals(
    min_score: int = Query(default=1, ge=0, le=4, description="Minimum sharp signal score (0-4)"),
) -> Dict[str, Any]:
    """
    Return sharp money signals for active NCAAB games.

    Signal types detected:
    - **book_divergence**: Sharp books (Pinnacle) and square books (FanDuel, DraftKings)
      have meaningfully different implied probabilities
    - **line_movement**: Line has moved from opening in a notable direction
    - **reverse_line_movement (RLM)**: Public betting % heavily on one side but
      the line is moving the other way – indicates sharp action on the opposite side
    - **spread_discrepancy**: Sharp and square books disagree on the spread number

    Score interpretation:
    - 0 = No signal
    - 1 = Weak signal
    - 2 = Moderate signal
    - 3 = Strong signal
    - 4 = Very strong signal
    """
    try:
        signals = await sharp_tracker.get_sharp_signals(min_score=min_score)
        return {
            "sport": "NCAAB",
            "min_score_filter": min_score,
            "total_signals": len(signals),
            "signal_type_legend": {
                "book_divergence": "Sharp book odds differ from square book odds by 3%+",
                "line_movement": "Opening line has moved from initial post",
                "reverse_line_movement": "Line moves opposite to public betting percentage",
                "spread_discrepancy": "Sharp and square books show different spread numbers",
            },
            "signals": signals,
        }
    except Exception as exc:
        logger.error(f"Sharp money error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cbb/line-movement")
async def get_line_movement() -> Dict[str, Any]:
    """
    Return line movement summary for all active NCAAB games.

    Tracks how spreads and moneylines have moved from opening to current.
    Large moves (1+ points on the spread) are strong sharp indicators.
    """
    try:
        movement = await sharp_tracker.get_line_movement_report()
        return {
            "sport": "NCAAB",
            "total_games": len(movement),
            "movement_data": movement,
        }
    except Exception as exc:
        logger.error(f"Line movement error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cbb/book-divergence")
async def get_book_divergence() -> Dict[str, Any]:
    """
    Return games where sharp books and square books have significantly different
    implied probabilities.

    A divergence of 3%+ (e.g., Pinnacle implies 52% but FanDuel implies 48%)
    represents a potential opportunity – bet with the sharp book's side at
    the square book's price before it corrects.
    """
    try:
        divergences = await sharp_tracker.get_book_divergence()
        return {
            "sport": "NCAAB",
            "divergence_threshold": "3% probability gap between sharp and square books",
            "total_divergences": len(divergences),
            "divergences": divergences,
        }
    except Exception as exc:
        logger.error(f"Book divergence error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cbb/best-bets")
async def get_cbb_best_bets(
    min_edge: float = Query(default=0.03, description="Minimum edge threshold"),
    min_sharp_score: int = Query(default=1, description="Minimum sharp signal score"),
    limit: int = Query(default=10, description="Maximum bets to return"),
) -> Dict[str, Any]:
    """
    Return top NCAAB bets combining edge calculation AND sharp money signals.

    A bet ranks higher when it has both:
    1. Positive edge (true probability > implied market probability)
    2. Sharp money signal (book divergence, RLM, or line movement confirming the side)

    This combination – positive edge + sharp confirmation – is the gold standard
    for identifying value plays in CBB.
    """
    try:
        # Fetch edge data and sharp signals concurrently
        import asyncio
        edge_data, sharp_signals = await asyncio.gather(
            edge_calc.get_games_with_edge(min_edge=min_edge),
            sharp_tracker.get_sharp_signals(min_score=min_sharp_score),
        )

        # Build a lookup: game_id -> list of sharp signal dicts
        sharp_by_game: Dict[str, List[Dict]] = {}
        for sig in sharp_signals:
            gid = sig["game_id"]
            sharp_by_game.setdefault(gid, []).append(sig)

        best_bets = []
        for game in edge_data:
            game_id = game["game_id"]
            game_signals = sharp_by_game.get(game_id, [])

            for market_type, market_data in game.get("markets", {}).items():
                for bet in market_data.get("bets", []):
                    if bet["edge"] < min_edge or not bet["is_positive_ev"]:
                        continue

                    # Find matching sharp signal for this side
                    matching_signals = [
                        s for s in game_signals
                        if s["market"] == market_type
                        and (
                            bet["side"] in s["sharp_side"]
                            or s["sharp_side"] in bet["side"]
                        )
                    ]
                    sharp_score = max((s["score"] for s in matching_signals), default=0)
                    sharp_confirmed = sharp_score >= min_sharp_score

                    # Composite rank: edge * (1 + 0.25 * sharp_score)
                    composite_score = bet["edge"] * (1 + 0.25 * sharp_score)

                    best_bets.append({
                        "game_id": game_id,
                        "home_team": game["home_team"],
                        "away_team": game["away_team"],
                        "commence_time": game["commence_time"],
                        "market": market_type,
                        "side": bet["side"],
                        "true_prob": bet["true_prob"],
                        "fair_odds": bet["fair_odds"],
                        "best_available_odds": bet["best_available_odds"],
                        "best_book": bet["best_book"],
                        "edge": bet["edge"],
                        "ev_per_unit": bet["ev_per_unit"],
                        "kelly_fraction": bet["kelly_fraction"],
                        "sharp_score": sharp_score,
                        "sharp_confirmed": sharp_confirmed,
                        "sharp_signals": [s["signal_types"] for s in matching_signals],
                        "composite_score": round(composite_score, 4),
                    })

        best_bets.sort(key=lambda b: b["composite_score"], reverse=True)
        best_bets = best_bets[:limit]

        return {
            "sport": "NCAAB",
            "filters": {
                "min_edge": min_edge,
                "min_sharp_score": min_sharp_score,
            },
            "total_best_bets": len(best_bets),
            "ranking_method": "edge * (1 + 0.25 * sharp_score)",
            "bets": best_bets,
        }
    except Exception as exc:
        logger.error(f"CBB best bets error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cbb/summary")
async def get_cbb_dashboard_summary() -> Dict[str, Any]:
    """
    Dashboard summary endpoint – returns a combined view of:
    - Active game count
    - Total positive-EV bets available
    - Top sharp signals
    - Top 3 best bets

    Designed for the frontend dashboard widget.
    """
    try:
        import asyncio
        edge_data, sharp_signals, divergences = await asyncio.gather(
            edge_calc.get_games_with_edge(min_edge=0.02),
            sharp_tracker.get_sharp_signals(min_score=1),
            sharp_tracker.get_book_divergence(),
        )

        # Count positive EV bets
        positive_ev_count = sum(
            1
            for game in edge_data
            for m in game.get("markets", {}).values()
            for bet in m.get("bets", [])
            if bet.get("is_positive_ev")
        )

        # Top 3 games by edge
        top_games = sorted(edge_data, key=lambda g: g.get("best_edge", 0), reverse=True)[:3]

        return {
            "sport": "NCAAB",
            "active_games": len(edge_data),
            "positive_ev_bets": positive_ev_count,
            "sharp_signal_count": len(sharp_signals),
            "book_divergence_count": len(divergences),
            "top_signals": sharp_signals[:5],
            "top_games_by_edge": [
                {
                    "game": f"{g['away_team']} @ {g['home_team']}",
                    "best_edge": g["best_edge"],
                    "sharp_books": g.get("sharp_book_count", 0),
                    "commence_time": g["commence_time"],
                }
                for g in top_games
            ],
        }
    except Exception as exc:
        logger.error(f"CBB summary error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
