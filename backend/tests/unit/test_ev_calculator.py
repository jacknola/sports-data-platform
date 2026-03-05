"""
Unit tests for app/services/ev_calculator.py  (EVCalculator class)

Uses the real settings defaults (HIGH=0.07, MEDIUM=0.05, LOW=0.03,
KELLY_FRACTION_QUARTER=0.25, MAX_BET_PERCENTAGE=0.05) — no patching needed.
"""
import pytest

from app.services.ev_calculator import EVCalculator


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def calc():
    return EVCalculator()


def _make_research_data(pts_values):
    return {
        "player_name": "Test Player",
        "game_logs": [{"pts": v} for v in pts_values],
    }


# ---------------------------------------------------------------------------
# american_to_decimal
# ---------------------------------------------------------------------------

class TestAmericanToDecimal:
    def test_positive_odds(self):
        assert EVCalculator.american_to_decimal(200) == pytest.approx(3.0)

    def test_negative_odds(self):
        assert EVCalculator.american_to_decimal(-110) == pytest.approx(100 / 110 + 1)

    def test_even_money(self):
        assert EVCalculator.american_to_decimal(100) == pytest.approx(2.0)

    def test_minus_200(self):
        assert EVCalculator.american_to_decimal(-200) == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# american_to_implied_prob
# ---------------------------------------------------------------------------

class TestAmericanToImpliedProb:
    def test_minus_110_approx_52pct(self):
        assert EVCalculator.american_to_implied_prob(-110) == pytest.approx(110 / 210, rel=1e-4)

    def test_plus_200_is_33pct(self):
        assert EVCalculator.american_to_implied_prob(200) == pytest.approx(100 / 300, rel=1e-4)

    def test_even_money_is_50pct(self):
        assert EVCalculator.american_to_implied_prob(100) == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# _hit_rate
# ---------------------------------------------------------------------------

