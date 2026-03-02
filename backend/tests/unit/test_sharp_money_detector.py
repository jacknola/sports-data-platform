"""
Unit tests for SharpMoneyDetector (app/services/sharp_money_detector.py).

All tests are pure-unit: no external I/O, no database.
"""
import pytest

from app.services.sharp_money_detector import SharpMoneyDetector


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
        return SharpMoneyDetector.analyze_game(
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
        """
        For a -110 Pinnacle line (52.38% raw implied), stripping ~2.5% vig
        must yield a true probability strictly less than the raw implied.
        """
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        pinnacle_raw = SharpMoneyDetector._american_to_implied_static(-110)
        # ev_edge = devigged - retail_implied; both retail sides are the same
        # so edge ≈ devigged_home - pinnacle_raw_home
        # devigged_home should be < pinnacle_raw
        # We verify indirectly: for a symmetric -110/-110 market, the retail
        # implied equals the Pinnacle raw implied, so edge = devigged - implied < 0
        assert result["ev_edge"] < 0.0, (
            "Symmetric -110/-110 market should show no edge (or negative) after devigging"
        )

    def test_devigged_prob_near_expected_for_even_market(self):
        """
        For a symmetric -110 / -110 Pinnacle market (true prob ≈ 50%),
        the devigged probability should be close to 0.5110
        (= 0.5238 / 1.025), not the raw 0.5238.
        """
        # Access the devigged value through the edge calculation:
        #   ev_edge = devigged_home - retail_implied
        # If retail is also -110, retail_implied = 0.5238
        # So devigged_home = ev_edge + 0.5238
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        retail_implied = SharpMoneyDetector._american_to_implied_static(-110)
        devigged_home = result["ev_edge"] + retail_implied
        assert abs(devigged_home - 0.5110) < 0.001, (
            f"Expected devigged_home ≈ 0.5110, got {devigged_home:.4f}"
        )

    def test_devigged_heavy_favorite_below_raw_implied(self):
        """
        For -200 Pinnacle odds (raw implied 0.6667), devigged must be
        0.6667 / 1.025 ≈ 0.6504 — strictly less than the raw implied.
        """
        result = self._run(pinnacle_odds=-200, retail_odds=-200)
        retail_implied = SharpMoneyDetector._american_to_implied_static(-200)
        devigged_home = result["ev_edge"] + retail_implied
        expected = SharpMoneyDetector._american_to_implied_static(-200) / 1.025
        assert abs(devigged_home - expected) < 0.001, (
            f"Expected devigged_home ≈ {expected:.4f}, got {devigged_home:.4f}"
        )

    def test_positive_ev_when_retail_worse_than_pinnacle(self):
        """
        When the retail book's implied probability is higher than
        Pinnacle's devigged probability, edge is negative (retail is worse).
        Conversely, when retail offers a higher true-value price, edge > 0.
        """
        # Retail at -120 (implied 0.5455) vs Pinnacle -110 devigged (0.5110)
        # edge = 0.5110 - 0.5455 < 0
        result_negative = self._run(pinnacle_odds=-110, retail_odds=-120)
        assert result_negative["ev_edge"] < 0.0

        # Retail at -100 (+EV: implied 0.50) vs Pinnacle -110 devigged (0.5110)
        # edge = 0.5110 - 0.50 > 0
        result_positive = self._run(pinnacle_odds=-110, retail_odds=100)
        assert result_positive["ev_edge"] > 0.0

    def test_pinnacle_implied_key_is_raw_not_devigged(self):
        """
        The 'pinnacle_implied' key in the result should return the
        raw (viggy) Pinnacle implied probability, as documented.
        """
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        expected_raw = SharpMoneyDetector._american_to_implied_static(-110)
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
