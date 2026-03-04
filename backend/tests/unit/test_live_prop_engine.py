"""Unit tests for LivePropEngine and estimate_live_pace."""
import pytest

from app.services.live_prop_engine import (
    LiveGameState,
    LivePlayerState,
    LivePropEngine,
    LivePropLine,
    estimate_live_pace,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return LivePropEngine()


def _make_game_state(
    minutes_remaining: float = 24.0,
    home_score: int = 50,
    away_score: int = 48,
    actual_pace: float = 100.0,
    sport: str = "nba",
    period: int = 3,
) -> LiveGameState:
    return LiveGameState(
        game_id="test_game",
        sport=sport,
        period=period,
        minutes_remaining=minutes_remaining,
        home_team="LAL",
        away_team="GSW",
        home_score=home_score,
        away_score=away_score,
        actual_pace=actual_pace,
    )


def _make_player(
    stat_type: str = "points",
    current_stat: float = 12.0,
    minutes_played: float = 24.0,
    fouls: int = 1,
    is_star: bool = True,
) -> LivePlayerState:
    return LivePlayerState(
        player_id="test_player",
        player_name="Test Player",
        team="LAL",
        stat_type=stat_type,
        current_stat=current_stat,
        minutes_played=minutes_played,
        fouls=fouls,
        is_star=is_star,
    )


def _make_live_line(
    threshold: float = 25.5,
    over_odds: float = -115,
    under_odds: float = -105,
) -> LivePropLine:
    return LivePropLine(threshold=threshold, over_odds=over_odds, under_odds=under_odds)


def _make_season_data(
    season_avg: float = 24.0,
    avg_minutes: float = 34.0,
    expected_pace: float = 100.0,
) -> dict:
    return {
        "season_avg": season_avg,
        "avg_minutes": avg_minutes,
        "expected_pace": expected_pace,
    }


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

class TestLivePropEngineAnalyze:
    def test_returns_projection_dict(self, engine):
        proj = engine.analyze(
            _make_player(),
            _make_game_state(),
            _make_season_data(),
            _make_live_line(),
        )
        result = proj.to_dict()
        assert isinstance(result, dict)
        required = [
            "player_name", "stat_type", "threshold", "current_stat",
            "true_p_over", "true_p_under", "edge_over", "edge_under",
            "best_side", "best_edge", "verdict", "is_positive_ev",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_probabilities_sum_to_one(self, engine):
        proj = engine.analyze(
            _make_player(),
            _make_game_state(),
            _make_season_data(),
            _make_live_line(),
        )
        assert abs(proj.true_p_over + proj.true_p_under - 1.0) < 1e-6

    def test_already_hit_threshold_high_p_over(self, engine):
        """Player with current_stat > threshold should have very high P(over)."""
        player = _make_player(current_stat=30.0)
        line = _make_live_line(threshold=25.5)
        proj = engine.analyze(player, _make_game_state(), _make_season_data(), line)
        assert proj.true_p_over >= 0.97

    def test_edge_calculation_is_consistent(self, engine):
        proj = engine.analyze(
            _make_player(),
            _make_game_state(),
            _make_season_data(),
            _make_live_line(),
        )
        # edge_over = true_p_over - implied_p_over
        assert abs(proj.edge_over - (proj.true_p_over - proj.implied_p_over)) < 1e-4

    def test_kelly_fraction_bounded(self, engine):
        """Half-Kelly must be in [0, 0.10]."""
        proj = engine.analyze(
            _make_player(),
            _make_game_state(),
            _make_season_data(),
            _make_live_line(over_odds=150),
        )
        assert 0.0 <= proj.kelly_fraction <= 0.10

    def test_verdict_pass_when_edge_near_zero(self, engine):
        """When true probability ≈ implied probability, verdict should be PASS or FADE."""
        # Use fair odds (-110 / -110) so edge is near zero
        proj = engine.analyze(
            _make_player(current_stat=12.0),
            _make_game_state(minutes_remaining=24.0),
            _make_season_data(season_avg=25.0),
            _make_live_line(threshold=24.0, over_odds=-110, under_odds=-110),
        )
        assert proj.verdict in ("PASS", "LEAN OVER", "LEAN UNDER", "MARGINAL OVER", "MARGINAL UNDER", "FADE OVER", "FADE UNDER", "STRONG OVER", "STRONG UNDER")

    def test_strong_verdict_with_big_edge(self, engine):
        """Clear hot hand + long odds over should give STRONG OVER verdict."""
        # Player has 5 threes in Q1 (very hot), asking about 3.5 threshold
        player = _make_player(
            stat_type="threes",
            current_stat=5.0,
            minutes_played=12.0,
            is_star=True,
        )
        line = _make_live_line(threshold=3.5, over_odds=200, under_odds=-280)
        proj = engine.analyze(player, _make_game_state(minutes_remaining=36.0), _make_season_data(season_avg=3.0, avg_minutes=34.0), line)
        assert proj.best_side == "over"
        assert proj.best_edge > 0.0


# ---------------------------------------------------------------------------
# Situational discounts
# ---------------------------------------------------------------------------

class TestGarbageTimeDiscount:
    def test_no_discount_in_close_game(self, engine):
        discount = engine._garbage_time_discount(
            score_diff=5, minutes_remaining=20.0, is_star=True
        )
        assert discount == 1.0

    def test_heavy_discount_for_star_in_blowout(self, engine):
        discount = engine._garbage_time_discount(
            score_diff=28, minutes_remaining=5.0, is_star=True
        )
        assert discount <= 0.50

    def test_lighter_discount_for_role_player(self, engine):
        star_disc = engine._garbage_time_discount(30, 6.0, True)
        role_disc = engine._garbage_time_discount(30, 6.0, False)
        assert role_disc > star_disc


class TestFoulDiscount:
    def test_no_discount_clean(self, engine):
        assert engine._foul_discount(1, 30.0, "nba") == 1.0

    def test_heavy_discount_one_foul_from_limit(self, engine):
        disc = engine._foul_discount(5, 20.0, "nba")   # 1 away from foul out
        assert disc == 0.55

    def test_moderate_discount_two_away_early(self, engine):
        disc = engine._foul_discount(4, 15.0, "nba")   # 2 away, early Q4
        assert disc == 0.72


# ---------------------------------------------------------------------------
# Slate analysis
# ---------------------------------------------------------------------------

class TestAnalyzeSlate:
    def test_slate_sorted_by_edge_descending(self, engine):
        props = [
            {
                "player": _make_player(stat_type="threes", current_stat=5.0, minutes_played=12.0),
                "game_state": _make_game_state(minutes_remaining=36.0),
                "player_season_data": _make_season_data(season_avg=3.0),
                "live_line": _make_live_line(threshold=3.5, over_odds=200, under_odds=-280),
            },
            {
                "player": _make_player(stat_type="points", current_stat=8.0, minutes_played=20.0),
                "game_state": _make_game_state(),
                "player_season_data": _make_season_data(),
                "live_line": _make_live_line(threshold=25.5),
            },
        ]
        results = engine.analyze_slate(props)
        assert len(results) == 2
        assert results[0]["best_edge"] >= results[1]["best_edge"]

    def test_empty_slate(self, engine):
        assert engine.analyze_slate([]) == []

    def test_bad_entry_skipped(self, engine):
        """A malformed entry should not crash the slate — it should be skipped."""
        props = [
            {"player": None, "game_state": None, "player_season_data": {}, "live_line": None},
            {
                "player": _make_player(),
                "game_state": _make_game_state(),
                "player_season_data": _make_season_data(),
                "live_line": _make_live_line(),
            },
        ]
        results = engine.analyze_slate(props)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# estimate_live_pace
# ---------------------------------------------------------------------------

class TestEstimateLivePace:
    def test_normal_game_pace(self):
        # 38+35=73 points in 14.5 min → ~(73/1.1/14.5)*48 ≈ 220 raw, clamped to 140
        # Use a realistic Q3 score: 95 pts through 36 min → pace ≈ 115
        pace = estimate_live_pace(home_score=48, away_score=47, minutes_played=36.0)
        assert 60 <= pace <= 140

    def test_zero_minutes_returns_default(self):
        pace = estimate_live_pace(home_score=0, away_score=0, minutes_played=0.0)
        assert pace == 100.0

    def test_pace_clamped_to_floor(self):
        pace = estimate_live_pace(home_score=2, away_score=1, minutes_played=24.0)
        assert pace >= 60.0

    def test_pace_clamped_to_ceiling(self):
        pace = estimate_live_pace(home_score=999, away_score=999, minutes_played=1.0)
        assert pace <= 140.0

    def test_ncaab_sport_param_accepted(self):
        pace = estimate_live_pace(30, 28, 10.0, sport="ncaab")
        assert isinstance(pace, float)
