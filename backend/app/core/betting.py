"""
Core betting calculation utilities.

This module provides the single source of truth for all betting-related
calculations. All services should import from this module rather than
implementing their own versions.

Consolidates previously duplicated implementations from:
- app/services/multivariate_kelly.py
- app/services/line_movement_analyzer.py
- app/services/nba_ml_predictor.py
- app/services/prop_analyzer.py
"""

from typing import Tuple

from app.constants import (
    KELLY_SCALE_DEFAULT,
    KELLY_MAX_SINGLE_FRACTION,
    PROBABILITY_DECIMAL_PLACES,
    EDGE_DECIMAL_PLACES,
    KELLY_FRACTION_DECIMAL_PLACES,
    FRACTION_ROUNDING_DENOMINATOR,
)


# ============================================================================
# ODDS CONVERSION
# ============================================================================


def american_to_decimal(american_odds: float) -> float:
    """
    Convert American odds to decimal odds.

    Args:
        american_odds: American odds (e.g., -110, +150, -200)

    Returns:
        Decimal odds (e.g., 1.909, 2.500, 1.500)

    Examples:
        >>> american_to_decimal(-110)
        1.909090909090909
        >>> american_to_decimal(150)
        2.5
        >>> american_to_decimal(-200)
        1.5
    """
    if american_odds > 0:
        return american_odds / 100 + 1
    else:
        return 100 / abs(american_odds) + 1


def decimal_to_american(decimal_odds: float) -> float:
    """
    Convert decimal odds to American odds.

    Args:
        decimal_odds: Decimal odds (e.g., 1.91, 2.50, 1.50)

    Returns:
        American odds (e.g., -110, +150, -200)

    Examples:
        >>> decimal_to_american(1.91)
        -111.11111111111111
        >>> decimal_to_american(2.5)
        150.0
        >>> decimal_to_american(1.5)
        -200.0
    """
    if decimal_odds >= 2.0:
        return (decimal_odds - 1) * 100
    else:
        return -100 / (decimal_odds - 1)


def american_to_decimal_int(american_odds: int) -> float:
    """
    Convert American odds (int) to decimal odds.

    Convenience wrapper for the common case where odds are integers.

    Args:
        american_odds: American odds as integer (e.g., -110, +150)

    Returns:
        Decimal odds
    """
    return american_to_decimal(float(american_odds))


# ============================================================================
# PROBABILITY CALCULATIONS
# ============================================================================


def implied_probability(american_odds: float) -> float:
    """
    Convert American odds to implied probability (including vig).

    This is the probability that the odds "imply" - it will sum to >100%
    for a two-sided market due to the bookmaker's vig.

    Args:
        american_odds: American odds (e.g., -110, +150)

    Returns:
        Implied probability (0.0 to 1.0)

    Examples:
        >>> implied_probability(-110)
        0.5238095238095238
        >>> implied_probability(150)
        0.4
    """
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def probability_to_american(prob: float) -> float:
    """
    Convert a probability to American odds (fair odds, no vig).

    Args:
        prob: True probability (0.0 to 1.0)

    Returns:
        Fair American odds

    Examples:
        >>> probability_to_american(0.5)
        100.0
        >>> probability_to_american(0.6)
        -150.0
    """
    if prob >= 0.5:
        return -100 * prob / (1 - prob)
    else:
        return 100 * (1 - prob) / prob


# ============================================================================
# DEVIGGING
# ============================================================================


def devig_odds(odds_side1: float, odds_side2: float) -> Tuple[float, float]:
    """
    Remove the bookmaker vig from a two-sided market to get true probabilities.

    Uses the multiplicative method (normalize to sum to 1.0).

    Args:
        odds_side1: American odds for side 1 (e.g., home team)
        odds_side2: American odds for side 2 (e.g., away team)

    Returns:
        Tuple of (true_prob_side1, true_prob_side2)

    Examples:
        >>> devig_odds(-110, -110)
        (0.5, 0.5)
        >>> devig_odds(-120, +100)
        (0.5454545454545454, 0.45454545454545453)
    """
    imp1 = implied_probability(odds_side1)
    imp2 = implied_probability(odds_side2)
    total = imp1 + imp2

    # Normalize to remove vig
    return imp1 / total, imp2 / total


def devig_decimal(
    decimal_odds_side1: float, decimal_odds_side2: float
) -> Tuple[float, float]:
    """
    Devig using decimal odds directly.

    Args:
        decimal_odds_side1: Decimal odds for side 1
        decimal_odds_side2: Decimal odds for side 2

    Returns:
        Tuple of (true_prob_side1, true_prob_side2)
    """
    imp1 = 1.0 / decimal_odds_side1
    imp2 = 1.0 / decimal_odds_side2
    total = imp1 + imp2

    return imp1 / total, imp2 / total


