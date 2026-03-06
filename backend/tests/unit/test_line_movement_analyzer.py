"""
Unit tests for LineMovementAnalyzer (app/services/line_movement_analyzer.py).

Tests cover:
    - Devigging correctness
    - Market consensus probability calculation
    - Line movement feature extraction
    - CLV recording and summary
"""
import pytest

from app.services.line_movement_analyzer import (
    LineMovementAnalyzer,
)


# ---------------------------------------------------------------------------
# Devigging correctness
# ---------------------------------------------------------------------------

class TestDevig:
    """Verify devig_odds and _american_to_implied produce correct results."""

    def test_implied_favorite(self):
        # -110 → 110/210 ≈ 0.5238
        imp = LineMovementAnalyzer._american_to_implied(-110)
        assert abs(imp - 0.5238) < 0.001

    def test_implied_underdog(self):
        # +150 → 100/250 = 0.40
        imp = LineMovementAnalyzer._american_to_implied(150)
        assert abs(imp - 0.40) < 0.001

    def test_devig_symmetric_market(self):
        p1, p2 = LineMovementAnalyzer.devig_odds(-110, -110)
        assert abs(p1 - 0.50) < 0.001
        assert abs(p2 - 0.50) < 0.001
        assert abs(p1 + p2 - 1.0) < 0.0001

    def test_devig_asymmetric_market(self):
        p1, p2 = LineMovementAnalyzer.devig_odds(-200, 170)
        assert p1 > p2
        assert abs(p1 + p2 - 1.0) < 0.0001


# ---------------------------------------------------------------------------
# analyze_game — EV edge calculation
# ---------------------------------------------------------------------------

class TestAnalyzeGame:
    """Verify analyze_game computes correct EV edges."""

    def _run(self, pinnacle_odds: float, retail_odds: float, **kwargs) -> dict:
        return LineMovementAnalyzer.analyze_game(
            game_id="test_game",
            market="spread",
            home_team="Home",
            away_team="Away",
            open_line=kwargs.get("open_line", -3.5),
            current_line=kwargs.get("current_line", -3.5),
            pinnacle_home_odds=pinnacle_odds,
            retail_home_odds=retail_odds,
        )

    def test_symmetric_market_no_edge(self):
        """For -110/-110 both sides, edge should be ≤ 0 after devigging."""
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        assert result["ev_edge"] < 0.0

    def test_devigged_prob_near_expected(self):
        """Devigged probability for -110 should be ~0.5110."""
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        retail_implied = LineMovementAnalyzer._american_to_implied(-110)
        devigged_home = result["ev_edge"] + retail_implied
        assert abs(devigged_home - 0.5110) < 0.001

    def test_positive_ev_when_retail_overpriced(self):
        """Retail at +100 vs Pinnacle -110 should show positive edge."""
        result = self._run(pinnacle_odds=-110, retail_odds=100)
        assert result["ev_edge"] > 0.0
        assert result["is_positive_ev"] is False  # Edge < 3% threshold

    def test_negative_ev_when_retail_underpriced(self):
        """Retail at -120 vs Pinnacle -110 should show negative edge."""
        result = self._run(pinnacle_odds=-110, retail_odds=-120)
        assert result["ev_edge"] < 0.0

    def test_heavy_favorite_devigged_below_raw(self):
        result = self._run(pinnacle_odds=-200, retail_odds=-200)
        retail_implied = LineMovementAnalyzer._american_to_implied(-200)
        devigged_home = result["ev_edge"] + retail_implied
        expected = LineMovementAnalyzer._american_to_implied(-200) / 1.025
        assert abs(devigged_home - expected) < 0.001

    def test_line_movement_signal_detected(self):
        """A 1.5-point line move should produce a LINE_MOVE signal."""
        result = self._run(
            pinnacle_odds=-110, retail_odds=-110,
            open_line=-3.0, current_line=-4.5,
        )
        assert "LINE_MOVE" in result["sharp_signals"]
        assert result["line_move"] == -1.5

    def test_small_line_move_no_signal(self):
        """A 0.5-point move should NOT produce a LINE_MOVE signal."""
        result = self._run(
            pinnacle_odds=-110, retail_odds=-110,
            open_line=-3.0, current_line=-3.5,
        )
        assert "LINE_MOVE" not in result["sharp_signals"]

    def test_pinnacle_implied_is_raw(self):
        """pinnacle_implied should be raw (viggy), not devigged."""
        result = self._run(pinnacle_odds=-110, retail_odds=-110)
        expected_raw = LineMovementAnalyzer._american_to_implied(-110)
        assert abs(result["pinnacle_implied"] - expected_raw) < 0.001


