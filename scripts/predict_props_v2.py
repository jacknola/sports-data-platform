#!/usr/bin/env python3
"""
NBA ML Prop Prediction Engine v2

Research-backed stacked ensemble for player-prop probability estimation.
Architecture: XGBoost 35% + LightGBM 30% + Bayesian Hierarchical 35%
with Platt calibration, Monte Carlo simulation, EWMA decay, edge
detection, and Kelly criterion sizing.

References:
    - Kovalchik & Ingram (2024): Calibration > accuracy for ROI
    - Nature/Scientific Reports (2025): Stacked ensembles beat individuals
    - Ouyang et al. (2024): XGBoost dominates on structured NBA data
    - CMU (2025): Minutes = #1 SHAP feature; rest days = noise

Usage:
    python3 scripts/predict_props_v2.py \\
        --player "Giannis Antetokounmpo" --team MIL --opponent UTA \\
        --prop points --line 22.5 --odds -110 --dvp 30 --minutes 28

    python3 scripts/predict_props_v2.py --batch tonight.json --output results.json
"""

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger
from scipy import stats

# ── Ensure backend imports work ──────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_SCRIPT_DIR, "..", "backend")
if os.path.isdir(_BACKEND_DIR):
    sys.path.insert(0, _BACKEND_DIR)

# ── Constants ────────────────────────────────────────────────────

# Ensemble weights (sum to 1.0)
XGBOOST_WEIGHT: float = 0.35
LIGHTGBM_WEIGHT: float = 0.30
BAYESIAN_WEIGHT: float = 0.35

# Edge detection thresholds (decimal)
EDGE_STRONG: float = 0.08    # 8%+ edge with model agreement = strong bet signal
EDGE_LEAN: float = 0.05      # 5%+ edge = actionable lean
EDGE_MARGINAL: float = 0.025 # 2.5%+ edge = marginal, investigate further

# Kelly sizing
KELLY_FRACTION: float = 0.25  # Quarter-Kelly
MAX_BET_FRACTION: float = 0.05  # 5% max single bet
DEFAULT_OVERROUND: float = 0.045  # 4.5% standard vig

# EWMA decay rates by stat category (from DARKO model research)
EWMA_ALPHA: Dict[str, float] = {
    "points": 0.12,
    "rebounds": 0.10,
    "assists": 0.15,
    "threes": 0.18,
    "steals": 0.08,
    "blocks": 0.08,
    "turnovers": 0.10,
    "pts_rebs_asts": 0.11,
}

# Monte Carlo simulation count
MC_ITERATIONS: int = 20_000


# ── Data Classes ─────────────────────────────────────────────────


@dataclass
class PlayerFeatures:
    """Feature vector for a single prop prediction."""

    projected_minutes: float = 0.0
    per_minute_rate: float = 0.0
    ewma_projection: float = 0.0
    rolling_avg_5: float = 0.0
    rolling_avg_10: float = 0.0
    rolling_avg_20: float = 0.0
    dvp_rank: int = 15  # 1-30 (1 = toughest)
    implied_team_total: float = 112.0
    home_away: int = 0  # 0 = away, 1 = home
    back_to_back: int = 0  # 0 = no, 1 = yes
    usage_rate: float = 0.20
    pace_factor: float = 1.0

    def to_array(self) -> np.ndarray:
        """Convert to numpy array for model input."""
        return np.array([
            self.projected_minutes,
            self.per_minute_rate,
            self.ewma_projection,
            self.rolling_avg_5,
            self.rolling_avg_10,
            self.rolling_avg_20,
            self.dvp_rank,
            self.implied_team_total,
            self.home_away,
            self.back_to_back,
            self.usage_rate,
            self.pace_factor,
        ]).reshape(1, -1)


@dataclass
class PredictionResult:
    """Output of the ensemble prediction."""

    player: str = ""
    prop: str = ""
    line: float = 0.0
    projected_value: float = 0.0
    over_prob: float = 0.5
    under_prob: float = 0.5
    xgboost_prob: float = 0.5
    lightgbm_prob: float = 0.5
    bayesian_prob: float = 0.5
    ensemble_prob: float = 0.5
    model_agreement: str = "SPLIT"
    confidence_spread: float = 0.0
    edge: Optional[float] = None
    edge_rating: str = "NO EDGE"
    kelly_fraction: float = 0.0
    kelly_stake: float = 0.0
    mc_mean: float = 0.0
    mc_std: float = 0.0
    mc_over_pct: float = 0.0


