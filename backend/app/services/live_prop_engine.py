"""
Live In-Game Prop Engine

Computes residual probability for player props during a live game given:
  - Current accumulated stat (e.g., Ty Jerome has 2 threes)
  - Minutes remaining in the game
  - Player's seasonal per-minute rate
  - Actual game pace vs. expected pace
  - Hot hand adjustment (current game rate vs. season rate)
  - Garbage time discount (blowout + star player sitting risk)
  - Foul trouble discount

Core formula:
    remaining_needed = max(0, threshold - current_stat)
    projected_remaining = blended_per_minute * effective_minutes * pace_factor
    sigma_remaining = projected_remaining * std_factor (shrinks with time elapsed)
    P(over) = 1 - Φ((remaining_needed - projected_remaining) / sigma_remaining)

This fills the gap between the pre-game PropProbabilityModel and actual
live-betting decisions — the same math done manually when analyzing live lines.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats
from loguru import logger

from app.services.prop_analyzer import PropAnalyzer
from app.services.multivariate_kelly import american_to_decimal


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NBA_GAME_MINUTES = 48.0
NCAAB_GAME_MINUTES = 40.0

# Empirical std factors — same as PropProbabilityModel (stat-unit scale)
STAT_STD_FACTORS: Dict[str, float] = {
    'points':   0.40,
    'rebounds': 0.45,
    'assists':  0.50,
    'threes':   0.55,
    'blocks':   0.60,
    'steals':   0.60,
    'pra':      0.35,
}

MIN_STD = 0.5  # tighter floor for live (less total variance remaining)

# Blowout thresholds for garbage time discount
# (score_diff, minutes_remaining) → discount factor for stars vs. role players
_GARBAGE_TABLE: List[Tuple[int, float, float, float]] = [
    # score_diff, max_minutes_remaining, star_discount, role_discount
    (25, 8,  0.40, 0.60),
    (20, 5,  0.40, 0.55),
    (20, 10, 0.65, 0.75),
    (15, 6,  0.75, 0.85),
    (15, 10, 0.85, 0.90),
]

# NBA: foul out at 6; NCAAB: foul out at 5
FOUL_LIMIT: Dict[str, int] = {'nba': 6, 'ncaab': 5}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class LiveGameState:
    """Current state of a live game"""
    game_id: str
    sport: str                  # 'nba' or 'ncaab'
    period: int                 # Quarter (NBA) or Half (NCAAB)
    minutes_remaining: float    # Total game clock remaining, e.g. 33.5
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    actual_pace: float          # Estimated possessions per 48 min based on current game
    is_overtime: bool = False

    @property
    def score_diff(self) -> int:
        return abs(self.home_score - self.away_score)

    @property
    def total_game_minutes(self) -> float:
        return NBA_GAME_MINUTES if self.sport == 'nba' else NCAAB_GAME_MINUTES

    @property
    def minutes_played(self) -> float:
        return self.total_game_minutes - self.minutes_remaining


@dataclass
class LivePlayerState:
    """Player's in-game status"""
    player_id: str
    player_name: str
    team: str
    stat_type: str          # 'points', 'threes', 'rebounds', 'assists', 'pra'
    current_stat: float     # Accumulated so far this game
    minutes_played: float   # Actual minutes this player has been on court
    fouls: int = 0
    is_star: bool = True    # Stars are more likely to sit in blowouts


@dataclass
class LivePropLine:
    """Current live prop market"""
    threshold: float        # Line to evaluate (e.g., 3.5 for 4+ threes)
    over_odds: float        # American odds for over
    under_odds: float       # American odds for under


