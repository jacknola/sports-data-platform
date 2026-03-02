"""
Parlay math utilities.

Pure functions for parlay odds calculation, EV analysis, and risk assessment.
Kept in a dedicated module so they can be tested independently of the full
FastAPI router stack.
"""

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Odds conversion helpers
# ---------------------------------------------------------------------------


def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return 1.0 + american_odds / 100.0
    else:
        return 1.0 + 100.0 / abs(american_odds)


def implied_prob(american_odds: float) -> float:
    """Raw (vig-inclusive) implied probability from American odds."""
    return 1.0 / american_to_decimal(american_odds)


# ---------------------------------------------------------------------------
# Core parlay helpers
# ---------------------------------------------------------------------------


def calculate_parlay_odds(leg_odds: List[float]) -> tuple:
    """
    Calculate total parlay odds and payout multiplier.

    Args:
        leg_odds: List of American odds for each leg.

    Returns:
        (total_american_odds, payout_multiplier)
    """
    combined_decimal = 1.0
    for odds in leg_odds:
        combined_decimal *= american_to_decimal(odds)

    if combined_decimal >= 2.0:
        total_american = (combined_decimal - 1) * 100
    else:
        total_american = -100 / (combined_decimal - 1)

    return total_american, combined_decimal


def calculate_parlay_ev(
    leg_odds: List[float],
    payout_multiplier: float,
    pinnacle_vig: float = 0.025,
) -> Dict[str, Any]:
    """
    Compute parlay expected value and vig-compounding analysis.

    Uses single-sided multiplicative devig (true_prob = implied / (1 + vig))
    to estimate each leg's true probability, then multiplies them together
    to get the combined true probability assuming independent outcomes.

    Args:
        leg_odds:          American odds for each leg (as offered by the book).
        payout_multiplier: Decimal payout for the full parlay.
        pinnacle_vig:      Estimated total overround per side for devigging
                           (default 2.5%, typical Pinnacle spread/total).

    Returns:
        Dict with:
            true_combined_prob  – product of devigged per-leg probabilities
            fair_payout         – 1 / true_combined_prob (break-even multiplier)
            offered_payout      – the book's actual payout_multiplier
            ev_per_unit         – EV per $1 wagered (positive = +EV)
            vig_cost_pct        – percentage of fair value surrendered to vig
            leg_count           – number of legs
            is_positive_ev      – bool convenience flag
    """
    n = len(leg_odds)
    if n == 0:
        return {}

    true_combined_prob = 1.0
    for odds in leg_odds:
        raw_implied = implied_prob(odds)
        devigged = raw_implied / (1.0 + pinnacle_vig)
        true_combined_prob *= devigged

    fair_payout = 1.0 / true_combined_prob if true_combined_prob > 0 else float("inf")
    ev_per_unit = true_combined_prob * payout_multiplier - 1.0
    vig_cost_pct = (
        round((1.0 - payout_multiplier / fair_payout) * 100, 2) if fair_payout > 0 else 0.0
    )

    return {
        "leg_count": n,
        "true_combined_prob": round(true_combined_prob, 6),
        "fair_payout": round(fair_payout, 3),
        "offered_payout": round(payout_multiplier, 3),
        "ev_per_unit": round(ev_per_unit, 4),
        "vig_cost_pct": vig_cost_pct,
        "is_positive_ev": ev_per_unit > 0,
    }


def parlay_risk_summary(
    legs: List[Dict[str, Any]],
    sport: str,
) -> Dict[str, Any]:
    """
    Build a parlay risk summary by delegating to ``assess_parlay_risk``.

    Constructs minimal ``BettingOpportunity`` proxies from the leg dicts
    (which must have at minimum ``game``, ``pick``, ``odds``, ``market``,
    ``team``, and optionally ``opponent`` keys).

    Args:
        legs:  List of leg dicts (matches ParlayLegCreate schema).
        sport: Parlay sport string (e.g. "NBA", "NCAAB").

    Returns:
        ``assess_parlay_risk`` result dict.
    """
    from app.services.multivariate_kelly import BettingOpportunity, assess_parlay_risk

    opportunities = []
    for leg in legs:
        odds = leg.get("odds", -110) if isinstance(leg, dict) else getattr(leg, "odds", -110)
        dec = american_to_decimal(odds)
        raw_impl = implied_prob(odds)
        devigged = raw_impl / 1.025
        edge = devigged - raw_impl  # always slightly negative (vig cost)

        def _get(key: str, default: Any = "") -> Any:
            return leg.get(key, default) if isinstance(leg, dict) else getattr(leg, key, default)

        opp = BettingOpportunity(
            game_id=_get("game", "unknown"),
            side=_get("pick", ""),
            market=_get("market", "moneyline"),
            true_prob=devigged,
            decimal_odds=dec,
            edge=edge,
            sport=sport.lower(),
            home_team=_get("team", ""),
            away_team=_get("opponent", ""),
        )
        opportunities.append(opp)

    return assess_parlay_risk(opportunities)
