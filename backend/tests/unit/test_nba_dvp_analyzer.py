"""
Unit tests for NBADvPAnalyzer (app/services/nba_dvp_analyzer.py).

All external API calls (nba_api) are patched; file I/O uses pytest's tmp_path.
"""
import json
import pytest

from app.services.nba_dvp_analyzer import NBADvPAnalyzer


@pytest.fixture
def analyzer():
    return NBADvPAnalyzer()


# ---------------------------------------------------------------------------
# calculate_implied_team_total  (static method — no instance needed)
# ---------------------------------------------------------------------------

class TestCalculateImpliedTeamTotal:
    def test_favourite_formula(self):
        # (O/U + |spread|) / 2
        result = NBADvPAnalyzer.calculate_implied_team_total(220.0, -5.5, True)
        assert result == pytest.approx(112.75)

    def test_underdog_formula(self):
        # (O/U - |spread|) / 2
        result = NBADvPAnalyzer.calculate_implied_team_total(220.0, -5.5, False)
        assert result == pytest.approx(107.25)

    def test_pick_em_both_teams_equal(self):
        fav = NBADvPAnalyzer.calculate_implied_team_total(220.0, 0.0, True)
        dog = NBADvPAnalyzer.calculate_implied_team_total(220.0, 0.0, False)
        assert fav == pytest.approx(110.0)
        assert dog == pytest.approx(110.0)

    def test_totals_sum_to_over_under(self):
        ou = 215.0
        spread = -7.0
        fav = NBADvPAnalyzer.calculate_implied_team_total(ou, spread, True)
        dog = NBADvPAnalyzer.calculate_implied_team_total(ou, spread, False)
        assert fav + dog == pytest.approx(ou)

    def test_positive_spread_treated_as_underdog(self):
        # Home team posted as +3.5 (underdog)
        dog = NBADvPAnalyzer.calculate_implied_team_total(215.0, 3.5, False)
        fav = NBADvPAnalyzer.calculate_implied_team_total(215.0, 3.5, True)
        assert fav > dog

    def test_large_spread(self):
        # -20 pt favourite — Vegas blowout
        fav = NBADvPAnalyzer.calculate_implied_team_total(200.0, -20.0, True)
        dog = NBADvPAnalyzer.calculate_implied_team_total(200.0, -20.0, False)
        assert fav == pytest.approx(110.0)
        assert dog == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# load_slate
# ---------------------------------------------------------------------------

class TestLoadSlate:
    def test_load_from_dict(self, analyzer, sample_slate):
        analyzer.load_slate(sample_slate)
        assert len(analyzer.slate["games"]) == 2

    def test_load_from_dict_overrides_file(self, analyzer, sample_slate):
        # Even if slate_path is bogus, dict takes priority
        analyzer.slate_path = "/nonexistent/path.json"
        analyzer.load_slate(sample_slate)
        assert analyzer.slate["date"] == "2026-02-22"

    def test_load_from_file(self, analyzer, sample_slate, tmp_path):
        slate_file = tmp_path / "slate.json"
        slate_file.write_text(json.dumps(sample_slate))
        analyzer.slate_path = str(slate_file)
        analyzer.load_slate()
        assert len(analyzer.slate["games"]) == 2

    def test_missing_file_produces_empty_games_list(self, analyzer):
        analyzer.slate_path = "/definitely/does/not/exist.json"
        analyzer.load_slate()
        assert analyzer.slate.get("games") == []

    def test_missing_file_slate_has_date(self, analyzer):
        analyzer.slate_path = "/definitely/does/not/exist.json"
        analyzer.load_slate()
        assert "date" in analyzer.slate


# ---------------------------------------------------------------------------
# compute_all_implied_totals
# ---------------------------------------------------------------------------

