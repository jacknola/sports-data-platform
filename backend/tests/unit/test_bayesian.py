"""
Unit tests for BayesianAnalyzer (app/services/bayesian.py).

All tests are pure-unit: no external I/O, no database.
Monte Carlo tests use a fixed numpy seed for determinism.
"""
import pytest
import numpy as np

from app.services.bayesian import BayesianAnalyzer


@pytest.fixture
def analyzer():
    return BayesianAnalyzer()


# ---------------------------------------------------------------------------
# _prob_to_american_odds
# ---------------------------------------------------------------------------

class TestProbToAmericanOdds:
    def test_favourite_60_percent(self, analyzer):
        # 0.6 -> -100 * 0.6 / 0.4 = -150
        result = analyzer._prob_to_american_odds(0.6)
        assert result == pytest.approx(-150.0, rel=1e-3)

    def test_underdog_40_percent(self, analyzer):
        # 0.4 -> 100 * 0.6 / 0.4 = 150
        result = analyzer._prob_to_american_odds(0.4)
        assert result == pytest.approx(150.0, rel=1e-3)

    def test_even_money_50_percent(self, analyzer):
        # 0.5 -> 100 * 0.5 / 0.5 = 100
        result = analyzer._prob_to_american_odds(0.5)
        assert result == pytest.approx(100.0, rel=1e-3)

    def test_heavy_favourite_75_percent(self, analyzer):
        # 0.75 -> -100 * 0.75 / 0.25 = -300
        result = analyzer._prob_to_american_odds(0.75)
        assert result == pytest.approx(-300.0, rel=1e-3)

    def test_heavy_underdog_25_percent(self, analyzer):
        # 0.25 -> 100 * 0.75 / 0.25 = 300
        result = analyzer._prob_to_american_odds(0.25)
        assert result == pytest.approx(300.0, rel=1e-3)

    def test_return_is_negative_for_probability_above_half(self, analyzer):
        assert analyzer._prob_to_american_odds(0.7) < 0

    def test_return_is_positive_for_probability_below_half(self, analyzer):
        assert analyzer._prob_to_american_odds(0.3) > 0


# ---------------------------------------------------------------------------
# calculate_kelly_criterion
# ---------------------------------------------------------------------------

class TestKellyCriterion:
    def test_positive_edge_returns_positive_fraction(self, analyzer):
        # 5% edge -> Half Kelly (0.5). Prob 0.55, Odds 2.0 -> Full Kelly 0.1. Result 0.05.
        k = analyzer.calculate_kelly_criterion(0.55, 2.0, edge=0.05)
        assert 0.0 < k <= 0.05
        assert k == pytest.approx(0.05)

    def test_low_edge_returns_quarter_kelly(self, analyzer):
        # 3% edge -> Quarter Kelly (0.25). Prob 0.53, Odds 2.0 -> Full Kelly 0.06. Result 0.015.
        k = analyzer.calculate_kelly_criterion(0.53, 2.0, edge=0.03)
        assert k == pytest.approx(0.015)

    def test_below_threshold_returns_zero(self, analyzer):
        # 2% edge < 3% threshold
        k = analyzer.calculate_kelly_criterion(0.52, 2.0, edge=0.02)
        assert k == 0.0

    def test_breakeven_returns_zero(self, analyzer):
        # 50% at decimal 2.0 -> (0.5*2 - 1) / (2-1) = 0
        k = analyzer.calculate_kelly_criterion(0.5, 2.0, edge=0.03)
        assert k == pytest.approx(0.0, abs=1e-9)

    def test_negative_edge_clamped_to_zero(self, analyzer):
        k = analyzer.calculate_kelly_criterion(0.3, 1.5, edge=0.05)
        assert k == 0.0

    def test_capped_at_five_percent(self, analyzer):
        # Extreme edge: prob=0.99, decimal=10, edge=0.8 -> raw half-kelly >> 0.05
        k = analyzer.calculate_kelly_criterion(0.99, 10.0, edge=0.20)
        assert k == 0.05

    def test_odds_equal_to_one_returns_zero(self, analyzer):
        assert analyzer.calculate_kelly_criterion(0.9, 1.0, edge=0.05) == 0.0

    def test_odds_below_one_returns_zero(self, analyzer):
        assert analyzer.calculate_kelly_criterion(0.9, 0.5, edge=0.05) == 0.0

    def test_fraction_never_exceeds_five_percent(self, analyzer):
        for prob in [0.6, 0.7, 0.8, 0.9]:
            for odds in [2.0, 3.0, 5.0]:
                k = analyzer.calculate_kelly_criterion(prob, odds, edge=0.1)
                assert k <= 0.05


# ---------------------------------------------------------------------------
# _compute_adjustments
# ---------------------------------------------------------------------------

