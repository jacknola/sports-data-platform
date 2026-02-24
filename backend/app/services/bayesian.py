"""
Bayesian analysis for sports betting
"""

import numpy as np
from typing import Dict, Any, List, Optional
from loguru import logger
from app.config import settings

# ---------------------------------------------------------------------------
# Conference tier variance penalty for large spread markets
#
# Mid-major spreads of 7.5+ cover at materially lower rates than the
# implied probability suggests. Books inflate spreads in low-sample-size
# leagues where public betting is less informed, creating a systematic
# overconfidence trap.
#
# Penalty applied as a negative adjustment to posterior probability when:
#   - conference_tier is not 'power_5'
#   - abs(spread) >= 7.5
#
# Derived from historical NCAAB cover rates by conference tier and spread size.
# ---------------------------------------------------------------------------

CONFERENCE_TIER_SPREAD_PENALTY: Dict[str, Dict[str, float]] = {
    # tier → {spread_bucket: probability penalty}
    "power_5": {"large": 0.00, "medium": 0.00},  # ACC, Big Ten, Big 12, SEC, Big East
    "high_major": {
        "large": -0.02,
        "medium": -0.01,
    },  # American, Mountain West, WCC, A10
    "mid_major": {
        "large": -0.05,
        "medium": -0.02,
    },  # MAC, Sun Belt, CUSA, OVC, Colonial
    "low_major": {"large": -0.08, "medium": -0.04},  # SWAC, MEAC, Patriot, NEC, Big Sky
}

LARGE_SPREAD_THRESHOLD = 7.5  # Spread size (points) triggering large penalty
MEDIUM_SPREAD_THRESHOLD = 5.0  # Spread size triggering medium penalty


