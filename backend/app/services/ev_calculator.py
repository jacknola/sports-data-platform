"""
+EV (Positive Expected Value) Prop Bet Calculation Engine

Calculates true probability from player stats research data, compares against
sportsbook implied probability, and identifies +EV betting opportunities using
a weighted multi-factor model.
"""
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from app.database import SessionLocal
from app.models.defense_vs_position import DefenseVsPosition
from app.services.position_mapper import PositionMapper


# ---------------------------------------------------------------------------
# Supported prop types and their stat key mappings
# ---------------------------------------------------------------------------
PROP_TYPE_KEYS: Dict[str, str] = {
    "points": "pts",
    "rebounds": "reb",
    "assists": "ast",
    "pts+reb+ast": "pra",
    "pts+reb": "pr",
    "pts+ast": "pa",
    "reb+ast": "ra",
    "threes": "fg3m",
    "blocks": "blk",
    "steals": "stl",
    "blocks+steals": "blk_stl",
    "turnovers": "tov",
    # Odds API market keys (alternate spellings)
    "player_points": "pts",
    "player_rebounds": "reb",
    "player_assists": "ast",
    "player_threes": "fg3m",
    "player_blocks": "blk",
    "player_steals": "stl",
    "player_turnovers": "tov",
    "player_points_rebounds_assists": "pra",
    "player_points_rebounds": "pr",
    "player_points_assists": "pa",
    "player_rebounds_assists": "ra",
    "player_blocks_steals": "blk_stl",
    # Alternate line markets (same stats, just different line values)
    "player_points_alternate": "pts",
    "player_rebounds_alternate": "reb",
    "player_assists_alternate": "ast",
    "player_threes_alternate": "fg3m",
}

# ---------------------------------------------------------------------------
# Model weights  (must sum to 1.0)
# ---------------------------------------------------------------------------
MODEL_WEIGHTS: Dict[str, float] = {
    "season_avg": 0.15,
    "l5": 0.30,
    "l10": 0.25,
    "l20": 0.15,
    "matchup": 0.10,
    "trend": 0.05,
}