class TestComputeAllImpliedTotals:
    def test_all_four_teams_present(self, analyzer, sample_slate):
        analyzer.load_slate(sample_slate)
        totals = analyzer.compute_all_implied_totals()
        assert set(totals.keys()) == {"LAL", "BOS", "GSW", "MIA"}

    def test_game_totals_sum_to_over_under(self, analyzer, sample_slate):
        analyzer.load_slate(sample_slate)
        totals = analyzer.compute_all_implied_totals()
        assert totals["LAL"] + totals["BOS"] == pytest.approx(220.0)
        assert totals["GSW"] + totals["MIA"] == pytest.approx(215.0)

    def test_home_favourite_gets_higher_total(self, analyzer, sample_slate):
        # LAL at -5.5 (home fav)
        analyzer.load_slate(sample_slate)
        totals = analyzer.compute_all_implied_totals()
        assert totals["LAL"] > totals["BOS"]

    def test_away_favourite_gets_higher_total(self, analyzer, sample_slate):
        # GSW at +3.0 means MIA (away) is favourite
        analyzer.load_slate(sample_slate)
        totals = analyzer.compute_all_implied_totals()
        assert totals["MIA"] > totals["GSW"]

    def test_empty_slate_returns_empty_dict(self, analyzer):
        analyzer.load_slate({"date": "2026-02-22", "games": []})
        totals = analyzer.compute_all_implied_totals()
        assert totals == {}

    def test_single_game(self, analyzer):
        analyzer.load_slate({
            "date": "2026-02-22",
            "games": [{"home": "CHI", "away": "DET", "spread": -2.0, "over_under": 210.0}],
        })
        totals = analyzer.compute_all_implied_totals()
        assert "CHI" in totals
        assert "DET" in totals
        assert totals["CHI"] + totals["DET"] == pytest.approx(210.0)


# ---------------------------------------------------------------------------
# compute_matchup_modifier
# ---------------------------------------------------------------------------