@dataclass
class LivePropProjection:
    """Full output of the live prop engine for a single player/stat/threshold"""
    player_name: str
    stat_type: str
    threshold: float
    current_stat: float
    minutes_remaining: float

    # Projection components
    season_per_minute: float
    current_per_minute: float
    blended_per_minute: float
    hot_hand_factor: float      # > 1.0 means player is running hot
    pace_factor: float
    garbage_time_discount: float
    foul_discount: float
    effective_minutes: float
    projected_remaining: float
    projected_final: float
    remaining_needed: float
    sigma_remaining: float

    # Probabilities
    true_p_over: float          # Model probability
    true_p_under: float
    implied_p_over: float       # Book implied probability (with vig)
    implied_p_under: float
    devig_p_over: float         # Devigged book probability

    # Edge
    edge_over: float            # true_p_over - implied_p_over
    edge_under: float

    # Sizing
    kelly_fraction: float       # Half-Kelly, capped at 10%
    over_odds: float
    under_odds: float

    @property
    def best_side(self) -> str:
        return 'over' if self.edge_over >= self.edge_under else 'under'

    @property
    def best_edge(self) -> float:
        return max(self.edge_over, self.edge_under)

    @property
    def verdict(self) -> str:
        edge = self.best_edge
        if edge >= 0.20:
            return f'STRONG {self.best_side.upper()}'
        elif edge >= 0.10:
            return f'LEAN {self.best_side.upper()}'
        elif edge >= 0.05:
            return f'MARGINAL {self.best_side.upper()}'
        elif edge >= 0.03:
            return f'SMALL {self.best_side.upper()}'
        elif abs(edge) < 0.03:
            return 'PASS'
        else:
            return f'FADE {self.best_side.upper()}'

    def to_dict(self) -> Dict:
        return {
            'player_name':          self.player_name,
            'stat_type':            self.stat_type,
            'threshold':            self.threshold,
            'current_stat':         self.current_stat,
            'minutes_remaining':    self.minutes_remaining,
            'projected_final':      round(self.projected_final, 2),
            'projected_remaining':  round(self.projected_remaining, 2),
            'remaining_needed':     round(self.remaining_needed, 2),
            'hot_hand_factor':      round(self.hot_hand_factor, 3),
            'pace_factor':          round(self.pace_factor, 3),
            'garbage_time_discount': round(self.garbage_time_discount, 3),
            'foul_discount':        round(self.foul_discount, 3),
            'effective_minutes':    round(self.effective_minutes, 2),
            'sigma_remaining':      round(self.sigma_remaining, 3),
            'true_p_over':          round(self.true_p_over, 4),
            'true_p_under':         round(self.true_p_under, 4),
            'implied_p_over':       round(self.implied_p_over, 4),
            'devig_p_over':         round(self.devig_p_over, 4),
            'edge_over':            round(self.edge_over, 4),
            'edge_under':           round(self.edge_under, 4),
            'best_side':            self.best_side,
            'best_edge':            round(self.best_edge, 4),
            'best_edge_pct':        round(self.best_edge * 100, 2),
            'kelly_fraction':       round(self.kelly_fraction, 4),
            'over_odds':            self.over_odds,
            'under_odds':           self.under_odds,
            'verdict':              self.verdict,
            'is_positive_ev':       self.best_edge >= 0.05,
        }


# ---------------------------------------------------------------------------
# Live Prop Engine
# ---------------------------------------------------------------------------