class EVCalculator:
    """
    Positive-expected-value calculator for NBA player prop bets.

    Combines multiple hit-rate windows, matchup context, and trend signals
    into a single true-probability estimate.  Compares against the sportsbook
    line to surface edge, classify the bet, and size positions via Kelly
    Criterion.
    """

    def __init__(self):
        """Initialize EVCalculator"""
        pass

    # ------------------------------------------------------------------
    # Odds conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def american_to_decimal(american_odds: float) -> float:
        """
        Convert American odds to decimal odds.

        Args:
            american_odds: American-format odds (e.g. -110, +150).

        Returns:
            Decimal odds (e.g. 1.909, 2.50).
        """
        if american_odds >= 100:
            return american_odds / 100.0 + 1.0
        elif american_odds <= -100:
            return 100.0 / abs(american_odds) + 1.0
        else:
            # Edge-case: odds between -100 and 100 are non-standard.
            # Treat positive side as >= 100.
            logger.warning(
                f"Non-standard American odds value: {american_odds}. "
                "Treating as even money."
            )
            return 2.0

    @staticmethod
    def american_to_implied_prob(american_odds: float) -> float:
        """
        Convert American odds to implied probability (no-vig).

        Args:
            american_odds: American-format odds.

        Returns:
            Implied probability as a float in [0, 1].
        """
        if american_odds >= 100:
            return 100.0 / (american_odds + 100.0)
        elif american_odds <= -100:
            return abs(american_odds) / (abs(american_odds) + 100.0)
        else:
            logger.warning(
                f"Non-standard American odds value: {american_odds}. "
                "Returning 0.50."
            )
            return 0.50

    # ------------------------------------------------------------------
    # Hit-rate extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_game_logs(
        research_data: Dict[str, Any], prop_type: str
    ) -> Optional[List[float]]:
        """
        Pull the relevant stat array from research data.

        The research data is expected to follow the NBAStatsAgent output
        schema.  We look for ``game_logs`` -> list of per-game dicts, each
        containing the stat key for the requested prop type.

        Returns:
            A list of per-game stat values (most-recent first), or *None*
            if the data is unavailable.
        """
        stat_key = PROP_TYPE_KEYS.get(prop_type)
        if stat_key is None:
            logger.error(f"Unknown prop type: {prop_type}")
            return None

        game_logs: Optional[List[Dict[str, Any]]] = research_data.get("game_logs")
        if not game_logs:
            logger.warning("No game_logs found in research_data")
            return None

        # Combo stat keys: sum multiple columns per game
        COMBO_KEYS: Dict[str, List[str]] = {
            "pra": ["pts", "reb", "ast"],
            "pr":  ["pts", "reb"],
            "pa":  ["pts", "ast"],
            "ra":  ["reb", "ast"],
            "blk_stl": ["blk", "stl"],
        }

        values: List[float] = []
        if stat_key in COMBO_KEYS:
            sub_keys = COMBO_KEYS[stat_key]
            for game in game_logs:
                parts = [game.get(k) for k in sub_keys]
                if all(p is not None for p in parts):
                    values.append(sum(float(p) for p in parts))
        else:
            for game in game_logs:
                val = game.get(stat_key)
                if val is not None:
                    values.append(float(val))

        if not values:
            logger.warning(f"No values for stat key '{stat_key}' in game_logs")
            return None

        return values

    @staticmethod
    def _hit_rate(values: List[float], line: float, n: Optional[int] = None) -> float:
        """
        Compute the fraction of games in *values* that went **over or pushed** *line*.

        Most sportsbooks treat landing exactly on the line as a push (refund),
        so pushes are NOT losses.  Using ``>=`` avoids systematically
        underestimating P(over).

        Args:
            values: Per-game stat values (most-recent first).
            line:   The sportsbook line to beat.
            n:      If provided, only consider the first *n* values.

        Returns:
            Hit rate as a float in [0, 1].  Returns 0.0 when the slice is
            empty to avoid division-by-zero.
        """
        subset = values[:n] if n is not None else values
        if not subset:
            return 0.0
        hits = sum(1 for v in subset if v >= line)
        return hits / len(subset)

    # ------------------------------------------------------------------
    # Matchup & trend adjustments
    # ------------------------------------------------------------------

    @staticmethod
    def _matchup_adjustment(
        research_data: Dict[str, Any], prop_type: str, line: float
    ) -> float:
        """
        Compute a matchup-based probability adjustment using DvP data.

        Priority:
        1. DvP (Defense vs Position) matchup factor
        2. Legacy matchup/opponent_stats from research_data
        3. Neutral 0.50 when no data available

        Returns:
            A probability adjustment centered around 0.50 (so the raw weight
            application treats it the same as a hit rate).
        """
        
        # Try DvP matchup factor first
        dvp_factor = EVCalculator._get_dvp_matchup_factor(research_data, prop_type)
        if dvp_factor is not None:
            logger.debug(f"Using DvP matchup factor: {dvp_factor:.3f}")
            return dvp_factor
        
        # Fall back to legacy matchup logic
        matchup = research_data.get("matchup", research_data.get("opponent_stats", {}))
        if not matchup:
            return 0.50  # neutral when no data

        stat_key = PROP_TYPE_KEYS.get(prop_type, prop_type)

        # Opponent allows X per game to the position / player
        opp_allows = matchup.get(f"{stat_key}_allowed_per_game")
        if opp_allows is not None:
            opp_allows = float(opp_allows)
            # If the opponent allows more than the line, slight positive signal
            if line > 0:
                ratio = opp_allows / line
                # Clamp to a reasonable range
                return float(np.clip(ratio * 0.50, 0.20, 0.80))

        # Defensive rank (1 = best defense, 30 = worst)
        def_rank = matchup.get(f"{stat_key}_def_rank", matchup.get("def_rank"))
        if def_rank is not None:
            def_rank = float(def_rank)
            # Normalise 1-30 so that rank 30 (worst D) -> 0.65, rank 1 -> 0.35
            return float(np.clip(0.35 + (def_rank - 1) * (0.30 / 29.0), 0.35, 0.65))

        return 0.50

    @staticmethod
    def _get_dvp_matchup_factor(
        research_data: Dict[str, Any], prop_type: str
    ) -> Optional[float]:
        """
        Get DvP-based matchup factor from Defense vs Position rankings.

        Args:
            research_data: Player research data (must include 'player_name', 'opponent')
            prop_type: Prop type (e.g., 'points', 'rebounds', 'assists')

        Returns:
            Matchup factor in [0.30, 0.70] range, or None if DvP data unavailable
        """
        
        player_name = research_data.get("player_name")
        opponent = research_data.get("opponent")
        
        if not player_name or not opponent:
            logger.debug("Missing player_name or opponent for DvP lookup")
            return None
        
        # Normalize team abbreviation
        position_mapper = PositionMapper()
        opponent = position_mapper.normalize_team_abbrev(opponent)
        
        # Get player position (infer from stat type if needed)
        stat_key = PROP_TYPE_KEYS.get(prop_type, prop_type)
        position = position_mapper.get_player_position(player_name, stat_type=stat_key)
        
        # Query DvP data
        session = SessionLocal()
        try:
            dvp = (
                session.query(DefenseVsPosition)
                .filter(
                    DefenseVsPosition.source == "hashtag",
                    DefenseVsPosition.position == position,
                    DefenseVsPosition.team == opponent,
                )
                .first()
            )
            
            if not dvp:
                logger.debug(f"No DvP data for {opponent} vs {position}")
                return None
            
            # Convert DvP rank to matchup factor
            # Rank scale: 1 (best defense) to 150 (worst defense)
            # Factor scale: 0.30 (elite defense) to 0.70 (worst defense)
            rank = dvp.rank
            
            if rank <= 50:
                # Elite defense (ranks 1-50): 0.30-0.40
                factor = 0.30 + (rank - 1) / 49.0 * 0.10
            elif rank <= 100:
                # Average defense (ranks 51-100): 0.40-0.55
                factor = 0.40 + (rank - 51) / 49.0 * 0.15
            elif rank <= 140:
                # Weak defense (ranks 101-140): 0.55-0.65
                factor = 0.55 + (rank - 101) / 39.0 * 0.10
            else:
                # Worst defenses (ranks 141-150): 0.65-0.70
                factor = 0.65 + min((rank - 141) / 9.0 * 0.05, 0.05)
            
            logger.info(
                f"DvP matchup: {player_name} ({position}) vs {opponent} "
                f"(rank {rank}) → factor {factor:.3f}"
            )
            
            return float(np.clip(factor, 0.30, 0.70))
            
        except Exception as e:
            logger.error(f"Error querying DvP data: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def _trend_adjustment(values: List[float], line: float) -> float:
        """
        Detect a recent trend in the stat values.

        Uses a simple linear regression slope over the last 10 games
        (most-recent first means index 0 is newest).

        Returns:
            A probability-like value centered on 0.50.
        """
        window = values[:10]
        if len(window) < 3:
            return 0.50

        # Reverse so index increases with time (oldest -> newest)
        window_chrono = list(reversed(window))
        x = np.arange(len(window_chrono), dtype=np.float64)
        y = np.array(window_chrono, dtype=np.float64)

        # Slope via least-squares
        slope = float(np.polyfit(x, y, 1)[0])

        # Normalise: a slope of +2 pts/game is very strong positive
        # Map slope to a 0.35-0.65 range around 0.50
        normalised = 0.50 + np.clip(slope / 4.0, -0.15, 0.15)
        return float(normalised)

    # ------------------------------------------------------------------
    # Core: true probability computation
    # ------------------------------------------------------------------

    def compute_true_probability(
        self,
        research_data: Dict[str, Any],
        prop_type: str,
        line: float,
    ) -> float:
        """
        Compute the model's true probability that the player goes OVER
        the given *line* for *prop_type*.

        Weighted model components:
            - season_avg  (0.15)  full-season hit rate
            - l5          (0.30)  last-5-game hit rate
            - l10         (0.25)  last-10-game hit rate
            - l20         (0.15)  last-20-game hit rate
            - matchup     (0.10)  opponent defensive context
            - trend       (0.05)  recent trajectory

        Args:
            research_data: NBAStatsAgent output dict.
            prop_type:     One of the supported PROP_TYPE_KEYS.
            line:          Sportsbook line value.

        Returns:
            True probability in [0, 1].
        """
        values = self._extract_game_logs(research_data, prop_type)
        if values is None or len(values) == 0:
            logger.warning(
                "Insufficient data for true probability; returning 0.50"
            )
            return 0.50

        # Per-window hit rates
        season_hr = self._hit_rate(values, line)
        l5_hr = self._hit_rate(values, line, n=5)
        l10_hr = self._hit_rate(values, line, n=10)
        l20_hr = self._hit_rate(values, line, n=20)

        # Contextual adjustments
        matchup_adj = self._matchup_adjustment(research_data, prop_type, line)
        trend_adj = self._trend_adjustment(values, line)

        components: Dict[str, float] = {
            "season_avg": season_hr,
            "l5": l5_hr,
            "l10": l10_hr,
            "l20": l20_hr,
            "matchup": matchup_adj,
            "trend": trend_adj,
        }

        weighted_prob = sum(
            MODEL_WEIGHTS[k] * components[k] for k in MODEL_WEIGHTS
        )

        # Clamp to avoid extreme tails
        true_prob = float(np.clip(weighted_prob, 0.05, 0.95))

        logger.debug(
            f"True probability for {prop_type} > {line}: {true_prob:.4f} "
            f"(components: {components})"
        )

        return true_prob

    # ------------------------------------------------------------------
    # Confidence estimation
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_confidence(
        research_data: Dict[str, Any],
        values: Optional[List[float]],
    ) -> float:
        """
        Estimate confidence in the true-probability estimate on a 0-1 scale.

        Factors:
            - Sample size (more games = higher confidence)
            - Variance of the stat (lower variance = higher confidence)
            - Data freshness (research_data timestamp, if available)

        Returns:
            Confidence score in [0, 1].
        """
        confidence = 0.50  # baseline

        if values is None or len(values) == 0:
            return 0.20

        # Sample size bonus: 40+ games -> full bonus of 0.20
        n_games = len(values)
        sample_bonus = min(n_games / 40.0, 1.0) * 0.20
        confidence += sample_bonus

        # Low-variance bonus (coefficient of variation)
        arr = np.array(values, dtype=np.float64)
        mean_val = np.mean(arr)
        if mean_val > 0:
            cv = float(np.std(arr) / mean_val)
            # CV < 0.20 is very consistent -> +0.15 bonus
            variance_bonus = max(0.0, (0.40 - cv) / 0.40) * 0.15
            confidence += variance_bonus

        # Data freshness bonus
        timestamp = research_data.get("timestamp") or research_data.get("updated_at")
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                else:
                    ts = timestamp
                hours_old = (datetime.now(ts.tzinfo) - ts).total_seconds() / 3600.0
                if hours_old < 6:
                    confidence += 0.10
                elif hours_old < 24:
                    confidence += 0.05
            except Exception:
                pass  # silently skip if timestamp is unparseable

        return float(np.clip(confidence, 0.10, 0.99))

    # ------------------------------------------------------------------
    # Bet classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify_bet(edge: float, confidence: float) -> str:
        """
        Classify a bet based on edge and confidence using dynamic settings.

        Classification rules (edge thresholds are confidence-adjusted):
            - "strong_play" : edge >= HIGH threshold
            - "good_play"   : edge >= MEDIUM threshold
            - "lean"        : edge >= LOW threshold
            - "pass"        : otherwise

        A low-confidence estimate (< 0.40) downgrades the classification
        by one tier.
        """
        from app.config import settings

        tiers = ["strong_play", "good_play", "lean", "pass"]

        if edge >= settings.EDGE_THRESHOLD_HIGH:
            tier_idx = 0
        elif edge >= settings.EDGE_THRESHOLD_MEDIUM:
            tier_idx = 1
        elif edge >= settings.EDGE_THRESHOLD_LOW:
            tier_idx = 2
        else:
            tier_idx = 3

        # Downgrade one tier when confidence is low
        if confidence < 0.40 and tier_idx < 3:
            tier_idx += 1
            logger.debug(
                f"Low confidence ({confidence:.2f}) downgraded tier to "
                f"{tiers[tier_idx]}"
            )

        return tiers[tier_idx]

    # ------------------------------------------------------------------
    # Kelly Criterion stake sizing
    # ------------------------------------------------------------------

    @staticmethod
    def kelly_stake(
        true_prob: float,
        decimal_odds: float,
        bankroll: float,
        fraction: Optional[float] = None,
    ) -> float:
        """
        Calculate the recommended stake via fractional Kelly Criterion.

        Formula:
            full_kelly = (p * b - q) / b
            where p = true_prob, q = 1 - p, b = decimal_odds - 1

        Uses fractional multiplier and max bet cap from settings.
        """
        from app.config import settings

        if decimal_odds <= 1.0 or true_prob <= 0.0 or true_prob >= 1.0:
            return 0.0

        b = decimal_odds - 1.0
        q = 1.0 - true_prob
        full_kelly = (true_prob * b - q) / b

        if full_kelly <= 0.0:
            return 0.0

        # Edge-based multiplier (simplified here as edge isn't passed)
        # Use provided fraction or default to settings.KELLY_FRACTION_QUARTER
        multiplier = fraction if fraction is not None else settings.KELLY_FRACTION_QUARTER
        fractional_kelly = full_kelly * multiplier

        # Hard cap from settings (default 5%)
        capped = min(fractional_kelly, settings.MAX_BET_PERCENTAGE)
        stake = round(capped * bankroll, 2)

        logger.debug(
            f"Kelly stake: full={full_kelly:.4f}, multiplier={multiplier}, "
            f"capped={capped:.4f}, stake=${stake:.2f}"
        )

        return stake

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def calculate_ev(
        self,
        research_data: Dict[str, Any],
        line: float,
        odds: float,
        prop_type: str,
        stake: float = 100.0,
        bankroll: float = 10000.0,
    ) -> Dict[str, Any]:
        """
        Full +EV calculation pipeline for a single prop bet.

        Steps:
            1. Convert American odds to decimal / implied probability.
            2. Compute true probability from the weighted model.
            3. Derive edge, raw EV, confidence-adjusted EV.
            4. Classify the bet.
            5. Compute Kelly-optimal stake.

        Args:
            research_data: NBAStatsAgent output dict containing game_logs,
                           matchup data, and metadata.
            line:          Sportsbook line (e.g. 24.5 points).
            odds:          American odds for the OVER (e.g. -110).
            prop_type:     One of the supported prop types.
            stake:         Notional stake for raw EV computation (default $100).
            bankroll:      Bankroll for Kelly sizing (default $10 000).

        Returns:
            EVResult dictionary:
                - player_name
                - prop_type
                - line
                - american_odds
                - decimal_odds
                - implied_prob
                - true_prob
                - edge
                - ev_raw          (EV at the given notional stake)
                - ev_per_dollar   (EV per $1 wagered)
                - confidence
                - confidence_adjusted_ev
                - classification
                - kelly_fraction
                - recommended_stake
                - model_components  (per-factor breakdown)
                - timestamp
        """
        logger.info(
            f"Calculating EV: {prop_type} > {line} @ {odds} "
            f"(player: {research_data.get('player_name', 'unknown')})"
        )

        # 1. Odds conversion
        decimal_odds = self.american_to_decimal(odds)
        implied_prob = self.american_to_implied_prob(odds)

        # 2. True probability
        true_prob = self.compute_true_probability(research_data, prop_type, line)

        # 3. Edge & EV
        edge = true_prob - implied_prob

        # EV = (true_prob * payout) - (1 - true_prob) * stake
        payout = stake * (decimal_odds - 1.0)
        ev_raw = (true_prob * payout) - ((1.0 - true_prob) * stake)
        ev_per_dollar = ev_raw / stake if stake > 0 else 0.0

        # 4. Confidence & adjusted EV
        game_values = self._extract_game_logs(research_data, prop_type)
        confidence = self._estimate_confidence(research_data, game_values)

        # Penalise EV when confidence is low:
        # adjusted_ev = ev_raw * confidence_multiplier
        # confidence_multiplier ranges from 0.50 (very low confidence) to
        # 1.0 (full confidence).
        confidence_multiplier = 0.50 + 0.50 * confidence
        confidence_adjusted_ev = ev_raw * confidence_multiplier

        # 5. Classification
        classification = self.classify_bet(edge, confidence)

        # 6. Kelly stake
        recommended_stake = self.kelly_stake(
            true_prob, decimal_odds, bankroll, fraction=0.25
        )

        # Full Kelly fraction for reference
        b = decimal_odds - 1.0
        if b > 0 and true_prob > 0:
            full_kelly = max(0.0, (true_prob * b - (1.0 - true_prob)) / b)
        else:
            full_kelly = 0.0

        # Per-component breakdown (for transparency / debugging)
        components: Dict[str, Any] = {}
        if game_values is not None and len(game_values) > 0:
            components = {
                "season_avg_hit_rate": round(self._hit_rate(game_values, line), 4),
                "l5_hit_rate": round(self._hit_rate(game_values, line, 5), 4),
                "l10_hit_rate": round(self._hit_rate(game_values, line, 10), 4),
                "l20_hit_rate": round(self._hit_rate(game_values, line, 20), 4),
                "matchup_factor": round(
                    self._matchup_adjustment(research_data, prop_type, line), 4
                ),
                "trend_factor": round(
                    self._trend_adjustment(game_values, line), 4
                ),
                "sample_size": len(game_values),
            }

        result: Dict[str, Any] = {
            "player_name": research_data.get("player_name", "unknown"),
            "prop_type": prop_type,
            "line": line,
            "american_odds": odds,
            "decimal_odds": round(decimal_odds, 4),
            "implied_prob": round(implied_prob, 4),
            "true_prob": round(true_prob, 4),
            "edge": round(edge, 4),
            "ev_raw": round(ev_raw, 2),
            "ev_per_dollar": round(ev_per_dollar, 4),
            "confidence": round(confidence, 4),
            "confidence_multiplier": round(confidence_multiplier, 4),
            "confidence_adjusted_ev": round(confidence_adjusted_ev, 2),
            "classification": classification,
            "kelly_fraction": round(full_kelly, 6),
            "recommended_stake": recommended_stake,
            "model_components": components,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"EV result: edge={edge:.4f}, ev=${ev_raw:.2f}, "
            f"class={classification}, kelly_stake=${recommended_stake:.2f}"
        )

        return result
