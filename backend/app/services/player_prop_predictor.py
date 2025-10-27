"""
Player Prop Over/Under Predictor
Computes probabilities, fair odds, EV, and Kelly for player stat props.
"""
from typing import Dict, Any, List, Optional, Tuple
from math import erf, sqrt, exp
from loguru import logger

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False


def american_to_decimal(odds: float) -> float:
    if odds is None:
        return 2.0
    if odds > 0:
        return odds / 100.0 + 1.0
    return 100.0 / abs(odds) + 1.0


def decimal_to_american(decimal_odds: float) -> int:
    if decimal_odds <= 1:
        return -10000
    if decimal_odds >= 2:
        return int(round((decimal_odds - 1.0) * 100.0))
    # favorite
    return int(round(-100.0 / (decimal_odds - 1.0)))


def weighted_mean_std(values: List[float], weight_lambda: float = 0.1) -> Tuple[float, float]:
    if not values:
        return 0.0, 1.0
    n = len(values)
    raw_weights = [exp(-weight_lambda * i) for i in range(n)]
    sum_w = sum(raw_weights) or 1.0
    weights = [w / sum_w for w in raw_weights]
    mean = sum(w * v for w, v in zip(weights, values))
    var = sum(w * (v - mean) ** 2 for w, v in zip(weights, values))
    std = sqrt(var) if var > 0 else 1.0
    return float(mean), float(std)


def normal_cdf(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.5 if x == mu else (1.0 if x > mu else 0.0)
    if SCIPY_AVAILABLE:
        return float(norm.cdf(x, loc=mu, scale=sigma))
    # Fallback using error function
    z = (x - mu) / (sigma * sqrt(2.0))
    return 0.5 * (1.0 + erf(z))


def kelly_fraction(prob: float, dec_odds: float, fraction: float = 0.5) -> float:
    # Kelly f* = (bp - q) / b where b = dec_odds - 1
    if prob <= 0.0 or prob >= 1.0:
        return 0.0
    b = max(dec_odds - 1.0, 1e-9)
    q = 1.0 - prob
    f_star = (b * prob - q) / b
    if f_star <= 0:
        return 0.0
    return float(min(fraction * f_star, 0.25))


class PlayerPropPredictor:
    """Predict over/under probability for a player stat using a simple statistical model."""

    def __init__(self, min_ev_threshold: float = 0.02):
        self.min_ev_threshold = min_ev_threshold

    def predict_over_under(
        self,
        *,
        player: str,
        market: str,
        line: float,
        history: Optional[List[float]] = None,
        side_odds: Optional[Dict[str, float]] = None,
        adjustment_pct: float = 0.0,
        weight_lambda: float = 0.1,
        kelly_fraction_default: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Compute probabilities and value for a player prop over/under.

        Args:
            player: Player name
            market: Stat market (e.g., points, assists, rebounds, pra, threes)
            line: The sportsbook line (e.g., 24.5)
            history: Recent game stat values (most recent first preferred)
            side_odds: American odds mapping like {"over": -110, "under": -110}
            adjustment_pct: Multiplicative adjustment to mean (+0.05 => +5%)
            weight_lambda: Exponential decay for weights (higher -> more recent emphasis)
            kelly_fraction_default: Fractional Kelly to apply to recommended stake
        """
        history = history or []
        if not isinstance(line, (int, float)):
            raise ValueError("line must be a number")

        logger.info(f"Player prop prediction for {player} {market} line {line}")

        mean, std = weighted_mean_std(history, weight_lambda=weight_lambda)
        # Apply simple mean adjustment
        adj_mean = mean * (1.0 + adjustment_pct)

        p_under = normal_cdf(line, adj_mean, std)
        p_over = max(0.0, min(1.0, 1.0 - p_under))

        # Fair odds
        fair_over_dec = (1.0 / p_over) if p_over > 0 else 1000.0
        fair_under_dec = (1.0 / p_under) if p_under > 0 else 1000.0
        fair_over_am = decimal_to_american(fair_over_dec)
        fair_under_am = decimal_to_american(fair_under_dec)

        offered_over_am = float(side_odds.get("over", -110)) if side_odds else -110.0
        offered_under_am = float(side_odds.get("under", -110)) if side_odds else -110.0
        offered_over_dec = american_to_decimal(offered_over_am)
        offered_under_dec = american_to_decimal(offered_under_am)

        # EV for $1 stake
        over_ev = p_over * (offered_over_dec - 1.0) - (1.0 - p_over)
        under_ev = p_under * (offered_under_dec - 1.0) - (1.0 - p_under)

        over_kelly = kelly_fraction(p_over, offered_over_dec, kelly_fraction_default)
        under_kelly = kelly_fraction(p_under, offered_under_dec, kelly_fraction_default)

        # Recommendation
        if over_ev > under_ev and over_ev >= self.min_ev_threshold:
            recommendation = "over"
            stake_fraction = over_kelly
            best_ev = over_ev
        elif under_ev >= self.min_ev_threshold:
            recommendation = "under"
            stake_fraction = under_kelly
            best_ev = under_ev
        else:
            recommendation = "no_bet"
            stake_fraction = 0.0
            best_ev = max(over_ev, under_ev)

        result = {
            "player": player,
            "market": market,
            "line": line,
            "history_count": len(history),
            "distribution": {
                "mean": adj_mean,
                "std": std,
                "raw_mean": mean,
                "adjustment_pct": adjustment_pct,
                "weight_lambda": weight_lambda,
            },
            "probabilities": {
                "over": p_over,
                "under": p_under,
            },
            "fair_odds": {
                "over_decimal": fair_over_dec,
                "under_decimal": fair_under_dec,
                "over_american": fair_over_am,
                "under_american": fair_under_am,
            },
            "offered_odds": {
                "over_american": offered_over_am,
                "under_american": offered_under_am,
                "over_decimal": offered_over_dec,
                "under_decimal": offered_under_dec,
            },
            "expected_value": {
                "over": over_ev,
                "under": under_ev,
            },
            "kelly_fraction": {
                "over": over_kelly,
                "under": under_kelly,
            },
            "recommendation": {
                "side": recommendation,
                "stake_fraction": stake_fraction,
                "best_ev": best_ev,
            },
            "method": "normal_weighted_v1",
        }

        return result