# ============================================================================
# EXPECTED VALUE & EDGE
# ============================================================================


def calculate_ev(true_prob: float, decimal_odds: float) -> float:
    """
    Calculate expected value of a bet.

    EV = (True Probability × Decimal Odds) - 1

    Args:
        true_prob: Model's estimate of true win probability
        decimal_odds: Offered decimal odds

    Returns:
        Expected value (positive = +EV, negative = -EV)

    Examples:
        >>> calculate_ev(0.55, 1.91)
        0.05049999999999999
        >>> calculate_ev(0.50, 2.0)
        0.0
    """
    return true_prob * decimal_odds - 1


def calculate_edge(true_prob: float, american_odds: float) -> float:
    """
    Calculate edge as probability difference.

    Edge = True Probability - Implied Probability

    This is equivalent to EV when expressed in probability terms.

    Args:
        true_prob: Model's estimate of true win probability
        american_odds: Offered American odds

    Returns:
        Edge in probability units (e.g., 0.03 = 3% edge)

    Examples:
        >>> calculate_edge(0.55, -110)
        0.02619047619047619
    """
    implied = implied_probability(american_odds)
    return true_prob - implied


def edge_percentage(true_prob: float, american_odds: float) -> float:
    """
    Calculate edge as a percentage (for display).

    Args:
        true_prob: Model's estimate of true win probability
        american_odds: Offered American odds

    Returns:
        Edge as percentage (e.g., 3.0 = 3% edge)
    """
    return calculate_edge(true_prob, american_odds) * 100


# ============================================================================
# KELLY CRITERION
# ============================================================================


def calculate_kelly(
    true_prob: float,
    decimal_odds: float,
    scale: float = KELLY_SCALE_DEFAULT,
    max_fraction: float = KELLY_MAX_SINGLE_FRACTION,
) -> float:
    """
    Calculate Kelly Criterion optimal bet fraction.

    Standard Kelly formula: f* = (p*b - q) / b
    where p = win probability, q = loss probability, b = net odds (decimal - 1)

    Simplified: f* = (p * decimal_odds - 1) / (decimal_odds - 1)

    This is equivalent to: f* = edge / (decimal_odds - 1)

    Args:
        true_prob: Model's estimate of true win probability
        decimal_odds: Offered decimal odds
        scale: Kelly fraction to apply (0.5 = half-Kelly, default)
        max_fraction: Maximum fraction of bankroll to bet

    Returns:
        Optimal bet fraction (0.0 to max_fraction)

    Examples:
        >>> calculate_kelly(0.55, 1.91)
        0.027472527472527476
        >>> calculate_kelly(0.55, 1.91, scale=0.25)  # Quarter-Kelly
        0.013736263736263738
    """
    # Validate inputs
    if true_prob <= 0 or true_prob >= 1:
        return 0.0
    if decimal_odds <= 1:
        return 0.0

    # Net odds (b in Kelly formula)
    net_odds = decimal_odds - 1

    # Full Kelly fraction
    # f* = (p * b - q) / b = (p * (b+1) - 1) / b = (p * decimal_odds - 1) / net_odds
    kelly_full = (true_prob * decimal_odds - 1) / net_odds

    # Can't be negative (no bet on -EV)
    kelly_full = max(0.0, kelly_full)

    # Apply fractional Kelly scaling
    kelly_scaled = kelly_full * scale

    # Cap at maximum
    kelly_final = min(kelly_scaled, max_fraction)

    return kelly_final


def calculate_kelly_from_edge(
    edge: float,
    decimal_odds: float,
    scale: float = KELLY_SCALE_DEFAULT,
    max_fraction: float = KELLY_MAX_SINGLE_FRACTION,
) -> float:
    """
    Calculate Kelly fraction directly from edge.

    Simplified formula: f* = edge / (decimal_odds - 1)

    This is mathematically equivalent to the full Kelly formula
    when edge is calculated as: edge = true_prob * decimal_odds - 1

    Args:
        edge: Edge in decimal form (e.g., 0.03 for 3% edge)
        decimal_odds: Offered decimal odds
        scale: Kelly fraction to apply
        max_fraction: Maximum fraction of bankroll

    Returns:
        Optimal bet fraction
    """
    if edge <= 0:
        return 0.0

    net_odds = decimal_odds - 1
    if net_odds <= 0:
        return 0.0

    kelly_full = edge / net_odds
    kelly_scaled = kelly_full * scale

    return min(kelly_scaled, max_fraction)