class LivePropEngine:
    """
    Computes residual probabilities for live player props.

    The key insight: once a game is in progress, we can condition on the
    player's current stat and compute P(final >= threshold | current_stat, minutes_remaining)
    rather than using the pre-game full-game distribution.

    This captures value that pre-game models miss:
    - A player with 2 threes in Q1 is running at a rate where 4+ is much
      more likely than the live line implies
    - Garbage time risk penalizes large over projections in blowouts
    - Foul trouble reduces effective remaining minutes

    Usage:
        engine = LivePropEngine()
        projection = engine.analyze(player, game_state, player_season_data, live_line)
        print(projection.verdict)  # e.g., "STRONG OVER"
    """

    def analyze(
        self,
        player: LivePlayerState,
        game_state: LiveGameState,
        player_season_data: Dict,
        live_line: LivePropLine,
    ) -> LivePropProjection:
        """
        Compute live residual probability for a single player prop.

        Args:
            player: Current in-game player status (stat so far, minutes, fouls)
            game_state: Current game state (clock, score, pace)
            player_season_data: {
                'season_avg': float,        # Season average for this stat
                'avg_minutes': float,       # Average minutes per game (default 32)
                'expected_pace': float,     # Team's expected game pace (possessions/48)
            }
            live_line: Current live prop line with odds

        Returns:
            LivePropProjection with true probability, edge, and verdict
        """
        season_avg = player_season_data['season_avg']
        avg_minutes = player_season_data.get('avg_minutes', 32.0)
        expected_pace = player_season_data.get('expected_pace', 100.0)
        sport = game_state.sport

        logger.info(
            f"[LiveProp] {player.player_name} {player.stat_type} "
            f"current={player.current_stat} threshold={live_line.threshold} "
            f"mins_remaining={game_state.minutes_remaining:.1f}"
        )

        # 1. Per-minute rates
        season_per_minute = season_avg / max(avg_minutes, 1.0)

        if player.minutes_played > 0:
            current_per_minute = player.current_stat / player.minutes_played
        else:
            current_per_minute = season_per_minute

        # 2. Hot hand blending
        # Weight toward current-game rate as game progresses (up to 60% at full game)
        game_progress = min(1.0, player.minutes_played / max(avg_minutes, 1.0))
        hot_hand_weight = min(0.60, game_progress * 1.5)
        blended_per_minute = (
            hot_hand_weight * current_per_minute
            + (1.0 - hot_hand_weight) * season_per_minute
        )
        hot_hand_factor = blended_per_minute / max(season_per_minute, 1e-6)

        # 3. Situational discounts
        garbage_discount = self._garbage_time_discount(
            game_state.score_diff,
            game_state.minutes_remaining,
            player.is_star,
            sport,
        )
        foul_discount = self._foul_discount(player.fouls, game_state.minutes_remaining, sport)

        effective_minutes = game_state.minutes_remaining * garbage_discount * foul_discount

        # 4. Pace adjustment
        actual_pace = game_state.actual_pace
        pace_factor = max(0.80, min(1.20, actual_pace / max(expected_pace, 1.0)))

        # 5. Projected remaining output
        projected_remaining = blended_per_minute * effective_minutes * pace_factor
        projected_final = player.current_stat + projected_remaining
        remaining_needed = max(0.0, live_line.threshold - player.current_stat)

        # 6. σ for remaining output
        # Shrinks with time: less total remaining variance as game nears end
        std_factor = STAT_STD_FACTORS.get(player.stat_type, 0.40)
        time_ratio = effective_minutes / max(avg_minutes, 1.0)
        sigma_remaining = max(MIN_STD, projected_remaining * std_factor * (time_ratio ** 0.5))

        # 7. P(over) — conditional on current stat
        if remaining_needed <= 0:
            # Already hit the threshold
            true_p_over = 0.97
        else:
            true_p_over = float(
                1.0 - stats.norm.cdf(remaining_needed, loc=projected_remaining, scale=sigma_remaining)
            )
        true_p_over = max(0.01, min(0.99, true_p_over))
        true_p_under = 1.0 - true_p_over

        # 8. Market probabilities — derive each side independently from its own odds
        implied_p_over = PropAnalyzer._american_to_implied(live_line.over_odds)
        implied_p_under = PropAnalyzer._american_to_implied(live_line.under_odds)
        devig_p_over, _ = PropAnalyzer.devig_prop(live_line.over_odds, live_line.under_odds)

        # 9. Edge
        edge_over = true_p_over - implied_p_over
        edge_under = true_p_under - implied_p_under

        # 10. Half-Kelly sizing for the best side, capped at 10%
        if edge_over >= edge_under:
            decimal_odds = american_to_decimal(live_line.over_odds)
            raw_kelly = max(0.0, (true_p_over * decimal_odds - 1.0) / (decimal_odds - 1.0))
        else:
            decimal_odds = american_to_decimal(live_line.under_odds)
            raw_kelly = max(0.0, (true_p_under * decimal_odds - 1.0) / (decimal_odds - 1.0))
        kelly_fraction = min(raw_kelly * 0.5, 0.10)

        projection = LivePropProjection(
            player_name=player.player_name,
            stat_type=player.stat_type,
            threshold=live_line.threshold,
            current_stat=player.current_stat,
            minutes_remaining=game_state.minutes_remaining,
            season_per_minute=round(season_per_minute, 4),
            current_per_minute=round(current_per_minute, 4),
            blended_per_minute=round(blended_per_minute, 4),
            hot_hand_factor=round(hot_hand_factor, 3),
            pace_factor=round(pace_factor, 3),
            garbage_time_discount=round(garbage_discount, 3),
            foul_discount=round(foul_discount, 3),
            effective_minutes=round(effective_minutes, 2),
            projected_remaining=round(projected_remaining, 3),
            projected_final=round(projected_final, 3),
            remaining_needed=round(remaining_needed, 3),
            sigma_remaining=round(sigma_remaining, 3),
            true_p_over=round(true_p_over, 4),
            true_p_under=round(true_p_under, 4),
            implied_p_over=round(implied_p_over, 4),
            implied_p_under=round(implied_p_under, 4),
            devig_p_over=round(devig_p_over, 4),
            edge_over=round(edge_over, 4),
            edge_under=round(edge_under, 4),
            kelly_fraction=round(kelly_fraction, 4),
            over_odds=live_line.over_odds,
            under_odds=live_line.under_odds,
        )

        logger.info(
            f"[LiveProp] {player.player_name} {player.stat_type} {live_line.threshold} "
            f"proj_final={projected_final:.1f} P(over)={true_p_over:.3f} "
            f"implied={implied_p_over:.3f} edge={edge_over:+.3f} "
            f"verdict={projection.verdict}"
        )

        return projection

    def analyze_slate(
        self,
        live_props: List[Dict],
    ) -> List[Dict]:
        """
        Analyze a slate of live props and return sorted by edge descending.

        Each dict in live_props must contain:
            player: LivePlayerState
            game_state: LiveGameState
            player_season_data: Dict
            live_line: LivePropLine

        Returns:
            List of projection dicts sorted by best_edge descending,
            filtered to positive EV (edge >= 0.05)
        """
        results = []
        for entry in live_props:
            try:
                proj = self.analyze(
                    player=entry['player'],
                    game_state=entry['game_state'],
                    player_season_data=entry['player_season_data'],
                    live_line=entry['live_line'],
                )
                results.append(proj.to_dict())
            except Exception as e:
                logger.error(f"LivePropEngine error: {e}")

        results.sort(key=lambda x: x['best_edge'], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Situational Discount Helpers
    # ------------------------------------------------------------------

    def _garbage_time_discount(
        self,
        score_diff: int,
        minutes_remaining: float,
        is_star: bool,
        sport: str,
    ) -> float:
        """
        Discount effective minutes for blowout garbage time risk.

        Large leads late in a game mean star players sit. This caps the
        over-optimism when a star is running hot in a blowout.
        """
        for diff_threshold, mins_threshold, star_disc, role_disc in _GARBAGE_TABLE:
            if score_diff >= diff_threshold and minutes_remaining <= mins_threshold:
                return star_disc if is_star else role_disc
        return 1.0

    def _foul_discount(self, fouls: int, minutes_remaining: float, sport: str) -> float:
        """
        Discount effective minutes for foul trouble risk.

        A player near the foul limit will play fewer minutes or not at all.
        """
        limit = FOUL_LIMIT.get(sport, 6)
        fouls_away = limit - fouls

        if fouls_away <= 1:
            return 0.55   # One foul from disqualification — high sit risk
        elif fouls_away == 2 and minutes_remaining > 12:
            return 0.72   # Two away but early enough to be careful
        elif fouls_away == 2:
            return 0.85
        elif fouls_away == 3 and minutes_remaining > 24:
            return 0.88   # 3 fouls in first half (NBA)
        return 1.0


# ---------------------------------------------------------------------------
# Convenience: estimate live game pace from current score/time
# ---------------------------------------------------------------------------

def estimate_live_pace(
    home_score: int,
    away_score: int,
    minutes_played: float,
    sport: str = 'nba',
) -> float:
    """
    Estimate current game pace (possessions per 48 min) from live score/time.

    Assumes each possession ends in roughly 1 point on average (imprecise
    but stable for live pace estimation).

    Args:
        home_score: Current home team score
        away_score: Current away team score
        minutes_played: Minutes elapsed in the game
        sport: 'nba' or 'ncaab'

    Returns:
        Estimated possessions per 48 minutes
    """
    if minutes_played <= 0:
        return 100.0

    total_points = home_score + away_score
    # Approximate: each possession ≈ 1.1 points (league average efficiency)
    estimated_possessions = total_points / 1.1
    # Normalize to per-48-minute rate
    pace = (estimated_possessions / minutes_played) * 48.0
    return round(max(60.0, min(140.0, pace)), 1)
