"""
Player Props Prediction API
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.player_prop_predictor import PlayerPropPredictor


class PlayerPropRequest(BaseModel):
    player: str = Field(..., description="Player name")
    market: str = Field(..., description="Stat market, e.g., points, assists, rebounds, pra, threes")
    line: float = Field(..., description="Sportsbook line, e.g., 24.5")
    history: Optional[List[float]] = Field(default=None, description="Recent game stat values, most-recent first")
    side_odds: Optional[Dict[str, float]] = Field(default=None, description='American odds, e.g., {"over": -110, "under": -110}')
    adjustment_pct: float = Field(default=0.0, description="Additive adjustment to mean as percent (+0.05 => +5%)")
    weight_lambda: float = Field(default=0.1, ge=0.0, description="Exponential decay factor; larger emphasizes recency")
    kelly_fraction_default: float = Field(default=0.5, ge=0.0, le=1.0, description="Fractional Kelly to apply to stake")


router = APIRouter()
_predictor = PlayerPropPredictor()


@router.post("/player-props/predict")
async def predict_player_prop(req: PlayerPropRequest) -> Dict[str, Any]:
    try:
        result = _predictor.predict_over_under(
            player=req.player,
            market=req.market,
            line=req.line,
            history=req.history,
            side_odds=req.side_odds,
            adjustment_pct=req.adjustment_pct,
            weight_lambda=req.weight_lambda,
            kelly_fraction_default=req.kelly_fraction_default,
        )
        return result
    except Exception as e:
        logger.error(f"Player prop prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
