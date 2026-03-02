"""
Unit tests for parlay helper functions in app/routers/parlays.py.

Covers:
- calculate_parlay_odds: correct combined decimal and American odds
- calculate_parlay_ev: vig-compounding, EV sign, true_combined_prob
- _parlay_risk_summary: leg count and sport concentration warnings

All tests are pure-unit: no database, no network.
"""
import pytest
import math

from app.routers.parlays import (
    calculate_parlay_odds,
    calculate_parlay_ev,
    _parlay_risk_summary,
    _american_to_decimal,
    _implied_prob,
    ParlayLegCreate,
)


# ---------------------------------------------------------------------------
# calculate_parlay_odds
# ---------------------------------------------------------------------------

class TestCalculateParlayOdds:
    def test_single_leg_passthrough(self):
        """One leg: parlay odds == that leg's odds."""
        american, decimal_mult = calculate_parlay_odds([-110])
        assert abs(decimal_mult - _american_to_decimal(-110)) < 0.001

    def test_two_leg_even_money(self):
        """Two +100 legs: 2.0 × 2.0 = 4.0 decimal → +300 American."""
        american, decimal_mult = calculate_parlay_odds([100, 100])
        assert abs(decimal_mult - 4.0) < 0.001
        assert abs(american - 300.0) < 1.0

    def test_two_leg_minus_110(self):
        """2-leg -110/-110: 1.909^2 ≈ 3.645 decimal → roughly +264 American."""
        american, decimal_mult = calculate_parlay_odds([-110, -110])
        assert abs(decimal_mult - (1.909090) ** 2) < 0.01
        assert american > 260 and american < 270

    def test_three_leg_minus_110(self):
        """3-leg at -110: decimal ≈ 6.96, American > +596."""
        american, decimal_mult = calculate_parlay_odds([-110, -110, -110])
        assert decimal_mult == pytest.approx(1.90909 ** 3, rel=0.01)
        assert american > 590

    def test_combined_decimal_increases_with_legs(self):
        """Adding more legs always increases the payout multiplier."""
        _, d1 = calculate_parlay_odds([-110])
        _, d2 = calculate_parlay_odds([-110, -110])
        _, d3 = calculate_parlay_odds([-110, -110, -110])
        assert d1 < d2 < d3

    def test_mixed_positive_negative_odds(self):
        """+150 leg × -110 leg = 2.50 × 1.909 ≈ 4.77 decimal."""
        american, decimal_mult = calculate_parlay_odds([150, -110])
        assert abs(decimal_mult - 2.50 * _american_to_decimal(-110)) < 0.01


# ---------------------------------------------------------------------------
# calculate_parlay_ev
# ---------------------------------------------------------------------------

class TestCalculateParlayEV:
    def test_empty_returns_empty_dict(self):
        result = calculate_parlay_ev([], 1.0)
        assert result == {}

    def test_single_fair_leg_ev_near_zero(self):
        """Single -110 leg at fair devigged price: EV should be slightly negative (vig cost)."""
        _, payout = calculate_parlay_odds([-110])
        result = calculate_parlay_ev([-110], payout)
        # Single leg at offered odds is always -EV (vig baked in)
        assert result["ev_per_unit"] < 0.0

    def test_vig_cost_increases_with_leg_count(self):
        """Each additional -110 leg must increase the vig cost percentage."""
        costs = []
        legs = []
        for _ in range(1, 6):
            legs.append(-110)
            _, payout = calculate_parlay_odds(legs)
            ev = calculate_parlay_ev(legs[:], payout)
            costs.append(ev["vig_cost_pct"])
        assert all(costs[i] < costs[i + 1] for i in range(len(costs) - 1))

    def test_true_combined_prob_is_product_of_devigged_probs(self):
        """true_combined_prob should equal the product of each leg's devigged probability."""
        legs = [-110, -110]
        _, payout = calculate_parlay_odds(legs)
        result = calculate_parlay_ev(legs, payout)
        expected = math.prod(_implied_prob(o) / 1.025 for o in legs)
        assert abs(result["true_combined_prob"] - expected) < 1e-6

    def test_offered_payout_matches_calculate_parlay_odds(self):
        """offered_payout in EV result must equal payout_multiplier from calculate_parlay_odds."""
        legs = [-110, 150, -120]
        _, payout = calculate_parlay_odds(legs)
        result = calculate_parlay_ev(legs, payout)
        assert abs(result["offered_payout"] - payout) < 0.001

    def test_fair_payout_exceeds_offered_payout(self):
        """fair_payout (1 / true_combined_prob) must exceed offered payout — that's the vig."""
        legs = [-110, -110, -110]
        _, payout = calculate_parlay_odds(legs)
        result = calculate_parlay_ev(legs, payout)
        assert result["fair_payout"] > result["offered_payout"]

    def test_is_positive_ev_false_for_all_negative_legs(self):
        """A pure -110/-110 parlay is never +EV (assuming no edge on any leg)."""
        _, payout = calculate_parlay_odds([-110, -110])
        result = calculate_parlay_ev([-110, -110], payout)
        assert result["is_positive_ev"] is False

    def test_five_leg_vig_cost_above_twenty_percent(self):
        """5-leg parlay at -110 each surrenders > 20% of fair value to vig."""
        legs = [-110] * 5
        _, payout = calculate_parlay_odds(legs)
        result = calculate_parlay_ev(legs, payout)
        assert result["vig_cost_pct"] > 20.0