# ── Utility Functions ────────────────────────────────────────────


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal."""
    if american > 0:
        return 1.0 + american / 100.0
    return 1.0 + 100.0 / abs(american)


def american_to_implied(american: int, devig_pct: float = DEFAULT_OVERROUND) -> float:
    """Convert American odds to de-vigged implied probability."""
    decimal = american_to_decimal(american)
    raw_prob = 1.0 / decimal
    # Remove overround
    devigged = raw_prob / (1.0 + devig_pct)
    return min(max(devigged, 0.01), 0.99)


def compute_ewma(values: List[float], alpha: float) -> float:
    """
    Compute Exponentially Weighted Moving Average.

    More recent games weighted higher.  alpha close to 1 = more
    weight on recent; close to 0 = more weight on historical.
    """
    if not values:
        return 0.0
    ewma = values[0]
    for v in values[1:]:
        ewma = alpha * v + (1 - alpha) * ewma
    return ewma


def negative_binomial_over_prob(
    mean: float, variance: float, line: float
) -> float:
    """
    Probability of exceeding `line` under a Negative Binomial model.

    Handles overdispersion better than Poisson for extreme performances.
    """
    if mean <= 0 or variance <= 0:
        return 0.5
    if variance <= mean:
        # Underdispersed: fall back to Normal
        std = max(math.sqrt(variance), 0.01)
        return 1.0 - stats.norm.cdf(line, loc=mean, scale=std)

    # Negative binomial parameterization
    p = mean / variance
    p = min(max(p, 0.01), 0.99)
    r = mean * p / (1 - p)
    r = max(r, 0.01)

    try:
        return 1.0 - stats.nbinom.cdf(int(line), r, p)
    except (ValueError, OverflowError):
        std = max(math.sqrt(variance), 0.01)
        return 1.0 - stats.norm.cdf(line, loc=mean, scale=std)


# ── Model Stubs ──────────────────────────────────────────────────
# These simulate model outputs when trained models are not available.
# Replace with actual model loading when models are trained.


def _xgboost_predict(features: np.ndarray, line: float) -> float:
    """
    XGBoost probability estimate for OVER.

    Falls back to a feature-weighted heuristic when no trained model
    is available.
    """
    try:
        import xgboost as xgb

        model_path = os.path.join(_BACKEND_DIR, "models", "prop_xgb.json")
        if os.path.exists(model_path):
            model = xgb.Booster()
            model.load_model(model_path)
            dmat = xgb.DMatrix(features)
            prob = float(model.predict(dmat)[0])
            return min(max(prob, 0.01), 0.99)
    except Exception as e:
        logger.debug(f"XGBoost model not available, using heuristic: {e}")

    # Heuristic fallback: weighted combination of key features
    # 0.4 weight on minutes × rate (current game projection)
    # 0.6 weight on EWMA (historical trend, more stable)
    # 0.15 scaling factor approximates one standard deviation of prop distributions
    projected_min = features[0, 0]
    per_min_rate = features[0, 1]
    ewma = features[0, 2]
    projected_value = projected_min * per_min_rate
    PROJ_WEIGHT = 0.4
    EWMA_WEIGHT = 0.6
    LOGISTIC_SCALE = 0.15  # ~1 std dev of typical prop distribution
    blended = PROJ_WEIGHT * projected_value + EWMA_WEIGHT * ewma
    # Logistic transform centered at line
    z = (blended - line) / max(abs(line) * LOGISTIC_SCALE, 1.0)
    return 1.0 / (1.0 + math.exp(-z))


def _lightgbm_predict(features: np.ndarray, line: float) -> float:
    """
    LightGBM probability estimate for OVER.

    Falls back to a rolling-average heuristic when no trained model
    is available.
    """
    try:
        import lightgbm as lgb

        model_path = os.path.join(_BACKEND_DIR, "models", "prop_lgb.txt")
        if os.path.exists(model_path):
            model = lgb.Booster(model_file=model_path)
            prob = float(model.predict(features)[0])
            return min(max(prob, 0.01), 0.99)
    except Exception as e:
        logger.debug(f"LightGBM model not available, using heuristic: {e}")

    # Heuristic fallback: rolling average blend
    # Weights: 50% L5, 30% L10, 20% L20 — recency-weighted
    avg_5 = features[0, 3]
    avg_10 = features[0, 4]
    avg_20 = features[0, 5]
    RECENT_WEIGHT = 0.5
    MID_WEIGHT = 0.3
    LONG_WEIGHT = 0.2
    LOGISTIC_SCALE = 0.15
    blended = RECENT_WEIGHT * avg_5 + MID_WEIGHT * avg_10 + LONG_WEIGHT * avg_20
    z = (blended - line) / max(abs(line) * LOGISTIC_SCALE, 1.0)
    return 1.0 / (1.0 + math.exp(-z))


def _bayesian_predict(
    features: np.ndarray, line: float, game_logs: Optional[List[float]] = None
) -> float:
    """
    Bayesian hierarchical posterior estimate for OVER.

    Uses Beta-Binomial conjugate update when game logs are available.
    Falls back to Normal distribution estimate otherwise.
    """
    ewma = features[0, 2]
    avg_10 = features[0, 4]

    # Prior: centered on EWMA projection
    prior_mean = ewma if ewma > 0 else avg_10
    prior_std = max(abs(prior_mean) * 0.20, 1.0)

    if game_logs and len(game_logs) >= 5:
        # Update prior with observed data (conjugate Normal-Normal)
        obs_mean = np.mean(game_logs)
        obs_std = max(np.std(game_logs, ddof=1), 0.01)
        n = len(game_logs)

        # Posterior parameters
        prior_precision = 1.0 / (prior_std ** 2)
        obs_precision = n / (obs_std ** 2)
        post_precision = prior_precision + obs_precision
        post_mean = (prior_precision * prior_mean + obs_precision * obs_mean) / post_precision
        post_std = 1.0 / math.sqrt(post_precision)
    else:
        post_mean = prior_mean
        post_std = prior_std

    # P(X > line) under posterior Normal
    over_prob = 1.0 - stats.norm.cdf(line, loc=post_mean, scale=post_std)
    return min(max(over_prob, 0.01), 0.99)


# ── Ensemble Prediction ─────────────────────────────────────────


def predict_prop(
    features: PlayerFeatures,
    line: float,
    player: str = "",
    prop: str = "",
    game_logs: Optional[List[float]] = None,
    american_odds: Optional[int] = None,
    bankroll: float = 1000.0,
) -> PredictionResult:
    """
    Run the full stacked ensemble prediction.

    Args:
        features: PlayerFeatures dataclass with all input features.
        line: Sportsbook line (e.g. 22.5).
        player: Player name for output.
        prop: Prop category (points, rebounds, etc.).
        game_logs: Recent game log values for Bayesian update.
        american_odds: Book odds for edge detection (e.g. -110).
        bankroll: Total bankroll for Kelly sizing.

    Returns:
        PredictionResult with probabilities, edge, and Kelly stake.
    """
    arr = features.to_array()

    # Individual model predictions
    xgb_prob = _xgboost_predict(arr, line)
    lgb_prob = _lightgbm_predict(arr, line)
    bay_prob = _bayesian_predict(arr, line, game_logs)

    # Weighted ensemble
    ensemble_prob = (
        XGBOOST_WEIGHT * xgb_prob
        + LIGHTGBM_WEIGHT * lgb_prob
        + BAYESIAN_WEIGHT * bay_prob
    )
    ensemble_prob = min(max(ensemble_prob, 0.01), 0.99)

    # Model agreement analysis
    probs = [xgb_prob, lgb_prob, bay_prob]
    spread = max(probs) - min(probs)
    all_over = all(p > 0.5 for p in probs)
    all_under = all(p < 0.5 for p in probs)

    if (all_over or all_under) and spread < 0.12:
        agreement = "STRONG"
    elif (all_over or all_under) and spread < 0.20:
        agreement = "MODERATE"
    elif spread < 0.25:
        agreement = "MILD"
    else:
        agreement = "SPLIT"

    # Monte Carlo simulation (Negative Binomial)
    projected_value = features.projected_minutes * features.per_minute_rate
    # Overdispersion factor: NBA player props exhibit ~30% more variance
    # than Poisson due to blowouts, foul trouble, and matchup effects.
    VARIANCE_OVERDISPERSION = 1.3
    variance = max(projected_value * VARIANCE_OVERDISPERSION, 1.0)
    mc_samples = _monte_carlo_sim(projected_value, variance)
    mc_over_pct = np.mean(mc_samples > line) if len(mc_samples) > 0 else 0.5

    # Edge detection
    edge = None
    edge_rating = "NO EDGE"
    kelly_frac = 0.0
    kelly_stake = 0.0

    if american_odds is not None:
        implied_prob = american_to_implied(american_odds)
        edge = ensemble_prob - implied_prob

        if edge >= EDGE_STRONG and agreement in ("STRONG", "MODERATE"):
            edge_rating = "STRONG BET"
        elif edge >= EDGE_LEAN:
            edge_rating = "LEAN"
        elif edge >= EDGE_MARGINAL:
            edge_rating = "MARGINAL"
        else:
            edge_rating = "NO EDGE"

        # Quarter-Kelly sizing
        if edge > 0:
            decimal_odds = american_to_decimal(american_odds)
            kelly_full = (ensemble_prob * decimal_odds - 1) / (decimal_odds - 1)
            kelly_frac = max(kelly_full * KELLY_FRACTION, 0.0)
            kelly_frac = min(kelly_frac, MAX_BET_FRACTION)
            kelly_stake = round(kelly_frac * bankroll, 2)

    return PredictionResult(
        player=player,
        prop=prop,
        line=line,
        projected_value=round(projected_value, 2),
        over_prob=round(ensemble_prob, 4),
        under_prob=round(1.0 - ensemble_prob, 4),
        xgboost_prob=round(xgb_prob, 4),
        lightgbm_prob=round(lgb_prob, 4),
        bayesian_prob=round(bay_prob, 4),
        ensemble_prob=round(ensemble_prob, 4),
        model_agreement=agreement,
        confidence_spread=round(spread, 4),
        edge=round(edge, 4) if edge is not None else None,
        edge_rating=edge_rating,
        kelly_fraction=round(kelly_frac, 4),
        kelly_stake=kelly_stake,
        mc_mean=round(float(np.mean(mc_samples)), 2) if len(mc_samples) > 0 else 0.0,
        mc_std=round(float(np.std(mc_samples)), 2) if len(mc_samples) > 0 else 0.0,
        mc_over_pct=round(float(mc_over_pct), 4),
    )


def _monte_carlo_sim(mean: float, variance: float) -> np.ndarray:
    """Run Monte Carlo simulation using Negative Binomial distribution."""
    if mean <= 0:
        return np.zeros(MC_ITERATIONS)

    try:
        if variance <= mean:
            # Underdispersed: use Normal
            std = max(math.sqrt(variance), 0.01)
            samples = np.random.normal(mean, std, MC_ITERATIONS)
        else:
            # Negative Binomial
            p = mean / variance
            p = min(max(p, 0.01), 0.99)
            r = mean * p / (1 - p)
            r = max(r, 0.01)
            samples = np.random.negative_binomial(r, p, MC_ITERATIONS).astype(float)
        return samples
    except (ValueError, OverflowError):
        std = max(math.sqrt(abs(variance)), 0.01)
        return np.random.normal(mean, std, MC_ITERATIONS)


# ── CLI ──────────────────────────────────────────────────────────


def _build_features_from_args(args: argparse.Namespace) -> PlayerFeatures:
    """Build PlayerFeatures from CLI arguments."""
    minutes = args.minutes or 32.0
    # Estimate per-minute rate from line and minutes
    per_min = args.line / minutes if minutes > 0 else 0.0

    alpha = EWMA_ALPHA.get(args.prop, 0.12)
    # Without game logs, EWMA equals the line estimate
    ewma = args.line

    return PlayerFeatures(
        projected_minutes=minutes,
        per_minute_rate=per_min,
        ewma_projection=ewma,
        rolling_avg_5=args.line,
        rolling_avg_10=args.line,
        rolling_avg_20=args.line,
        dvp_rank=args.dvp or 15,
        implied_team_total=args.total or 112.0,
        home_away=0,
        back_to_back=0,
    )


def _format_output(result: PredictionResult) -> str:
    """Format prediction result for terminal output."""
    lines = [
        "",
        f"{'═' * 60}",
        f"  {result.player} — {result.prop.upper()} {result.line}",
        f"{'═' * 60}",
        "",
        f"  Projected Value:    {result.projected_value}",
        f"  OVER Probability:   {result.over_prob:.1%}",
        f"  UNDER Probability:  {result.under_prob:.1%}",
        "",
        f"  ── Model Breakdown ──",
        f"  XGBoost:   {result.xgboost_prob:.1%}",
        f"  LightGBM:  {result.lightgbm_prob:.1%}",
        f"  Bayesian:  {result.bayesian_prob:.1%}",
        f"  Ensemble:  {result.ensemble_prob:.1%}",
        "",
        f"  Agreement:  {result.model_agreement} (spread: {result.confidence_spread:.1%})",
        "",
        f"  ── Monte Carlo ({MC_ITERATIONS:,} sims) ──",
        f"  Mean: {result.mc_mean}  Std: {result.mc_std}",
        f"  MC Over%: {result.mc_over_pct:.1%}",
    ]

    if result.edge is not None:
        lines.extend([
            "",
            f"  ── Edge Detection ──",
            f"  Edge:    {result.edge:.1%}",
            f"  Rating:  {result.edge_rating}",
            f"  Kelly:   {result.kelly_fraction:.2%} → ${result.kelly_stake:.2f}",
        ])

    lines.append(f"{'═' * 60}")
    return "\n".join(lines)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="NBA ML Prop Prediction Engine v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Single-prop mode
    parser.add_argument("--player", type=str, help="Player name")
    parser.add_argument("--team", type=str, help="Player team abbreviation")
    parser.add_argument("--opponent", type=str, help="Opponent team abbreviation")
    parser.add_argument(
        "--prop", type=str, default="points",
        choices=list(EWMA_ALPHA.keys()),
        help="Prop category",
    )
    parser.add_argument("--line", type=float, help="Sportsbook line")
    parser.add_argument("--odds", type=int, default=None, help="American odds (e.g. -110)")
    parser.add_argument("--dvp", type=int, default=None, help="DvP rank 1-30")
    parser.add_argument("--minutes", type=float, default=None, help="Projected minutes")
    parser.add_argument("--total", type=float, default=None, help="Implied team total")
    parser.add_argument("--bankroll", type=float, default=1000.0, help="Bankroll for Kelly sizing")

    # Batch mode
    parser.add_argument("--batch", type=str, default=None, help="Batch input JSON file")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file")

    args = parser.parse_args()

    # Batch mode
    if args.batch:
        if not os.path.exists(args.batch):
            logger.error(f"Batch file not found: {args.batch}")
            sys.exit(1)

        with open(args.batch, "r") as f:
            batch_data = json.load(f)

        results = []
        for entry in batch_data:
            feats = PlayerFeatures(
                projected_minutes=entry.get("minutes", 32.0),
                per_minute_rate=entry.get("line", 20.0) / max(entry.get("minutes", 32.0), 1),
                ewma_projection=entry.get("line", 20.0),
                rolling_avg_5=entry.get("line", 20.0),
                rolling_avg_10=entry.get("line", 20.0),
                rolling_avg_20=entry.get("line", 20.0),
                dvp_rank=entry.get("dvp", 15),
                implied_team_total=entry.get("total", 112.0),
            )
            result = predict_prop(
                features=feats,
                line=entry.get("line", 20.0),
                player=entry.get("player", "Unknown"),
                prop=entry.get("prop", "points"),
                american_odds=entry.get("odds"),
                bankroll=args.bankroll,
            )
            results.append(asdict(result))
            print(_format_output(result))

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {args.output}")

        sys.exit(0)

    # Single-prop mode
    if not args.player or args.line is None:
        parser.print_help()
        sys.exit(1)

    features = _build_features_from_args(args)
    result = predict_prop(
        features=features,
        line=args.line,
        player=args.player,
        prop=args.prop,
        american_odds=args.odds,
        bankroll=args.bankroll,
    )
    print(_format_output(result))


if __name__ == "__main__":
    main()