class TestComputeAdjustments:
    def test_injury_out_applies_large_negative(self, analyzer):
        adj = analyzer._compute_adjustments({"injury_status": "OUT"})
        assert adj["injury"] == -0.99

    def test_injury_questionable_applies_small_negative(self, analyzer):
        adj = analyzer._compute_adjustments({"injury_status": "QUESTIONABLE"})
        assert adj["injury"] == -0.05

    def test_injury_active_applies_zero(self, analyzer):
        adj = analyzer._compute_adjustments({"injury_status": "ACTIVE"})
        assert adj.get("injury", 0.0) == 0.0

    def test_missing_injury_defaults_to_zero(self, analyzer):
        adj = analyzer._compute_adjustments({})
        assert adj.get("injury", 0.0) == 0.0

    def test_home_advantage_positive(self, analyzer):
        adj = analyzer._compute_adjustments({"is_home": True})
        assert adj["home_advantage"] == 0.03

    def test_away_disadvantage_negative(self, analyzer):
        adj = analyzer._compute_adjustments({"is_home": False})
        assert adj["home_advantage"] == -0.03

    def test_weather_high_wind_reduces_prob(self, analyzer):
        adj = analyzer._compute_adjustments(
            {"weather": {"type": "outdoor", "wind_mph": 25}}
        )
        assert adj["weather"] == -0.03

    def test_weather_low_wind_no_adjustment(self, analyzer):
        adj = analyzer._compute_adjustments(
            {"weather": {"type": "outdoor", "wind_mph": 10}}
        )
        assert adj.get("weather", 0.0) == 0.0

    def test_indoor_weather_key_not_present(self, analyzer):
        # No weather feature -> no weather key in adjustments dict
        adj = analyzer._compute_adjustments({})
        assert "weather" not in adj

    def test_pace_faster_than_league_positive_adjustment(self, analyzer):
        features = {
            "team_pace": 110.0,
            "opponent_pace": 110.0,
            "league_avg_pace": 100.0,
        }
        adj = analyzer._compute_adjustments(features)
        # pace_factor=110, delta=0.1, adjustment=0.1*0.1=0.01
        assert adj["pace"] == pytest.approx(0.01, rel=1e-3)

    def test_pace_slower_than_league_negative_adjustment(self, analyzer):
        features = {
            "team_pace": 90.0,
            "opponent_pace": 90.0,
            "league_avg_pace": 100.0,
        }
        adj = analyzer._compute_adjustments(features)
        assert adj["pace"] < 0

    def test_recent_form_above_average_positive(self, analyzer):
        # all wins: avg=1.0, (1.0-0.5)*0.1 = 0.05
        adj = analyzer._compute_adjustments({"recent_form": [1.0, 1.0, 1.0]})
        assert adj["form"] == pytest.approx(0.05, rel=1e-3)

    def test_recent_form_below_average_negative(self, analyzer):
        # all losses: avg=0.0, (0.0-0.5)*0.1 = -0.05
        adj = analyzer._compute_adjustments({"recent_form": [0.0, 0.0, 0.0]})
        assert adj["form"] == pytest.approx(-0.05, rel=1e-3)

    def test_empty_recent_form_no_form_key(self, analyzer):
        adj = analyzer._compute_adjustments({"recent_form": []})
        assert "form" not in adj


# ---------------------------------------------------------------------------
# compute_posterior
# ---------------------------------------------------------------------------

class TestComputePosterior:
    @pytest.fixture(autouse=True)
    def seed_numpy(self):
        np.random.seed(42)

    def _make_data(self, devig=0.55, implied=0.52, features=None):
        return {
            "selection_id": "test_sel",
            "devig_prob": devig,
            "implied_prob": implied,
            "features": features or {},
        }

    def test_returns_all_required_keys(self, analyzer):
        result = analyzer.compute_posterior(self._make_data())
        for key in [
            "selection_id",
            "prior_prob",
            "posterior_p",
            "fair_american_odds",
            "edge",
            "confidence_interval",
            "monte_carlo",
            "adjustments",
        ]:
            assert key in result

    def test_selection_id_preserved(self, analyzer):
        data = self._make_data()
        data["selection_id"] = "unique_id_123"
        result = analyzer.compute_posterior(data)
        assert result["selection_id"] == "unique_id_123"

    def test_positive_edge_when_devig_above_implied(self, analyzer):
        result = analyzer.compute_posterior(self._make_data(devig=0.60, implied=0.50))
        assert result["edge"] > 0

    def test_confidence_interval_lower_below_upper(self, analyzer):
        result = analyzer.compute_posterior(self._make_data())
        ci = result["confidence_interval"]
        assert ci["p05"] < ci["p95"]

    def test_posterior_within_valid_probability_range(self, analyzer):
        result = analyzer.compute_posterior(self._make_data())
        assert 0.0 < result["posterior_p"] < 1.0

    def test_out_injury_does_not_produce_invalid_probability(self, analyzer):
        # OUT applies -0.99; adjusted_prob should be clamped to 0.01
        result = analyzer.compute_posterior(
            self._make_data(features={"injury_status": "OUT"})
        )
        assert result["posterior_p"] > 0.0
        assert result["posterior_p"] < 1.0

    def test_monte_carlo_n_simulations_reported(self, analyzer):
        result = analyzer.compute_posterior(self._make_data())
        assert result["monte_carlo"]["n_simulations"] == 20000

    def test_default_devig_prob_is_0_5(self, analyzer):
        data = {"selection_id": "no_probs", "features": {}}
        result = analyzer.compute_posterior(data)
        # Should not raise; defaults to 0.5
        assert result["prior_prob"] == 0.5
