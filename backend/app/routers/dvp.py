"""
DvP (Defense vs. Position) API Router

Exposes the NBADvPAnalyzer through REST endpoints that integrate
with the existing FastAPI application.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.agents.dvp_agent import DvPAgent


router = APIRouter()
dvp_agent = DvPAgent()


@router.get("/dvp/analysis")
async def get_dvp_analysis(
    high_value_only: bool = Query(False, description="Return only HIGH VALUE plays"),
    num_recent: int = Query(15, description="Number of recent games for rolling average"),
    export_csv: Optional[str] = Query(None, description="Optional CSV export path"),
) -> Dict[str, Any]:
    """
    Run full DvP +EV analysis for today's NBA slate.

    Returns projected player lines with DvP advantage percentages
    and over/under recommendations.
    """
    logger.info("GET /dvp/analysis (high_value_only={}, num_recent={})", high_value_only, num_recent)
    task_type = "high_value_only" if high_value_only else "full_analysis"

    result = await dvp_agent.execute({
        "type": task_type,
        "num_recent": num_recent,
        "export_csv": export_csv,
    })

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/dvp/analysis")
async def run_dvp_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run DvP analysis with a custom slate or parameters.

    Request body keys:
        slate_data       – Full slate dict (games, spreads, O/U)
        type             – "full_analysis" | "high_value_only" | "implied_totals"
        num_recent       – Games window (default 15)
        export_csv       – Optional CSV path
        player_name      – For single_player lookups
        stat_category    – For single_player lookups (PTS, REB, AST, PTS+REB+AST)
    """
    logger.info("POST /dvp/analysis (type={})", data.get("type", "full_analysis"))

    result = await dvp_agent.execute(data)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/dvp/implied-totals")
async def get_implied_totals() -> Dict[str, Any]:
    """
    Compute implied team totals for today's slate.

    Uses the spread and over/under from the configured slate to derive
    each team's implied scoring total.
    """
    result = await dvp_agent.execute({"type": "implied_totals"})

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/dvp/player/{player_name}")
async def get_player_projection(
    player_name: str,
    stat: str = Query("PTS", description="Stat category: PTS, REB, AST, PTS+REB+AST"),
) -> Dict[str, Any]:
    """
    Get DvP projection for a specific player and stat category.
    """
    logger.info("GET /dvp/player/{} (stat={})", player_name, stat)

    result = await dvp_agent.execute({
        "type": "single_player",
        "player_name": player_name,
        "stat_category": stat,
    })

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/dvp/status")
async def get_dvp_agent_status() -> Dict[str, Any]:
    """Return DvP agent status and execution history stats."""
    return dvp_agent.get_agent_status()