# ---------------------------------------------------------------------------
# _parlay_risk_summary (assess_parlay_risk integration)
# ---------------------------------------------------------------------------

class TestParlayRiskSummary:
    def _make_legs(self, n: int, odds: float = -110) -> list:
        return [
            ParlayLegCreate(
                game=f"Game {i}",
                pick=f"Team {i}",
                odds=odds,
                reasoning="test",
                team=f"Team {i}",
                market="spread",
            )
            for i in range(n)
        ]

    def test_small_parlay_no_size_warning(self):
        """4-leg parlay should produce no PARLAY_SIZE warning."""
        result = _parlay_risk_summary(self._make_legs(4), "NCAAB")
        warning_types = [w["type"] for w in result.get("warnings", [])]
        assert "PARLAY_SIZE" not in warning_types

    def test_seven_leg_parlay_triggers_medium_warning(self):
        """7-leg parlay must trigger a MEDIUM PARLAY_SIZE warning."""
        result = _parlay_risk_summary(self._make_legs(7), "NCAAB")
        parlay_size_warnings = [
            w for w in result.get("warnings", []) if w["type"] == "PARLAY_SIZE"
        ]
        assert len(parlay_size_warnings) >= 1
        assert parlay_size_warnings[0]["severity"] == "MEDIUM"

    def test_nine_leg_parlay_triggers_high_warning(self):
        """9-leg parlay must trigger a HIGH PARLAY_SIZE warning."""
        result = _parlay_risk_summary(self._make_legs(9), "NCAAB")
        parlay_size_warnings = [
            w for w in result.get("warnings", []) if w["type"] == "PARLAY_SIZE"
        ]
        assert len(parlay_size_warnings) >= 1
        assert parlay_size_warnings[0]["severity"] == "HIGH"

    def test_result_contains_required_keys(self):
        """Risk summary must include the standard keys from assess_parlay_risk."""
        result = _parlay_risk_summary(self._make_legs(3), "NBA")
        for key in ("parlay_risk_score", "leg_count", "warnings", "recommendation"):
            assert key in result

    def test_risk_score_increases_with_leg_count(self):
        """Risk score for a 9-leg parlay must exceed risk score for a 4-leg parlay."""
        r_small = _parlay_risk_summary(self._make_legs(4), "NBA")
        r_large = _parlay_risk_summary(self._make_legs(9), "NBA")
        assert r_large["parlay_risk_score"] > r_small["parlay_risk_score"]

    def test_high_risk_recommendation_for_nine_legs(self):
        """9-leg parlay should produce HIGH_RISK recommendation."""
        result = _parlay_risk_summary(self._make_legs(9), "NBA")
        assert "HIGH_RISK" in result["recommendation"]