class TestHitRate:
    def test_all_over_returns_one(self):
        assert EVCalculator._hit_rate([25.0, 26.0, 27.0], 20.0) == pytest.approx(1.0)

    def test_none_over_returns_zero(self):
        assert EVCalculator._hit_rate([10.0, 11.0, 12.0], 15.0) == pytest.approx(0.0)

    def test_half_hit_rate(self):
        assert EVCalculator._hit_rate([25.0, 15.0, 25.0, 15.0], 20.0) == pytest.approx(0.5)

    def test_pushes_counted_as_hits(self):
        assert EVCalculator._hit_rate([20.0, 19.0], 20.0) == pytest.approx(0.5)

    def test_n_limits_window(self):
        assert EVCalculator._hit_rate([25.0, 25.0, 25.0, 10.0, 10.0], 20.0, n=3) == pytest.approx(1.0)

    def test_empty_values_returns_zero(self):
        assert EVCalculator._hit_rate([], 20.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _matchup_adjustment
# ---------------------------------------------------------------------------

class TestMatchupAdjustment:
    def test_no_matchup_data_returns_neutral(self):
        assert EVCalculator._matchup_adjustment({}, "points", 25.0) == pytest.approx(0.50)

    def test_soft_defense_returns_above_neutral(self):
        data = {"matchup": {"pts_allowed_per_game": 30.0}}
        assert EVCalculator._matchup_adjustment(data, "points", 25.0) > 0.50

    def test_tough_defense_returns_below_neutral(self):
        data = {"matchup": {"pts_allowed_per_game": 15.0}}
        assert EVCalculator._matchup_adjustment(data, "points", 25.0) < 0.50

    def test_defensive_rank_30_is_high_prob(self):
        data = {"matchup": {"pts_def_rank": 30}}
        assert EVCalculator._matchup_adjustment(data, "points", 25.0) > 0.55

    def test_defensive_rank_1_is_low_prob(self):
        data = {"matchup": {"pts_def_rank": 1}}
        assert EVCalculator._matchup_adjustment(data, "points", 25.0) < 0.45

    def test_result_within_bounds(self):
        data = {"matchup": {"pts_allowed_per_game": 1000.0}}
        result = EVCalculator._matchup_adjustment(data, "points", 25.0)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# _trend_adjustment
# ---------------------------------------------------------------------------

class TestTrendAdjustment:
    def test_strong_uptrend_returns_above_neutral(self):
        # Most-recent first; reversed for regression: ascending → positive slope
        values = list(reversed([10, 12, 14, 16, 18, 20, 22, 24, 26, 28]))
        assert EVCalculator._trend_adjustment(values, 20.0) > 0.50

    def test_strong_downtrend_returns_below_neutral(self):
        values = list(reversed([28, 26, 24, 22, 20, 18, 16, 14, 12, 10]))
        assert EVCalculator._trend_adjustment(values, 20.0) < 0.50

    def test_flat_trend_returns_near_neutral(self):
        assert EVCalculator._trend_adjustment([20.0] * 10, 20.0) == pytest.approx(0.50)

    def test_fewer_than_3_returns_neutral(self):
        assert EVCalculator._trend_adjustment([25.0, 20.0], 20.0) == pytest.approx(0.50)

    def test_result_within_valid_range(self):
        values = [100.0, 50.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        result = EVCalculator._trend_adjustment(values, 20.0)
        assert 0.35 <= result <= 0.65


# ---------------------------------------------------------------------------
# compute_true_probability
# ---------------------------------------------------------------------------

class TestComputeTrueProbability:
    def test_returns_float_in_0_1(self, calc):
        prob = calc.compute_true_probability(_make_research_data([25.0] * 20), "points", 24.5)
        assert 0.0 <= prob <= 1.0

    def test_hot_player_has_higher_prob(self, calc):
        prob = calc.compute_true_probability(_make_research_data([30.0] * 20), "points", 20.0)
        assert prob > 0.70

    def test_cold_player_has_lower_prob(self, calc):
        prob = calc.compute_true_probability(_make_research_data([10.0] * 20), "points", 25.0)
        assert prob < 0.30

    def test_no_game_logs_returns_half(self, calc):
        prob = calc.compute_true_probability(
            {"player_name": "Unknown", "game_logs": []}, "points", 25.0
        )
        assert prob == pytest.approx(0.50)

    def test_unknown_prop_type_returns_half(self, calc):
        prob = calc.compute_true_probability(_make_research_data([25.0] * 10), "invalid_stat", 20.0)
        assert prob == pytest.approx(0.50)

    def test_result_clamped_between_05_and_95(self, calc):
        prob = calc.compute_true_probability(_make_research_data([100.0] * 40), "points", 0.0)
        assert 0.05 <= prob <= 0.95


# ---------------------------------------------------------------------------
# kelly_stake (real settings: KELLY_FRACTION_QUARTER=0.25, MAX_BET_PERCENTAGE=0.05)
# ---------------------------------------------------------------------------

class TestKellyStake:
    def test_no_edge_returns_zero(self):
        assert EVCalculator.kelly_stake(0.50, 2.0, bankroll=10000) == pytest.approx(0.0, abs=0.01)

    def test_negative_edge_returns_zero(self):
        assert EVCalculator.kelly_stake(0.40, 2.0, bankroll=10000) == pytest.approx(0.0, abs=0.01)

    def test_positive_edge_returns_positive_stake(self):
        assert EVCalculator.kelly_stake(0.60, 2.0, bankroll=10000) > 0

    def test_stake_capped_at_max_bet_pct(self):
        # MAX_BET_PERCENTAGE=0.05 → stake ≤ $500 for $10k bankroll
        stake = EVCalculator.kelly_stake(0.99, 10.0, bankroll=10000)
        assert stake <= 10000 * 0.05

    def test_custom_fraction_higher_gives_bigger_stake(self):
        stake_25 = EVCalculator.kelly_stake(0.60, 2.0, bankroll=10000, fraction=0.25)
        stake_50 = EVCalculator.kelly_stake(0.60, 2.0, bankroll=10000, fraction=0.50)
        assert stake_50 >= stake_25

    def test_decimal_odds_le_1_returns_zero(self):
        assert EVCalculator.kelly_stake(0.80, 1.0, bankroll=10000) == pytest.approx(0.0)

    def test_fractional_kelly_25pct_formula(self):
        # full_kelly = (0.60*1 - 0.40)/1 = 0.20; 25% = 0.05; $500 on $10k bankroll
        stake = EVCalculator.kelly_stake(0.60, 2.0, bankroll=10000, fraction=0.25)
        assert stake == pytest.approx(500.0, abs=1.0)


# ---------------------------------------------------------------------------
# classify_bet (real settings: HIGH=0.07, MEDIUM=0.05, LOW=0.03)
# ---------------------------------------------------------------------------

class TestClassifyBet:
    def test_edge_above_high_threshold_is_strong_play(self):
        # 0.08 >= HIGH=0.07
        assert EVCalculator.classify_bet(edge=0.08, confidence=0.80) == "strong_play"

    def test_edge_between_medium_and_high_is_good_play(self):
        # 0.06 in [0.05, 0.07)
        assert EVCalculator.classify_bet(edge=0.06, confidence=0.80) == "good_play"

    def test_edge_between_low_and_medium_is_lean(self):
        # 0.04 in [0.03, 0.05)
        assert EVCalculator.classify_bet(edge=0.04, confidence=0.80) == "lean"

    def test_edge_below_low_threshold_is_pass(self):
        # 0.01 < LOW=0.03
        assert EVCalculator.classify_bet(edge=0.01, confidence=0.80) == "pass"

    def test_low_confidence_downgrades_tier(self):
        # 0.08 → strong_play; confidence=0.30 < 0.40 → downgraded to good_play
        assert EVCalculator.classify_bet(edge=0.08, confidence=0.30) == "good_play"

    def test_pass_not_downgraded_below_pass(self):
        assert EVCalculator.classify_bet(edge=0.00, confidence=0.20) == "pass"


# ---------------------------------------------------------------------------
# calculate_ev (full pipeline)
# ---------------------------------------------------------------------------

class TestCalculateEV:
    def test_returns_all_required_keys(self, calc):
        result = calc.calculate_ev(
            _make_research_data([28.0] * 30), line=24.5, odds=-110, prop_type="points"
        )
        required = {
            "player_name", "prop_type", "line", "american_odds", "decimal_odds",
            "implied_prob", "true_prob", "edge", "ev_raw", "ev_per_dollar",
            "confidence", "classification", "kelly_fraction", "recommended_stake",
            "timestamp",
        }
        assert required.issubset(set(result.keys()))

    def test_positive_edge_when_player_consistently_over(self, calc):
        result = calc.calculate_ev(
            _make_research_data([30.0] * 30), line=24.5, odds=-110, prop_type="points"
        )
        assert result["edge"] > 0

    def test_negative_edge_when_player_consistently_under(self, calc):
        result = calc.calculate_ev(
            _make_research_data([15.0] * 30), line=24.5, odds=-110, prop_type="points"
        )
        assert result["edge"] < 0

    def test_probabilities_within_bounds(self, calc):
        result = calc.calculate_ev(
            _make_research_data([25.0] * 20), line=24.5, odds=-110, prop_type="points"
        )
        assert 0.0 <= result["true_prob"] <= 1.0
        assert 0.0 <= result["implied_prob"] <= 1.0

    def test_player_name_propagated(self, calc):
        data = _make_research_data([25.0] * 20)
        data["player_name"] = "LeBron James"
        result = calc.calculate_ev(data, line=24.5, odds=-110, prop_type="points")
        assert result["player_name"] == "LeBron James"

    def test_model_components_included(self, calc):
        result = calc.calculate_ev(
            _make_research_data([25.0] * 20), line=24.5, odds=-110, prop_type="points"
        )
        comps = result["model_components"]
        assert "l5_hit_rate" in comps
        assert "l10_hit_rate" in comps
        assert "sample_size" in comps
