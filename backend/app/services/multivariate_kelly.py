"""
Multivariate Kelly Criterion for Correlated Betting Portfolios

Extends the standard Kelly formula to handle simultaneous, correlated wagers
(e.g., an entire NCAAB or NFL slate) using convex portfolio optimization.

Theory:
    Single Kelly:  f* = (p*b - q) / b
    Multivariate:  maximize g(f) ≈ f·μ - (1/2) f^T V f
                   where μ = vector of expected returns
                         V = covariance matrix of outcomes

References:
    - Kelly (1956) "A New Interpretation of Information Rate"
    - Thorp (2006) "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market"
    - Busseti et al. (2016) "Risk-Constrained Kelly Gambling"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import minimize
from loguru import logger


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class BettingOpportunity:
    """Single betting opportunity in a portfolio"""
    game_id: str
    side: str
    market: str             # 'spread', 'total', 'moneyline'
    true_prob: float        # Model-estimated win probability (devigged)
    decimal_odds: float     # Offered decimal odds (e.g., 1.91 for -110)
    edge: float             # true_prob - implied_prob
    sport: str = 'ncaab'
    conference: str = ''
    home_team: str = ''
    away_team: str = ''
    sharp_signal_boost: float = 0.0  # Additional confidence from sharp signals

    @property
    def implied_prob(self) -> float:
        return 1.0 / self.decimal_odds

    @property
    def net_odds(self) -> float:
        """Net fractional odds (b in Kelly formula)"""
        return self.decimal_odds - 1.0

    @property
    def single_kelly(self) -> float:
        """Standard single-bet Kelly fraction"""
        p = self.true_prob
        b = self.net_odds
        if b <= 0:
            return 0.0
        k = (p * b - (1 - p)) / b
        return max(0.0, k)

    @property
    def adjusted_kelly(self) -> float:
        """Single Kelly with sharp signal boost"""
        return min(1.0, self.single_kelly + self.sharp_signal_boost * 0.02)


@dataclass
class PortfolioResult:
    """Result from multivariate Kelly optimization"""
    opportunities: List[BettingOpportunity]
    optimal_fractions: List[float]          # Fraction of bankroll per bet
    expected_growth_rate: float             # Expected log-growth of bankroll
    portfolio_variance: float               # Total portfolio variance
    correlation_matrix: np.ndarray
    covariance_matrix: np.ndarray
    kelly_scale: float                      # Fractional Kelly applied (0.25, 0.5, etc.)
    bankroll: float = 10000.0

    @property
    def bet_sizes(self) -> List[float]:
        """Dollar amounts to bet given bankroll"""
        return [f * self.bankroll for f in self.optimal_fractions]

    @property
    def total_exposure(self) -> float:
        return sum(self.optimal_fractions)

    def summary(self) -> Dict:
        results = []
        for opp, frac, size in zip(
            self.opportunities, self.optimal_fractions, self.bet_sizes
        ):
            if frac >= 0.001:  # Skip negligible allocations
                results.append({
                    'game_id': opp.game_id,
                    'side': opp.side,
                    'market': opp.market,
                    'true_prob': round(opp.true_prob, 4),
                    'decimal_odds': round(opp.decimal_odds, 3),
                    'edge_pct': round(opp.edge * 100, 2),
                    'single_kelly': round(opp.single_kelly, 4),
                    'portfolio_fraction': round(frac, 4),
                    'portfolio_fraction_pct': round(frac * 100, 2),
                    'bet_size_$': round(size, 2),
                    'sharp_signal': opp.sharp_signal_boost > 0
                })

        return {
            'kelly_scale': self.kelly_scale,
            'total_bankroll_exposure_pct': round(self.total_exposure * 100, 2),
            'expected_growth_rate': round(self.expected_growth_rate, 5),
            'portfolio_variance': round(self.portfolio_variance, 6),
            'bets': results,
            'bankroll': self.bankroll
        }


# ---------------------------------------------------------------------------
# Correlation Estimation
# ---------------------------------------------------------------------------

class CorrelationEstimator:
    """
    Estimates outcome correlations between simultaneous sports bets.

    Correlation factors (empirically derived):
    - Same game spread + total: ~0.60
    - Same team on consecutive days: ~0.30
    - Same conference, same division: ~0.15-0.25
    - Cross-conference: ~0.05-0.10
    - Different sports entirely: ~0.02
    """

    SAME_GAME_SPREAD_TOTAL = 0.60
    SAME_GAME_SAME_MARKET = 0.85   # e.g., two spread bets on same game
    BACK_TO_BACK_SAME_TEAM = 0.30
    SAME_CONFERENCE_SAME_DAY = 0.18
    SAME_DIVISION_SAME_DAY = 0.22
    CROSS_CONFERENCE_SAME_DAY = 0.08
    DIFFERENT_SPORT = 0.02

    @classmethod
    def estimate_correlation(
        cls,
        opp_i: BettingOpportunity,
        opp_j: BettingOpportunity
    ) -> float:
        """
        Estimate correlation coefficient between two betting outcomes.

        Args:
            opp_i: First betting opportunity
            opp_j: Second betting opportunity

        Returns:
            Correlation coefficient in [-1, 1]
        """
        if opp_i.game_id == opp_j.game_id:
            # Same game
            if opp_i.market != opp_j.market:
                return cls.SAME_GAME_SPREAD_TOTAL  # e.g., spread + total
            else:
                return cls.SAME_GAME_SAME_MARKET   # Same market (rare edge case)

        # Different games
        if opp_i.sport != opp_j.sport:
            return cls.DIFFERENT_SPORT

        # Same sport — check team overlap
        teams_i = {opp_i.home_team, opp_i.away_team}
        teams_j = {opp_j.home_team, opp_j.away_team}

        if teams_i & teams_j:
            # Shared team (back-to-back)
            return cls.BACK_TO_BACK_SAME_TEAM

        if opp_i.conference and opp_j.conference:
            if opp_i.conference == opp_j.conference:
                return cls.SAME_CONFERENCE_SAME_DAY
            else:
                return cls.CROSS_CONFERENCE_SAME_DAY

        return cls.CROSS_CONFERENCE_SAME_DAY

    @classmethod
    def build_correlation_matrix(
        cls, opportunities: List[BettingOpportunity]
    ) -> np.ndarray:
        """Build the N×N correlation matrix for a portfolio"""
        n = len(opportunities)
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                r = cls.estimate_correlation(opportunities[i], opportunities[j])
                corr[i, j] = r
                corr[j, i] = r
        return corr


# ---------------------------------------------------------------------------
# Multivariate Kelly Optimizer
# ---------------------------------------------------------------------------

class MultivariateKellyOptimizer:
    """
    Solves the multivariate Kelly optimization problem for a portfolio of
    simultaneous, correlated bets using constrained convex optimization.

    Usage:
        optimizer = MultivariateKellyOptimizer(kelly_scale=0.5)
        result = optimizer.optimize(opportunities, bankroll=10000)
        print(result.summary())
    """

    def __init__(
        self,
        kelly_scale: float = 0.5,
        max_single_fraction: float = 0.05,
        max_total_exposure: float = 0.30,
        min_edge: float = 0.03,
    ):
        """
        Args:
            kelly_scale: Fractional Kelly multiplier (0.5 = half-Kelly)
            max_single_fraction: Maximum fraction of bankroll on any single bet
            max_total_exposure: Maximum total bankroll exposure across all bets
            min_edge: Minimum edge to include opportunity in portfolio
        """
        self.kelly_scale = kelly_scale
        self.max_single_fraction = max_single_fraction
        self.max_total_exposure = max_total_exposure
        self.min_edge = min_edge

    def optimize(
        self,
        opportunities: List[BettingOpportunity],
        bankroll: float = 10000.0
    ) -> PortfolioResult:
        """
        Run multivariate Kelly optimization on a set of opportunities.

        Args:
            opportunities: List of betting opportunities to evaluate
            bankroll: Current bankroll in dollars

        Returns:
            PortfolioResult with optimal bet fractions and sizes
        """
        # Filter to positive edge only
        eligible = [o for o in opportunities if o.edge >= self.min_edge]

        if not eligible:
            logger.warning("No eligible opportunities meet minimum edge threshold")
            return self._empty_result(opportunities, bankroll)

        logger.info(
            f"Optimizing portfolio: {len(eligible)}/{len(opportunities)} "
            f"opportunities meet ≥{self.min_edge:.0%} edge threshold"
        )

        n = len(eligible)

        # Build correlation and covariance matrices
        corr_matrix = CorrelationEstimator.build_correlation_matrix(eligible)

        # Variance of each bet outcome (Bernoulli: p*(1-p))
        variances = np.array([
            o.true_prob * (1 - o.true_prob) * (o.net_odds ** 2)
            for o in eligible
        ])

        # Scale variances by decimal odds squared for proper covariance
        std_devs = np.sqrt(variances)
        cov_matrix = np.outer(std_devs, std_devs) * corr_matrix

        # Expected return vector: E[return] = p*b - q
        mu = np.array([
            o.true_prob * o.net_odds - (1 - o.true_prob)
            for o in eligible
        ])

        # Objective: maximize g(f) = f·μ - (1/2) f^T V f
        # Equivalent to minimizing the negative
        def neg_growth_rate(f):
            return -(np.dot(f, mu) - 0.5 * f @ cov_matrix @ f)

        def neg_growth_gradient(f):
            return -(mu - cov_matrix @ f)

        # Constraints
        constraints = [
            {
                'type': 'ineq',
                'fun': lambda f: self.max_total_exposure - np.sum(f)
            }
        ]

        # Bounds: [0, max_single * kelly_scale] per bet
        upper_bound = self.max_single_fraction * self.kelly_scale
        bounds = [(0, upper_bound)] * n

        # Initial guess: equal-weight small allocation
        f0 = np.ones(n) * (self.max_total_exposure / n / 4)

        result = minimize(
            neg_growth_rate,
            f0,
            jac=neg_growth_gradient,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-10, 'maxiter': 1000}
        )

        if not result.success:
            logger.warning(f"Optimization did not fully converge: {result.message}")

        raw_fractions = result.x.clip(0, upper_bound)

        # Apply kelly_scale (fractional Kelly)
        optimal_fractions = raw_fractions * self.kelly_scale

        # Round to human-like denominations (avoid algorithmic fingerprint)
        rounded_fractions = self._round_fractions(optimal_fractions)

        # Compute portfolio stats
        expected_growth = float(np.dot(optimal_fractions, mu)
                                - 0.5 * optimal_fractions @ cov_matrix @ optimal_fractions)
        portfolio_variance = float(optimal_fractions @ cov_matrix @ optimal_fractions)

        # Pad fractions back to original opportunities list order
        all_fractions = []
        eligible_idx = 0
        for opp in opportunities:
            if opp.edge >= self.min_edge:
                all_fractions.append(float(rounded_fractions[eligible_idx]))
                eligible_idx += 1
            else:
                all_fractions.append(0.0)

        portfolio = PortfolioResult(
            opportunities=opportunities,
            optimal_fractions=all_fractions,
            expected_growth_rate=expected_growth,
            portfolio_variance=portfolio_variance,
            correlation_matrix=corr_matrix,
            covariance_matrix=cov_matrix,
            kelly_scale=self.kelly_scale,
            bankroll=bankroll
        )

        logger.info(
            f"Portfolio optimized: {sum(1 for f in all_fractions if f > 0.001)} bets, "
            f"total exposure={portfolio.total_exposure:.1%}, "
            f"expected growth={expected_growth:.4f}"
        )

        return portfolio

    def _round_fractions(self, fractions: np.ndarray) -> np.ndarray:
        """
        Round fractions to human-like bet sizes to avoid algorithmic profiling.
        Rounds to nearest 0.25% of bankroll increment.
        """
        return np.round(fractions * 400) / 400  # Nearest 0.25%

    def _empty_result(
        self, opportunities: List[BettingOpportunity], bankroll: float
    ) -> PortfolioResult:
        n = len(opportunities)
        return PortfolioResult(
            opportunities=opportunities,
            optimal_fractions=[0.0] * n,
            expected_growth_rate=0.0,
            portfolio_variance=0.0,
            correlation_matrix=np.eye(n) if n > 0 else np.array([[]]),
            covariance_matrix=np.zeros((n, n)) if n > 0 else np.array([[]]),
            kelly_scale=self.kelly_scale,
            bankroll=bankroll
        )


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to decimal odds"""
    if american_odds > 0:
        return american_odds / 100 + 1
    else:
        return 100 / abs(american_odds) + 1


def decimal_to_american(decimal_odds: float) -> float:
    """Convert decimal odds to American odds"""
    if decimal_odds >= 2.0:
        return (decimal_odds - 1) * 100
    else:
        return -100 / (decimal_odds - 1)


def implied_prob(american_odds: float) -> float:
    """Convert American odds to implied probability"""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def devig(home_odds: float, away_odds: float) -> Tuple[float, float]:
    """Devig a two-sided market to get true probabilities"""
    p_home = implied_prob(home_odds)
    p_away = implied_prob(away_odds)
    total = p_home + p_away
    return p_home / total, p_away / total
