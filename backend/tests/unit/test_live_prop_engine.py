"""
Unit tests for LivePropEngine — verifying the three logic fixes:

  1. implied_p_under is derived from under_odds independently (not 1 - implied_p_over)
  2. Kelly fraction uses best-side's odds and probability
  3. Verdict SMALL tier covers 3-5% edge; FADE targets best_side for negative-edge cases
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.live_prop_engine import (
    LivePropEngine,
    LivePropProjection,
    LiveGameState,
    LivePlayerState,
    LivePropLine,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _game_state(minutes_remaining: float = 20.0, score_diff: int = 2) -> LiveGameState:
    home_score = 50 + score_diff
    return LiveGameState(
        game_id="test_game",
        sport="nba",
        period=3,
        minutes_remaining=minutes_remaining,
        home_team="HOME",
        away_team="AWAY",
        home_score=home_score,
        away_score=50,
        actual_pace=100.0,
    )


def _player(stat_type: str = "points", current_stat: float = 18.0, minutes_played: float = 28.0) -> LivePlayerState:
    return LivePlayerState(
        player_id="test_player",
        player_name="Test Player",
        team="HOME",
        stat_type=stat_type,
        current_stat=current_stat,
        minutes_played=minutes_played,
        fouls=0,
        is_star=True,
    )


def _season_data(season_avg: float = 25.0, avg_minutes: float = 35.0) -> dict:
    return {
        "season_avg": season_avg,
        "avg_minutes": avg_minutes,
        "expected_pace": 100.0,
    }


# ---------------------------------------------------------------------------
# Bug 1: implied_p_under must use under_odds, not (1 - implied_p_over)
# ---------------------------------------------------------------------------

class TestImpliedUnderFromOdds:
    """implied_p_under should be independently derived from under_odds."""

    def test_implied_p_under_from_under_odds_not_complement(self) -> None:
        """
        When over and under have different vig, implied_p_under must NOT equal
        1 - implied_p_over. The two must sum to more than 1.0 (the book's vig).
        """
        engine = LivePropEngine()
        # Asymmetric odds: over at -110 (52.4% implied), under at -130 (56.5% implied)
        line = LivePropLine(threshold=25.5, over_odds=-110, under_odds=-130)
        proj = engine.analyze(
            player=_player(),
            game_state=_game_state(),
            player_season_data=_season_data(),
            live_line=line,
        )
        # With the fix, implied_p_over + implied_p_under > 1.0 (vig > 0)
        total_implied = proj.implied_p_over + proj.implied_p_under
        assert total_implied > 1.0, (
            f"Expected vig: implied_p_over + implied_p_under > 1.0, got {total_implied:.4f}"
        )

    def test_implied_p_under_matches_under_odds_directly(self) -> None:
        """implied_p_under must equal _american_to_implied(under_odds)."""
        from app.services.prop_analyzer import PropAnalyzer

        engine = LivePropEngine()
        over_odds = -110
        under_odds = -130
        line = LivePropLine(threshold=25.5, over_odds=over_odds, under_odds=under_odds)
        proj = engine.analyze(
            player=_player(),
            game_state=_game_state(),
            player_season_data=_season_data(),
            live_line=line,
        )
        expected_implied_under = PropAnalyzer._american_to_implied(under_odds)
        # Projection rounds to 4 decimal places, so allow 1e-4 tolerance
        assert abs(proj.implied_p_under - expected_implied_under) < 1e-4, (
            f"implied_p_under={proj.implied_p_under:.6f} "
            f"expected={expected_implied_under:.6f}"
        )

    def test_edge_under_not_simply_negative_edge_over(self) -> None:
        """
        With asymmetric odds, edge_under should NOT equal -edge_over.
        (Pre-fix this was always equal because implied_p_under = 1 - implied_p_over.)
        """
        engine = LivePropEngine()
        # Meaningful vig difference: over favored, under more expensive
        line = LivePropLine(threshold=25.5, over_odds=-110, under_odds=-150)
        proj = engine.analyze(
            player=_player(),
            game_state=_game_state(),
            player_season_data=_season_data(),
            live_line=line,
        )
        assert abs(proj.edge_over + proj.edge_under) > 0.01, (
            "edge_over and edge_under should NOT be perfect negatives of each other "
            "when the book has vig on both sides"
        )

    def test_symmetric_odds_edge_under_equals_negative_edge_over(self) -> None:
        """
        With perfectly symmetric odds (-110 / -110), total implied ≈ 1.048.
        edge_over + edge_under ≈ -vig (both sides penalised equally).
        """
        engine = LivePropEngine()
        line = LivePropLine(threshold=25.5, over_odds=-110, under_odds=-110)
        proj = engine.analyze(
            player=_player(),
            game_state=_game_state(),
            player_season_data=_season_data(),
            live_line=line,
        )
        # With symmetric odds, edge_over and edge_under should be equal magnitudes
        # apart only by the vig penalty shared equally
        assert abs(proj.edge_over + proj.edge_under) < 0.10, (
            "With symmetric odds the total edge should approximately equal -vig"
        )


# ---------------------------------------------------------------------------
# Bug 2: Kelly fraction must use best-side's odds and probability
# ---------------------------------------------------------------------------

class TestKellyBestSide:
    """Kelly fraction must reflect the odds/probability of whichever side has the edge."""

    def _kelly_manual(self, true_prob: float, american_odds: float) -> float:
        from app.core.betting import american_to_decimal
        decimal = american_to_decimal(american_odds)
        raw = max(0.0, (true_prob * decimal - 1.0) / (decimal - 1.0))
        return min(raw * 0.5, 0.10)

    def test_kelly_uses_over_odds_when_over_is_best_side(self) -> None:
        """When over has higher edge, Kelly should be computed from over_odds."""
        engine = LivePropEngine()
        # Favour the over: high current stat, low threshold
        line = LivePropLine(threshold=5.0, over_odds=-110, under_odds=-110)
        player = _player(current_stat=4.0, minutes_played=10.0)  # likely to over
        proj = engine.analyze(
            player=player,
            game_state=_game_state(minutes_remaining=38.0),
            player_season_data=_season_data(season_avg=25.0, avg_minutes=35.0),
            live_line=line,
        )
        if proj.best_side == 'over':
            expected_kelly = self._kelly_manual(proj.true_p_over, line.over_odds)
            assert abs(proj.kelly_fraction - expected_kelly) < 1e-4, (
                f"Kelly should use over odds: expected={expected_kelly:.4f} got={proj.kelly_fraction:.4f}"
            )
        else:
            pytest.fail(
                f"Expected best_side='over' for a below-threshold scenario, got '{proj.best_side}'"
            )

    def test_kelly_uses_under_odds_when_under_is_best_side(self) -> None:
        """When under has higher edge, Kelly should be computed from under_odds."""
        engine = LivePropEngine()
        # Make under best side: player has very high implied probability of UNDER
        # Use large threshold (far above likely projection) + generous under odds
        line = LivePropLine(threshold=60.0, over_odds=+500, under_odds=-800)
        player = _player(current_stat=5.0, minutes_played=35.0)  # very unlikely to reach 60
        proj = engine.analyze(
            player=player,
            game_state=_game_state(minutes_remaining=1.0),
            player_season_data=_season_data(season_avg=20.0, avg_minutes=35.0),
            live_line=line,
        )
        assert proj.best_side == 'under', (
            f"Expected best_side='under' for an unreachable threshold, got '{proj.best_side}'"
        )
        expected_kelly = self._kelly_manual(proj.true_p_under, line.under_odds)
        assert abs(proj.kelly_fraction - expected_kelly) < 1e-4, (
            f"Kelly should use under odds when under is best_side: "
            f"expected={expected_kelly:.4f} got={proj.kelly_fraction:.4f}"
        )

    def test_kelly_non_negative(self) -> None:
        """Kelly fraction should never be negative and must match manual formula."""
        engine = LivePropEngine()
        line = LivePropLine(threshold=25.5, over_odds=-110, under_odds=-110)
        proj = engine.analyze(
            player=_player(),
            game_state=_game_state(),
            player_season_data=_season_data(),
            live_line=line,
        )
        assert proj.kelly_fraction >= 0.0
        # Verify the exact Kelly formula for whichever side was chosen
        expected = self._kelly_manual(
            proj.true_p_over if proj.best_side == "over" else proj.true_p_under,
            line.over_odds if proj.best_side == "over" else line.under_odds,
        )
        assert abs(proj.kelly_fraction - expected) < 1e-4

    def test_kelly_capped_at_10_percent(self) -> None:
        """Kelly fraction should never exceed 0.10 (the cap)."""
        engine = LivePropEngine()
        # Player already hit threshold — near-certain over
        line = LivePropLine(threshold=1.0, over_odds=-110, under_odds=-110)
        player = _player(current_stat=5.0, minutes_played=5.0)  # already past threshold
        proj = engine.analyze(
            player=player,
            game_state=_game_state(minutes_remaining=43.0),
            player_season_data=_season_data(),
            live_line=line,
        )
        assert proj.kelly_fraction <= 0.10


# ---------------------------------------------------------------------------
# Bug 3: Verdict tiers — SMALL for 3-5%, FADE targets best_side
# ---------------------------------------------------------------------------

class TestVerdictTiers:
    """Verdict property must correctly classify all edge ranges."""

    def _make_proj(self, edge_over: float, edge_under: float) -> LivePropProjection:
        """Build a minimal LivePropProjection with given edges.

        true_p_over and true_p_under are set so they sum to 1.0 and are
        centered at 0.5, independent of edge_under (which may differ from
        -edge_over when vig is accounted for).
        """
        true_p_over = 0.5 + edge_over
        return LivePropProjection(
            player_name="Test",
            stat_type="points",
            threshold=25.5,
            current_stat=15.0,
            minutes_remaining=20.0,
            season_per_minute=0.5,
            current_per_minute=0.5,
            blended_per_minute=0.5,
            hot_hand_factor=1.0,
            pace_factor=1.0,
            garbage_time_discount=1.0,
            foul_discount=1.0,
            effective_minutes=20.0,
            projected_remaining=10.0,
            projected_final=25.0,
            remaining_needed=10.5,
            sigma_remaining=3.0,
            true_p_over=true_p_over,
            true_p_under=1.0 - true_p_over,
            implied_p_over=0.5,
            implied_p_under=0.5,
            devig_p_over=0.5,
            edge_over=edge_over,
            edge_under=edge_under,
            kelly_fraction=0.02,
            over_odds=-110,
            under_odds=-110,
        )

    def test_strong_over_at_25_pct_edge(self) -> None:
        proj = self._make_proj(edge_over=0.25, edge_under=-0.25)
        assert proj.verdict == "STRONG OVER"

    def test_lean_over_at_15_pct_edge(self) -> None:
        proj = self._make_proj(edge_over=0.15, edge_under=-0.15)
        assert proj.verdict == "LEAN OVER"

    def test_marginal_over_at_7_pct_edge(self) -> None:
        proj = self._make_proj(edge_over=0.07, edge_under=-0.07)
        assert proj.verdict == "MARGINAL OVER"

    def test_small_over_at_4_pct_edge(self) -> None:
        """3–5% edge must produce SMALL, not FADE (pre-fix this was FADE)."""
        proj = self._make_proj(edge_over=0.04, edge_under=-0.04)
        assert proj.verdict == "SMALL OVER", (
            f"Expected 'SMALL OVER' for 4% edge, got '{proj.verdict}'"
        )

    def test_small_over_at_3_pct_edge(self) -> None:
        """Exactly 3% edge should also be SMALL."""
        proj = self._make_proj(edge_over=0.03, edge_under=-0.03)
        assert proj.verdict == "SMALL OVER"

    def test_pass_at_zero_edge(self) -> None:
        proj = self._make_proj(edge_over=0.00, edge_under=0.00)
        assert proj.verdict == "PASS"

    def test_pass_at_small_negative_edge(self) -> None:
        proj = self._make_proj(edge_over=-0.01, edge_under=0.01)
        # best_side = 'under' (edge_under > edge_over), best_edge = 0.01
        assert proj.verdict == "PASS"

    def test_fade_best_side_not_opposite(self) -> None:
        """FADE must name best_side, not the opposite (pre-fix was reversed)."""
        # best_side = 'over' (edge_over > edge_under), best_edge = -0.05
        proj = self._make_proj(edge_over=-0.05, edge_under=-0.10)
        assert proj.best_side == "over"
        assert proj.verdict == "FADE OVER", (
            f"FADE should target best_side='over', got '{proj.verdict}'"
        )

    def test_fade_under_when_under_is_best_side(self) -> None:
        """FADE UNDER when edge_under > edge_over and both negative."""
        proj = self._make_proj(edge_over=-0.10, edge_under=-0.05)
        assert proj.best_side == "under"
        assert proj.verdict == "FADE UNDER"

    def test_lean_over_matches_table_example_ty_jerome(self) -> None:
        """
        Ty Jerome 3PM example from the problem statement:
        edge_over=10%, best_side=OVER → LEAN OVER.
        """
        proj = self._make_proj(edge_over=0.10, edge_under=-0.10)
        assert proj.verdict == "LEAN OVER"

    def test_marginal_over_matches_table_example_luka(self) -> None:
        """
        Luka Doncic PTS example from the problem statement:
        edge_over=8%, best_side=OVER → MARGINAL OVER.
        """
        proj = self._make_proj(edge_over=0.08, edge_under=-0.08)
        assert proj.verdict == "MARGINAL OVER"