# ---------------------------------------------------------------------------
# Market consensus
# ---------------------------------------------------------------------------

class TestMarketConsensus:
    """Verify weighted multi-book consensus probability."""

    def test_single_book_returns_nonzero(self):
        prob = LineMovementAnalyzer.compute_market_consensus({"pinnacle": -110})
        assert prob > 0

    def test_consensus_higher_weight_to_pinnacle(self):
        """Pinnacle should pull the consensus toward its implied probability."""
        # Pinnacle says -200 (implied ~0.6667), retail says -110 (implied ~0.5238)
        prob = LineMovementAnalyzer.compute_market_consensus({
            "pinnacle": -200,
            "fanduel": -110,
        })
        pinnacle_devig = LineMovementAnalyzer._american_to_implied(-200) / 1.025
        fanduel_devig = LineMovementAnalyzer._american_to_implied(-110) / 1.025
        # Consensus should be between the two but closer to Pinnacle
        assert pinnacle_devig > prob > fanduel_devig

    def test_empty_dict_returns_zero(self):
        assert LineMovementAnalyzer.compute_market_consensus({}) == 0.0


# ---------------------------------------------------------------------------
# Line features extraction
# ---------------------------------------------------------------------------

class TestExtractLineFeatures:

    def test_stable_line(self):
        f = LineMovementAnalyzer.extract_line_features(
            game_id="g1", market="spread",
            open_line=-3.0, current_line=-3.0,
        )
        assert f.move_direction == "STABLE"
        assert f.line_move == 0.0

    def test_toward_away(self):
        f = LineMovementAnalyzer.extract_line_features(
            game_id="g1", market="spread",
            open_line=-3.0, current_line=-5.0,
        )
        assert f.move_direction == "TOWARD_AWAY"
        assert f.line_move == -2.0

    def test_toward_home(self):
        f = LineMovementAnalyzer.extract_line_features(
            game_id="g1", market="spread",
            open_line=-3.0, current_line=-1.0,
        )
        assert f.move_direction == "TOWARD_HOME"
        assert f.line_move == 2.0


# ---------------------------------------------------------------------------
# CLV tracking
# ---------------------------------------------------------------------------

class TestCLVTracking:

    def test_positive_clv(self):
        analyzer = LineMovementAnalyzer()
        record = analyzer.record_clv(
            game_id="g1", market="spread", side="home",
            bet_odds=-105, closing_odds=-110,
            game_start=1000000.0, bet_timestamp=999000.0,
        )
        # Closing odds are worse (more vig), so we got a better price → positive CLV
        assert record.clv_pct > 0

    def test_negative_clv(self):
        analyzer = LineMovementAnalyzer()
        record = analyzer.record_clv(
            game_id="g1", market="spread", side="home",
            bet_odds=-115, closing_odds=-105,
            game_start=1000000.0, bet_timestamp=999000.0,
        )
        assert record.clv_pct < 0

    def test_clv_summary(self):
        analyzer = LineMovementAnalyzer()
        analyzer.record_clv("g1", "spread", "home", -105, -110, 1e6)
        analyzer.record_clv("g2", "spread", "away", -115, -105, 1e6)
        summary = analyzer.clv_summary()
        assert summary["count"] == 2
        assert "avg_clv" in summary
        assert "pct_positive" in summary

    def test_empty_clv_summary(self):
        analyzer = LineMovementAnalyzer()
        summary = analyzer.clv_summary()
        assert summary["count"] == 0