def calculate_kelly_from_american(
    true_prob: float,
    american_odds: float,
    scale: float = KELLY_SCALE_DEFAULT,
    max_fraction: float = KELLY_MAX_SINGLE_FRACTION,
) -> float:
    """
    Calculate Kelly fraction using American odds.

    Convenience wrapper that converts American to decimal internally.

    Args:
        true_prob: Model's estimate of true win probability
        american_odds: Offered American odds
        scale: Kelly fraction to apply
        max_fraction: Maximum fraction of bankroll

    Returns:
        Optimal bet fraction
    """
    decimal_odds = american_to_decimal(american_odds)
    return calculate_kelly(true_prob, decimal_odds, scale, max_fraction)


# ============================================================================
# ROUNDING UTILITIES
# ============================================================================


def round_kelly_fraction(fraction: float) -> float:
    """
    Round Kelly fraction to human-like bet sizes.

    Rounds to nearest 0.25% of bankroll to avoid algorithmic
    fingerprinting by sportsbooks.

    Args:
        fraction: Raw Kelly fraction

    Returns:
        Rounded fraction
    """
    return (
        round(fraction * FRACTION_ROUNDING_DENOMINATOR) / FRACTION_ROUNDING_DENOMINATOR
    )


def round_probability(prob: float) -> float:
    """
    Round probability to standard decimal places.

    Args:
        prob: Probability value

    Returns:
        Rounded probability
    """
    return round(prob, PROBABILITY_DECIMAL_PLACES)


def round_edge(edge: float) -> float:
    """
    Round edge to standard decimal places.

    Args:
        edge: Edge value

    Returns:
        Rounded edge
    """
    return round(edge, EDGE_DECIMAL_PLACES)


def round_kelly(kelly: float) -> float:
    """
    Round Kelly fraction to standard decimal places.

    Args:
        kelly: Kelly fraction

    Returns:
        Rounded Kelly fraction
    """
    return round(kelly, KELLY_FRACTION_DECIMAL_PLACES)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def is_positive_ev(
    true_prob: float,
    american_odds: float,
    min_edge: float = 0.0,
) -> bool:
    """
    Check if a bet has positive expected value.

    Args:
        true_prob: Model's estimate of true win probability
        american_odds: Offered American odds
        min_edge: Minimum edge threshold (default 0 = any +EV)

    Returns:
        True if edge >= min_edge
    """
    edge = calculate_edge(true_prob, american_odds)
    return edge >= min_edge


def get_bet_size(
    bankroll: float,
    true_prob: float,
    american_odds: float,
    scale: float = KELLY_SCALE_DEFAULT,
    max_fraction: float = KELLY_MAX_SINGLE_FRACTION,
    round_to_human: bool = True,
) -> float:
    """
    Calculate actual bet size in dollars.

    Args:
        bankroll: Current bankroll
        true_prob: Model's estimate of true win probability
        american_odds: Offered American odds
        scale: Kelly fraction to apply
        max_fraction: Maximum fraction of bankroll
        round_to_human: Whether to round to human-like denominations

    Returns:
        Bet size in dollars
    """
    kelly = calculate_kelly_from_american(true_prob, american_odds, scale, max_fraction)

    if round_to_human:
        kelly = round_kelly_fraction(kelly)

    return kelly * bankroll


def profit_from_american_bet(
    bet_size: float,
    american_odds: float,
    won: bool,
) -> float:
    """
    Calculate profit/loss from a bet given American odds.

    Args:
        bet_size: Amount wagered in dollars
        american_odds: American odds at time of bet
        won: Whether the bet won

    Returns:
        Profit (positive) or loss (negative) in dollars
    """
    if not won:
        return -bet_size

    if american_odds > 0:
        # Underdog: profit = bet_size * (odds / 100)
        return bet_size * (american_odds / 100)
    else:
        # Favorite: profit = bet_size * (100 / abs(odds))
        return bet_size * (100 / abs(american_odds))


def payout_from_american_bet(
    bet_size: float,
    american_odds: float,
    won: bool,
) -> float:
    """
    Calculate total payout (stake + profit) from a bet.

    Args:
        bet_size: Amount wagered in dollars
        american_odds: American odds at time of bet
        won: Whether the bet won

    Returns:
        Total payout in dollars (0 if lost, stake + profit if won)
    """
    if not won:
        return 0.0

    profit = profit_from_american_bet(bet_size, american_odds, won)
    return bet_size + profit