class TestComputeMatchupModifier:
    def test_neutral_matchup_produces_modifier_of_one(self, analyzer):
        opp_dvp = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
        for stat in ["PTS", "REB", "AST", "PTS+REB+AST"]:
            assert mods[stat] == pytest.approx(1.0), f"Expected 1.0 for {stat}"

    def test_soft_pts_defence_boosts_pts_modifier(self, analyzer):
        # opp allows 30 PTS vs 25 league avg -> dvp_factor = 1.2
        opp_dvp = {"PTS": 30.0, "REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
        assert mods["PTS"] == pytest.approx(1.2)

    def test_stingy_defence_reduces_modifier(self, analyzer):
        # opp allows 20 PTS vs 25 league avg -> dvp_factor = 0.8
        opp_dvp = {"PTS": 20.0, "REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
        assert mods["PTS"] == pytest.approx(0.8)

    def test_pace_multiplier_scales_modifier(self, analyzer):
        opp_dvp = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.1)
        assert mods["PTS"] == pytest.approx(1.1)

    def test_high_implied_total_boosts_modifier(self, analyzer):
        opp_dvp = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        # implied=121, season_avg=110 -> env_factor=1.1
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 121.0, 110.0, 1.0)
        assert mods["PTS"] == pytest.approx(1.1)

    def test_zero_league_avg_uses_one_to_avoid_division(self, analyzer):
        opp_dvp = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 0.0, "REB": 0.0, "AST": 0.0}
        # Should not raise; opp/1 = opp value itself
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
        assert mods["PTS"] == pytest.approx(25.0)

    def test_zero_season_avg_total_env_factor_is_one(self, analyzer):
        opp_dvp = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        # season_avg_total=0 -> env_factor = 1.0
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 0.0, 1.0)
        assert mods["PTS"] == pytest.approx(1.0)

    def test_combo_stat_is_mean_of_components(self, analyzer):
        opp_dvp = {"PTS": 30.0, "REB": 6.0, "AST": 7.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
        expected = (mods["PTS"] + mods["REB"] + mods["AST"]) / 3.0
        assert mods["PTS+REB+AST"] == pytest.approx(expected)

    def test_missing_stat_in_opp_dvp_defaults_to_zero(self, analyzer):
        # Missing PTS key -> opp_allowed=0, modifier = 0
        opp_dvp = {"REB": 5.0, "AST": 5.0}
        lg_avg  = {"PTS": 25.0, "REB": 5.0, "AST": 5.0}
        mods = analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
        assert mods["PTS"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_pace_multiplier
# ---------------------------------------------------------------------------

class TestComputePaceMultiplier:
    def test_equal_pace_teams_returns_one(self, analyzer):
        analyzer.team_pace = {"LAL": 100.0, "BOS": 100.0}
        analyzer.league_avg_pace = 100.0
        assert analyzer.compute_pace_multiplier("LAL", "BOS") == pytest.approx(1.0)

    def test_faster_teams_returns_above_one(self, analyzer):
        analyzer.team_pace = {"LAL": 110.0, "BOS": 110.0}
        analyzer.league_avg_pace = 100.0
        assert analyzer.compute_pace_multiplier("LAL", "BOS") == pytest.approx(1.1)

    def test_slower_teams_returns_below_one(self, analyzer):
        analyzer.team_pace = {"LAL": 90.0, "BOS": 90.0}
        analyzer.league_avg_pace = 100.0
        assert analyzer.compute_pace_multiplier("LAL", "BOS") == pytest.approx(0.9)

    def test_missing_team_falls_back_to_league_avg(self, analyzer):
        analyzer.team_pace = {}
        analyzer.league_avg_pace = 100.0
        # Both teams unknown -> game_pace = (100+100)/2 = 100 -> mult = 1.0
        assert analyzer.compute_pace_multiplier("LAL", "BOS") == pytest.approx(1.0)

    def test_zero_league_avg_returns_one(self, analyzer):
        analyzer.team_pace = {"LAL": 100.0, "BOS": 100.0}
        analyzer.league_avg_pace = 0.0
        assert analyzer.compute_pace_multiplier("LAL", "BOS") == pytest.approx(1.0)

    def test_asymmetric_teams_averages_paces(self, analyzer):
        analyzer.team_pace = {"LAL": 120.0, "BOS": 100.0}
        analyzer.league_avg_pace = 100.0
        # game_pace = (120+100)/2 = 110 -> mult = 1.1
        assert analyzer.compute_pace_multiplier("LAL", "BOS") == pytest.approx(1.1)


# ---------------------------------------------------------------------------
# flag_discrepancy  (static method)
# ---------------------------------------------------------------------------

class TestFlagDiscrepancy:
    def test_high_value_over_above_12_percent(self):
        rec, pct = NBADvPAnalyzer.flag_discrepancy(25.0, 20.0)  # +25%
        assert rec == "HIGH VALUE OVER"
        assert pct == pytest.approx(25.0)

    def test_high_value_under_below_neg12_percent(self):
        rec, pct = NBADvPAnalyzer.flag_discrepancy(17.0, 20.0)  # -15%
        assert rec == "HIGH VALUE UNDER"
        assert pct < -12.0

    def test_lean_over_between_5_and_12_percent(self):
        rec, pct = NBADvPAnalyzer.flag_discrepancy(21.5, 20.0)  # +7.5%
        assert rec == "LEAN OVER"
        assert 5.0 < pct < 12.0

    def test_lean_under_between_neg5_and_neg12_percent(self):
        rec, pct = NBADvPAnalyzer.flag_discrepancy(18.5, 20.0)  # -7.5%
        assert rec == "LEAN UNDER"
        assert -12.0 < pct < -5.0

    def test_no_edge_within_5_percent(self):
        rec, _ = NBADvPAnalyzer.flag_discrepancy(20.5, 20.0)  # +2.5%
        assert rec == "NO EDGE"

    def test_zero_sportsbook_line_returns_no_line(self):
        rec, pct = NBADvPAnalyzer.flag_discrepancy(20.0, 0.0)
        assert rec == "NO LINE"
        assert pct == 0.0

    def test_exactly_at_12_percent_threshold_is_lean_not_high_value(self):
        # flag_discrepancy uses strict > so exactly 12% is NOT HIGH VALUE
        # 20 * 1.12 = 22.4  =>  diff_pct = 0.12  =>  not > 0.12
        rec, _ = NBADvPAnalyzer.flag_discrepancy(22.4, 20.0)
        assert rec == "LEAN OVER"

    def test_just_above_12_percent_threshold_is_high_value(self):
        # 22.41 / 20 - 1 = 0.1205 > 0.12
        rec, _ = NBADvPAnalyzer.flag_discrepancy(22.41, 20.0)
        assert rec == "HIGH VALUE OVER"

    def test_custom_threshold_respected(self):
        # 7% above -> LEAN OVER with default threshold, but NO EDGE with 20% threshold
        rec, _ = NBADvPAnalyzer.flag_discrepancy(21.4, 20.0, threshold=0.20)
        assert rec == "LEAN OVER"

    def test_advantage_pct_rounded_to_one_decimal(self):
        _, pct = NBADvPAnalyzer.flag_discrepancy(25.0, 20.0)
        # 25.0 should be a clean float with one decimal place
        assert pct == round(pct, 1)


# ---------------------------------------------------------------------------
# project_player_line
# ---------------------------------------------------------------------------

class TestProjectPlayerLine:
    def test_positive_modifier_increases_line(self, analyzer):
        result = analyzer.project_player_line(20.0, 1.15)
        assert result == pytest.approx(23.0, abs=0.1)

    def test_neutral_modifier_returns_baseline(self, analyzer):
        result = analyzer.project_player_line(25.0, 1.0)
        assert result == pytest.approx(25.0)

    def test_negative_modifier_decreases_line(self, analyzer):
        result = analyzer.project_player_line(20.0, 0.85)
        assert result == pytest.approx(17.0, abs=0.1)

    def test_result_is_rounded_to_one_decimal(self, analyzer):
        result = analyzer.project_player_line(20.0, 1.137)
        # Should be rounded to 1 decimal
        assert result == round(result, 1)
