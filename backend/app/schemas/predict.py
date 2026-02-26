"""
Pydantic schemas for NBA player prop prediction requests and responses.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PropPredictionRequest(BaseModel):
    # ── The 10 model features ─────────────────────────────────────────────────
    usage_rate_season: float = Field(
        ..., description="Season pts/min * 36 proxy (opportunity rate)", ge=0
    )
    l5_form_variance: float = Field(
        ..., description="Variance of pts in last 5 games (hot/cold signal)", ge=0
    )
    expected_mins: float = Field(
        ..., description="Season average minutes played", ge=0
    )
    opp_pace: float = Field(
        100.0, description="Opponent pace (possessions per 48 min)", ge=80, le=130
    )
    opp_def_rtg: float = Field(
        112.0, description="Opponent defensive rating (pts allowed per 100 poss)", ge=90, le=130
    )
    def_vs_position: float = Field(
        0.0, description="Defence vs position delta (+ = weak defence against this position)"
    )
    implied_team_total: float = Field(
        112.5, description="Implied team total points from the game total/spread", ge=80, le=160
    )
    spread: float = Field(
        0.0, description="Game spread (negative = home favourite)"
    )
    rest_advantage: float = Field(
        2.0, description="Days since player's last game (1 = back-to-back, 3+ = rested)", ge=0, le=14
    )
    is_home: int = Field(
        0, description="1 if player's team is home, 0 if away", ge=0, le=1
    )

    # ── Prop line context ─────────────────────────────────────────────────────
    prop_line: float = Field(
        ..., description="Sportsbook points total line (e.g. 24.5)", ge=0
    )
    implied_prob: float = Field(
        ..., description="Market implied probability of the OVER (0–1)", gt=0, lt=1
    )

    # ── Backtesting only — prevents Qdrant data leakage ──────────────────────
    date_limit: Optional[datetime] = Field(
        None,
        description=(
            "Only use Qdrant neighbours with game_date < this datetime. "
            "Pass the current loop date during backtesting to prevent leakage."
        ),
    )

    # ── Optional metadata (stored in logs, not used in model) ────────────────
    player_name: Optional[str] = None
    game_date: Optional[datetime] = None

    model_config = {"json_schema_extra": {
        "example": {
            "usage_rate_season": 22.4,
            "l5_form_variance": 18.5,
            "expected_mins": 34.2,
            "opp_pace": 101.3,
            "opp_def_rtg": 109.8,
            "def_vs_position": 3.1,
            "implied_team_total": 115.0,
            "spread": -4.5,
            "rest_advantage": 2.0,
            "is_home": 1,
            "prop_line": 24.5,
            "implied_prob": 0.524,
            "player_name": "LeBron James",
        }
    }}


class PropPredictionResponse(BaseModel):
    rf_prob: float = Field(..., description="Random Forest baseline probability of OVER")
    posterior_mean: float = Field(..., description="Bayesian posterior mean probability of OVER")
    edge: float = Field(..., description="Edge over market (posterior_mean - implied_prob)")
    p05: float = Field(..., description="95% HDI lower bound")
    p95: float = Field(..., description="95% HDI upper bound")
    kelly_fraction: float = Field(..., description="Fractional Quarter-Kelly bet size (fraction of bankroll)")
    recommendation: str = Field(..., description="OVER | UNDER | PASS")
    n_neighbors_used: int = Field(..., description="Number of Qdrant neighbours used in RF training")
    n_over: int = Field(..., description="Count of OVER outcomes among neighbours")
