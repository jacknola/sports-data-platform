"""
Unit tests for LineMovementAnalyzer devigging (migrated from sharp_money_detector tests).

All tests are pure-unit: no external I/O, no database.
"""

from app.services.line_movement_analyzer import LineMovementAnalyzer


# ---------------------------------------------------------------------------
# analyze_game — devigging correctness
# ---------------------------------------------------------------------------

class TestAnalyzeGameDevig:
    """
    Verify that analyze_game correctly removes Pinnacle's vig before
    computing edge against the retail book.

    Pinnacle's typical overround is ~2.5% on spreads/totals.
    The devigged true probability must be LOWER than the raw implied
    probability, since we are stripping out the bookmaker's margin.
    """

    def _run(self, pinnacle_odds: float, retail_odds: float) -> dict:
        return LineMovementAnalyzer.analyze_game(
            game_id="test_game",
            market="spread",
            home_team="Home",
            away_team="Away",
            open_line=-3.5,
            current_line=-3.5,
            home_ticket_pct=0.50,
            home_money_pct=0.50,
            pinnacle_home_odds=pinnacle_odds,
            retail_home_odds=retail_odds,
        )

    def test_devigged_prob_lower_than_raw_implied_for_favorite(self):
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        _ = LineMovementAnalyzer._american_to_implied_static(-110)
        assert result["ev_edge"] < 0.0, (
            "Symmetric -110/-110 market should show no edge (or negative) after devigging"
        )

    def test_devigged_prob_near_expected_for_even_market(self):
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        retail_implied = LineMovementAnalyzer._american_to_implied_static(-110)
        devigged_home = result["ev_edge"] + retail_implied
        assert abs(devigged_home - 0.5110) < 0.001, (
            f"Expected devigged_home ≈ 0.5110, got {devigged_home:.4f}"
        )

    def test_devigged_heavy_favorite_below_raw_implied(self):
        result = self._run(pinnacle_odds=-200, retail_odds=-200)
        retail_implied = LineMovementAnalyzer._american_to_implied_static(-200)
        devigged_home = result["ev_edge"] + retail_implied
        expected = LineMovementAnalyzer._american_to_implied_static(-200) / 1.025
        assert abs(devigged_home - expected) < 0.001, (
            f"Expected devigged_home ≈ {expected:.4f}, got {devigged_home:.4f}"
        )

    def test_positive_ev_when_retail_worse_than_pinnacle(self):
        result_negative = self._run(pinnacle_odds=-110, retail_odds=-120)
        assert result_negative["ev_edge"] < 0.0

        result_positive = self._run(pinnacle_odds=-110, retail_odds=100)
        assert result_positive["ev_edge"] > 0.0

    def test_pinnacle_implied_key_is_raw_not_devigged(self):
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        expected_raw = LineMovementAnalyzer._american_to_implied_static(-110)
        assert abs(result["pinnacle_implied"] - expected_raw) < 0.001


# ---------------------------------------------------------------------------
# CBB kelly_criterion max cap
# ---------------------------------------------------------------------------

class TestCBBKellyCap:
    """
    Verify the CBB edge calculator kelly_criterion respects the 5% max cap
    (platform policy per AGENTS.md: single bet cap = 5% of bankroll).
    """

    def test_kelly_capped_at_five_percent(self):
        from app.services.cbb_edge_calculator import kelly_criterion
        # Very high edge scenario: true_prob=0.99, decimal_odds=10.0
        # Full Kelly would be massive; quarter Kelly should still exceed 5% raw,
        # but the cap must clamp it to 0.05.
        result = kelly_criterion(true_prob=0.99, decimal_odds=10.0, fraction=0.25)
        assert result <= 0.05, f"Kelly capped at 5%, got {result}"

    def test_kelly_below_cap_unaffected(self):
        from app.services.cbb_edge_calculator import kelly_criterion
        # Normal edge: true_prob=0.55, decimal_odds=1.91, quarter kelly < 5%
        result = kelly_criterion(true_prob=0.55, decimal_odds=1.91, fraction=0.25)
        assert 0.0 < result < 0.05

    def test_kelly_negative_ev_returns_zero(self):
        from app.services.cbb_edge_calculator import kelly_criterion
        # Negative EV: true_prob=0.40, decimal_odds=1.91
        result = kelly_criterion(true_prob=0.40, decimal_odds=1.91, fraction=0.25)
        assert result == 0.0
