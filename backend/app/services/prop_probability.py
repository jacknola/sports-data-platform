"""
Player Prop Probability Model

Distribution-based projection model for player prop over/under markets.

Models a player's stat output as a Normal distribution parameterized by:
  - Season average (base mean μ)
  - Recent form adjustment (L5 vs season avg)
  - Pace adjustment (game pace vs league avg)
  - Matchup adjustment (opponent defensive rating vs position)
  - Usage rate trend
  - Injury / rest factors
  - Home/away advantage

P(over line) = 1 - Φ((line - μ_adj) / σ_adj)

The devigged market probability (from PropAnalyzer.devig_prop) serves as the
prior in BayesianAnalyzer.compute_posterior(), with the model projection used
as the feature-adjusted likelihood — consistent with how bayesian.py handles
game spread markets.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import numpy as np
from scipy import stats
from loguru import logger

from app.services.prop_analyzer import PropAnalyzer


# ---------------------------------------------------------------------------
# Constants — NBA league averages (2024-25 season baselines)
# ---------------------------------------------------------------------------

LEAGUE_AVG_PACE = 100.0          # possessions per 48 min
LEAGUE_AVG_DEF_RATING = 113.5   # points allowed per 100 possessions

# Empirical standard deviation as fraction of mean (Normal approximation)
# Points: ~0.40, Rebounds: ~0.45, Assists: ~0.50, Threes: ~0.55
STAT_STD_FACTORS: Dict[str, float] = {
    'points':   0.40,
    'rebounds': 0.45,
    'assists':  0.50,
    'threes':   0.55,
    'blocks':   0.60,
    'steals':   0.60,
    'pra':      0.35,   # points + rebounds + assists (diversified, lower CV)
}

# Minimum σ floor to avoid division edge cases on near-zero stats
MIN_STD = 1.0


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class PropProjection:
    """
    Full projection and probability output for a single player prop.

    Plugs directly into BayesianAnalyzer.compute_posterior():
        devig_prob  → true_over_prob (devigged from market)
        implied_prob → market_over_implied (retail book implied)
        features    → prop_features dict
    """
    player_id: str
    player_name: str
    stat_type: str
    line: float

    # Distribution parameters (pre-adjustment)
    base_mean: float
    base_std: float

    # Adjustment breakdown (mirrors bayesian._compute_adjustments output)
    adjustments: Dict[str, float] = field(default_factory=dict)

    # Adjusted distribution
    projected_mean: float = 0.0
    projected_std: float = 0.0

    # Model-based probabilities (from Normal CDF)
    model_p_over: float = 0.0
    model_p_under: float = 0.0

    # Market-based probabilities (devigged from book odds)
    market_p_over: float = 0.0
    market_p_under: float = 0.0

    # Market implied probability (with vig, for edge calculation)
    market_over_implied: float = 0.0

    # Edge: model probability vs. market implied
    model_edge_over: float = 0.0
    model_edge_under: float = 0.0

    # Bayesian posterior inputs (ready to pass to BayesianAnalyzer)
    devig_prob: float = 0.0       # true_over_prob from devigged market (prior)
    implied_prob: float = 0.0     # retail over implied probability

    @property
    def best_side(self) -> str:
        return 'over' if self.model_edge_over >= self.model_edge_under else 'under'

    @property
    def best_edge(self) -> float:
        return max(self.model_edge_over, self.model_edge_under)

    def to_bayesian_input(self) -> Dict:
        """Format as input dict for BayesianAnalyzer.compute_posterior()"""
        return {
            'selection_id': f"{self.player_id}:{self.stat_type}:{self.best_side}",
            'devig_prob': self.devig_prob,
            'implied_prob': self.implied_prob,
            'current_american_odds': None,  # set by caller from snapshot
            'features': self._build_features(),
        }

    def _build_features(self) -> Dict:
        """
        Build features dict compatible with BayesianAnalyzer._compute_adjustments().

        Reuses the same feature keys so the Bayesian layer applies its own
        adjustments on top of the model projection.
        """
        return {
            'injury_status': 'ACTIVE',          # caller overrides if needed
            'team_pace': self.adjustments.get('_team_pace', 0),
            'opponent_pace': self.adjustments.get('_opp_pace', 0),
            'league_avg_pace': LEAGUE_AVG_PACE,
            'usage': {
                'value': True,
                'trend': self.adjustments.get('usage_trend', 0) / 0.02  # undo the 0.02 scaling
            },
            'is_home': self.adjustments.get('home_advantage', 0) > 0,
            'recent_form': [],  # pre-computed in adjustments; pass empty to avoid double-dip
        }


# ---------------------------------------------------------------------------
# Probability Model
# ---------------------------------------------------------------------------

class PropProbabilityModel:
    """
    Computes over/under probabilities for player props using a Normal
    distribution model, adjusted for pace, matchup, usage, and situational factors.

    Designed to produce the `devig_prob` and `implied_prob` inputs required by
    BayesianAnalyzer.compute_posterior(), consistent with how game markets feed
    into the Bayesian layer.

    Usage:
        model = PropProbabilityModel()
        projection = model.project(player_data, game_context, over_odds, under_odds)
        posterior = bayesian.compute_posterior(projection.to_bayesian_input())
    """

    def project(
        self,
        player_data: Dict,
        game_context: Dict,
        over_odds: float,
        under_odds: float,
    ) -> PropProjection:
        """
        Build a full prop projection and probability estimate.

        Args:
            player_data: {
                'player_id': str,
                'player_name': str,
                'stat_type': str,           # 'points', 'rebounds', 'assists', etc.
                'line': float,              # prop line to evaluate
                'season_avg': float,        # season average for this stat
                'last_5_avg': float,        # average over last 5 games
                'usage_rate': float,        # fraction of team possessions (0.0–1.0)
                'usage_trend': float,       # recent usage minus season usage (signed)
                'injury_status': str,       # 'ACTIVE', 'QUESTIONABLE', 'OUT'
                'rest_days': int,           # days since last game (0 = back-to-back)
            }
            game_context: {
                'team_pace': float,
                'opponent_pace': float,
                'opponent_def_rating': float,   # lower = better defense
                'is_home': bool,
            }
            over_odds: float    — American odds for over
            under_odds: float   — American odds for under

        Returns:
            PropProjection with all probabilities and Bayesian inputs populated
        """
        player_id = player_data['player_id']
        player_name = player_data['player_name']
        stat_type = player_data['stat_type']
        line = player_data['line']
        season_avg = player_data['season_avg']

        logger.info(
            f"Projecting {player_name} {stat_type} vs line {line} "
            f"(season avg {season_avg})"
        )

        # Base distribution
        base_mean = season_avg
        std_factor = STAT_STD_FACTORS.get(stat_type, 0.40)
        base_std = max(MIN_STD, base_mean * std_factor)

        # Compute adjustments (returns dict of {factor: delta_mean})
        adjustments = self._compute_mean_adjustments(player_data, game_context, base_mean)
        total_adj = sum(v for k, v in adjustments.items() if not k.startswith('_'))

        projected_mean = max(0.5, base_mean + total_adj)
        projected_std = self._compute_std(projected_mean, player_data, std_factor)

        # Model probabilities (Normal CDF)
        model_p_over = float(1.0 - stats.norm.cdf(line, loc=projected_mean, scale=projected_std))
        model_p_under = float(stats.norm.cdf(line, loc=projected_mean, scale=projected_std))

        # Market probabilities
        market_p_over, market_p_under = PropAnalyzer.devig_prop(over_odds, under_odds)
        market_over_implied = PropAnalyzer._american_to_implied(over_odds)

        # Edge
        model_edge_over = model_p_over - market_over_implied
        model_edge_under = model_p_under - (1.0 - market_over_implied)

        projection = PropProjection(
            player_id=player_id,
            player_name=player_name,
            stat_type=stat_type,
            line=line,
            base_mean=round(base_mean, 2),
            base_std=round(base_std, 2),
            adjustments=adjustments,
            projected_mean=round(projected_mean, 2),
            projected_std=round(projected_std, 2),
            model_p_over=round(model_p_over, 4),
            model_p_under=round(model_p_under, 4),
            market_p_over=round(market_p_over, 4),
            market_p_under=round(market_p_under, 4),
            market_over_implied=round(market_over_implied, 4),
            model_edge_over=round(model_edge_over, 4),
            model_edge_under=round(model_edge_under, 4),
            # Bayesian inputs: devig_prob = market devigged (sharp market prior)
            # implied_prob = retail implied (what we're betting into)
            devig_prob=round(market_p_over, 4),
            implied_prob=round(market_over_implied, 4),
        )

        logger.info(
            f"{player_name} {stat_type} {line}: "
            f"μ={projected_mean:.1f} σ={projected_std:.1f} "
            f"P(over)={model_p_over:.3f} edge={model_edge_over:+.3f}"
        )

        return projection

    def _compute_mean_adjustments(
        self,
        player_data: Dict,
        game_context: Dict,
        base_mean: float,
    ) -> Dict[str, float]:
        """
        Compute mean adjustments for each factor.

        Mirrors BayesianAnalyzer._compute_adjustments() in structure —
        returns a dict of {factor: delta} in the same units (delta to mean),
        rather than delta to probability, since we operate on the raw stat scale.

        Factors are scaled to be additive on the stat (e.g., +1.2 points, -0.3 assists).
        """
        adjustments: Dict[str, float] = {}

        # --- Recent form ---
        last_5_avg = player_data.get('last_5_avg', base_mean)
        form_delta = (last_5_avg - base_mean) * 0.40  # blend 40% toward recent form
        adjustments['recent_form'] = round(form_delta, 3)

        # --- Pace adjustment ---
        team_pace = game_context.get('team_pace', LEAGUE_AVG_PACE)
        opp_pace = game_context.get('opponent_pace', LEAGUE_AVG_PACE)
        game_pace = (team_pace + opp_pace) / 2.0
        pace_delta = (game_pace - LEAGUE_AVG_PACE) / LEAGUE_AVG_PACE
        # Each 1% faster pace ≈ +1% more volume
        adjustments['pace'] = round(base_mean * pace_delta, 3)
        # Store raw values for feature dict (prefixed _ = excluded from total_adj sum)
        adjustments['_team_pace'] = team_pace
        adjustments['_opp_pace'] = opp_pace

        # --- Matchup (opponent defensive rating vs position) ---
        opp_def_rating = game_context.get('opponent_def_rating', LEAGUE_AVG_DEF_RATING)
        # Worse defense (higher rating) = more stat production
        def_delta = (opp_def_rating - LEAGUE_AVG_DEF_RATING) / LEAGUE_AVG_DEF_RATING
        adjustments['matchup'] = round(base_mean * def_delta * 0.5, 3)

        # --- Usage rate trend ---
        usage_trend = player_data.get('usage_trend', 0.0)  # positive = usage rising
        adjustments['usage_trend'] = round(base_mean * usage_trend * 0.15, 3)

        # --- Injury / rest ---
        injury_status = player_data.get('injury_status', 'ACTIVE')
        if injury_status == 'QUESTIONABLE':
            adjustments['injury'] = round(-base_mean * 0.08, 3)
        elif injury_status == 'OUT':
            adjustments['injury'] = round(-base_mean * 0.99, 3)  # player doesn't play
        else:
            adjustments['injury'] = 0.0

        rest_days = player_data.get('rest_days', 2)
        if rest_days == 0:  # back-to-back
            adjustments['rest'] = round(-base_mean * 0.04, 3)
        elif rest_days >= 3:  # well-rested
            adjustments['rest'] = round(base_mean * 0.02, 3)
        else:
            adjustments['rest'] = 0.0

        # --- Home/away ---
        is_home = game_context.get('is_home', False)
        adjustments['home_advantage'] = round(base_mean * 0.02, 3) if is_home else round(-base_mean * 0.01, 3)

        # --- DvP positional modifier ---
        # When available (from NBADvPAnalyzer or NCAABDvPAnalyzer), dvp_modifier
        # is the % delta vs league average for the opposing defense at the
        # player's position and stat type.  E.g. +0.06 → opponent allows 6%
        # more than average.
        dvp_modifier = game_context.get('dvp_modifier')
        if dvp_modifier is not None and dvp_modifier != 0.0:
            adjustments['dvp_positional'] = round(base_mean * dvp_modifier * 0.60, 3)
        else:
            adjustments['dvp_positional'] = 0.0

        return adjustments

    def _compute_std(
        self,
        projected_mean: float,
        player_data: Dict,
        std_factor: float,
    ) -> float:
        """
        Compute adjusted standard deviation.

        Base σ = projected_mean × std_factor.
        Widens slightly for injury concern (higher variance when status uncertain).
        """
        base_std = max(MIN_STD, projected_mean * std_factor)

        injury_status = player_data.get('injury_status', 'ACTIVE')
        if injury_status == 'QUESTIONABLE':
            base_std *= 1.15  # more uncertain

        return round(base_std, 2)

    def batch_project(
        self,
        props: list,  # List of (player_data, game_context, over_odds, under_odds)
    ) -> list:
        """
        Project a slate of props. Returns list of PropProjection objects.

        Args:
            props: List of tuples (player_data, game_context, over_odds, under_odds)

        Returns:
            List[PropProjection] sorted by abs(best_edge) descending
        """
        projections = []
        for player_data, game_context, over_odds, under_odds in props:
            try:
                proj = self.project(player_data, game_context, over_odds, under_odds)
                projections.append(proj)
            except Exception as e:
                logger.error(
                    f"Projection failed for {player_data.get('player_name')}: {e}"
                )

        return sorted(projections, key=lambda p: abs(p.best_edge), reverse=True)