class BayesianAnalyzer:
    """Bayesian probability calculator for sports betting"""

    def compute_posterior(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute Bayesian posterior probability for a betting selection

        Args:
            data: Contains devig_prob, implied_prob, features, selection_id

        Returns:
            Dictionary with posterior_p, fair_american_odds, edge, and confidence interval
        """
        prior_prob = data.get("devig_prob", 0.5)
        implied_prob = data.get("implied_prob", 0.5)
        features = data.get("features", {})

        logger.info(f"Computing posterior for selection {data.get('selection_id')}")

        # Convert prior to Beta parameters.
        # prior_strength controls how much the prior resists the model projection.
        # For props, we want the Normal CDF / hit-rate projection to dominate
        # over the market-implied prior — so keep this weak (4 = ~4 pseudo-obs).
        prior_strength = 4  # was 10 — weakened so model projection dominates
        alpha_prior = prior_prob * prior_strength
        beta_prior = (1 - prior_prob) * prior_strength

        # Feature-based adjustments
        adjustments = self._compute_adjustments(features)

        # Apply adjustments
        total_adjustment = sum(adjustments.values())
        adjusted_prob = max(0.01, min(0.99, prior_prob + total_adjustment))

        # Update Beta parameters with pseudo-observations from the model projection.
        # pseudo_obs controls how strongly the likelihood (adjusted_prob) updates
        # the posterior. Higher = tighter posterior, but we want it responsive.
        pseudo_obs = 8  # was 20 — reduced so posterior tracks adjusted_prob closely
        alpha_post = alpha_prior + adjusted_prob * pseudo_obs
        beta_post = beta_prior + (1 - adjusted_prob) * pseudo_obs

        # Monte Carlo simulation
        n_simulations = 20000
        samples = np.random.beta(alpha_post, beta_post, n_simulations)

        # Calculate statistics
        posterior_p = float(np.mean(samples))
        p05 = float(np.percentile(samples, 5))
        p95 = float(np.percentile(samples, 95))

        # Convert to American odds
        fair_american = self._prob_to_american_odds(posterior_p)

        # Calculate edge
        edge = posterior_p - implied_prob

        result = {
            "selection_id": data.get("selection_id"),
            "prior_prob": round(prior_prob, 4),
            "posterior_p": round(posterior_p, 4),
            "fair_american_odds": round(fair_american, 1),
            "current_american_odds": data.get("current_american_odds"),
            "edge": round(edge, 4),
            "confidence_interval": {"p05": round(p05, 4), "p95": round(p95, 4)},
            "monte_carlo": {
                "n_simulations": n_simulations,
                "mean": round(posterior_p, 4),
                "std": round(float(np.std(samples)), 4),
            },
            "adjustments": adjustments,
        }

        logger.info(f"Posterior computed: {posterior_p:.4f}, Edge: {edge:.4f}")

        return result

    def _compute_adjustments(self, features: Dict[str, Any]) -> Dict[str, float]:
        """Compute adjustments based on feature values"""
        adjustments = {}

        adjustments["injury"] = self._get_injury_adjustment(features.get("injury_status", "ACTIVE"))
        adjustments["pace"] = self._get_pace_adjustment(features)
        adjustments["usage"] = self._get_usage_adjustment(features.get("usage", {}))
        adjustments["weather"] = self._get_weather_adjustment(features.get("weather", {}))
        adjustments["home_advantage"] = self._get_home_advantage_adjustment(features.get("is_home"))
        adjustments["form"] = self._get_form_adjustment(features.get("recent_form", []))

        # Conference tier variance penalty for large spreads
        spread_penalty = self._get_conference_spread_adjustment(features)
        if spread_penalty != 0.0:
            adjustments["conference_spread_variance"] = spread_penalty

        # Remove 0.0 adjustments to keep it clean
        return {k: v for k, v in adjustments.items() if v != 0.0}

    def _get_injury_adjustment(self, injury_status: str) -> float:
        """Calculate adjustment based on injury status."""
        if injury_status == "QUESTIONABLE":
            return -0.05
        elif injury_status == "OUT":
            return -0.99
        return 0.0

    def _get_pace_adjustment(self, features: Dict[str, Any]) -> float:
        """Calculate adjustment based on pace comparison."""
        team_pace = features.get("team_pace", 0)
        opp_pace = features.get("opponent_pace", 0)

        if team_pace and opp_pace:
            pace_factor = (team_pace + opp_pace) / 2
            league_avg = features.get("league_avg_pace", pace_factor)
            if league_avg > 0:
                pace_delta = (pace_factor - league_avg) / league_avg
                return pace_delta * 0.1
        return 0.0

    def _get_usage_adjustment(self, usage: Dict[str, Any]) -> float:
        """Calculate adjustment based on player usage trend."""
        if usage.get("value"):
            usage_trend = usage.get("trend", 0)
            return usage_trend * 0.02
        return 0.0

    def _get_weather_adjustment(self, weather: Dict[str, Any]) -> float:
        """Calculate adjustment based on weather conditions (for outdoor sports)."""
        if weather.get("type") == "outdoor":
            wind = weather.get("wind_mph", 0)
            if wind > 20:
                return -0.03
        return 0.0

    def _get_home_advantage_adjustment(self, is_home: Optional[bool]) -> float:
        """Calculate adjustment for home/away."""
        if is_home is None:
            return 0.0
        return 0.03 if is_home else -0.03

    def _get_form_adjustment(self, recent_form: List[float]) -> float:
        """Calculate adjustment based on recent form."""
        if recent_form:
            avg_form = np.mean(recent_form)
            return (float(avg_form) - 0.5) * 0.1
        return 0.0

    def _get_conference_spread_adjustment(self, features: Dict[str, Any]) -> float:
        """
        Calculate conference tier variance penalty for large spreads.

        Mid-major large spreads are systematically overconfident — books inflate
        lines in low-sample-size leagues.
        """
        conference_tier = features.get("conference_tier", "power_5")
        spread = features.get("spread", 0.0)  # signed: negative = favorite spread
        abs_spread = abs(spread)

        bucket: Optional[str] = None
        if abs_spread >= LARGE_SPREAD_THRESHOLD:
            bucket = "large"
        elif abs_spread >= MEDIUM_SPREAD_THRESHOLD:
            bucket = "medium"

        if bucket is not None and conference_tier in CONFERENCE_TIER_SPREAD_PENALTY:
            penalty = CONFERENCE_TIER_SPREAD_PENALTY[conference_tier].get(bucket, 0.0)
            if penalty != 0.0:
                logger.debug(
                    f"Applied {conference_tier} {bucket}-spread variance penalty: {penalty:+.3f} "
                    f"(spread={spread}, tier={conference_tier})"
                )
            return penalty

        return 0.0

    def _prob_to_american_odds(self, prob: float) -> float:
        """Convert probability to American odds"""
        if prob > 0.5:
            return -100 * prob / (1 - prob)
        else:
            return 100 * (1 - prob) / prob

    def calculate_kelly_criterion(
        self, prob: float, odds: float, edge: float = 0.0
    ) -> float:
        """
        Calculate Kelly Criterion for bet sizing

        Args:
            prob: Probability of winning
            odds: Decimal odds
            edge: Edge (posterior_p - implied_p) to determine fraction

        Returns:
            Kelly fraction (percentage of bankroll to bet)
        """
        if odds <= 1:
            return 0.0

        # Full Kelly formula: (p*b - q) / b where b is decimal odds - 1
        b = odds - 1
        q = 1 - prob
        full_kelly = (prob * b - q) / b

        if full_kelly <= 0:
            return 0.0

        # Determine fractional multiplier based on edge thresholds
        # AGENTS.md: >=3% edge (0.03) = Quarter Kelly, >=5% edge (0.05) = Half Kelly
        if edge >= settings.EDGE_THRESHOLD_MEDIUM:
            multiplier = settings.KELLY_FRACTION_HALF
        elif edge >= settings.EDGE_THRESHOLD_LOW:
            multiplier = settings.KELLY_FRACTION_QUARTER
        else:
            # Below minimum threshold (3% by default), don't recommend a bet
            return 0.0

        kelly_stake = full_kelly * multiplier

        # Apply global max bet cap (5% by default)
        return max(0.0, min(kelly_stake, settings.MAX_BET_PERCENTAGE))
