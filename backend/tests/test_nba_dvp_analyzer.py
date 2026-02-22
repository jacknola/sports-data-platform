"""Tests for NBADvPAnalyzer service"""
import json
import os
import tempfile
import pytest
import pandas as pd
from app.services.nba_dvp_analyzer import NBADvPAnalyzer, POSITIONS, STAT_CATEGORIES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SLATE = {
    "date": "2026-02-22",
    "season": "2025-26",
    "games": [
        {"home": "OKC", "away": "CLE", "spread": -5.5, "over_under": 222.5, "tip_off": "19:00 ET"},
        {"home": "ATL", "away": "BKN", "spread": -7.0, "over_under": 225.0, "tip_off": "19:30 ET"},
    ],
}


@pytest.fixture
def analyzer():
    return NBADvPAnalyzer()


@pytest.fixture
def loaded_analyzer():
    a = NBADvPAnalyzer()
    a.load_slate(SAMPLE_SLATE)
    a.team_pace = a._fallback_pace_data()
    a.league_avg_pace = 100.0
    a.team_dvp = a._fallback_dvp_data()
    a.player_baselines = a._fallback_player_baselines()
    return a


# ---------------------------------------------------------------------------
# Slate loading
# ---------------------------------------------------------------------------

def test_load_slate_from_dict(analyzer):
    analyzer.load_slate(SAMPLE_SLATE)
    assert len(analyzer.slate["games"]) == 2


def test_load_slate_from_file(analyzer):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(SAMPLE_SLATE, f)
        path = f.name

    try:
        analyzer.slate_path = path
        analyzer.load_slate()
        assert len(analyzer.slate["games"]) == 2
    finally:
        os.unlink(path)


def test_load_slate_missing_file_uses_empty(analyzer):
    analyzer.slate_path = "/nonexistent/path/slate.json"
    analyzer.load_slate()
    assert analyzer.slate["games"] == []


# ---------------------------------------------------------------------------
# Implied team totals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ou,spread,is_fav,expected", [
    (220.0, -5.0, True,  112.5),   # favorite: (220 + 5) / 2
    (220.0, -5.0, False, 107.5),   # underdog: (220 - 5) / 2
    (230.0, 0.0,  True,  115.0),   # pick-em
    (210.0, -10.0, True, 110.0),
    (210.0, -10.0, False, 100.0),
])
def test_calculate_implied_team_total(ou, spread, is_fav, expected):
    result = NBADvPAnalyzer.calculate_implied_team_total(ou, spread, is_fav)
    assert abs(result - expected) < 1e-9


def test_compute_all_implied_totals(loaded_analyzer):
    totals = loaded_analyzer.compute_all_implied_totals()
    # OKC is home and favored (spread -5.5), CLE is away underdog
    assert "OKC" in totals and "CLE" in totals
    assert totals["OKC"] > totals["CLE"]  # favorite always higher
    # ATL is home and favored (spread -7.0)
    assert totals["ATL"] > totals["BKN"]


def test_compute_implied_totals_sum_approx_ou(loaded_analyzer):
    totals = loaded_analyzer.compute_all_implied_totals()
    # home + away ≈ over/under for each game
    for game in SAMPLE_SLATE["games"]:
        home, away, ou = game["home"], game["away"], game["over_under"]
        combined = totals[home] + totals[away]
        assert abs(combined - ou) < 1e-6


# ---------------------------------------------------------------------------
# Pace multiplier
# ---------------------------------------------------------------------------

def test_pace_multiplier_equal_teams(loaded_analyzer):
    # Both teams same pace as league avg → multiplier = 1.0
    loaded_analyzer.team_pace = {"TEAM_A": 100.0, "TEAM_B": 100.0}
    loaded_analyzer.league_avg_pace = 100.0
    mult = loaded_analyzer.compute_pace_multiplier("TEAM_A", "TEAM_B")
    assert abs(mult - 1.0) < 1e-9


def test_pace_multiplier_fast_game(loaded_analyzer):
    loaded_analyzer.team_pace = {"FAST": 110.0, "ALSO_FAST": 110.0}
    loaded_analyzer.league_avg_pace = 100.0
    mult = loaded_analyzer.compute_pace_multiplier("FAST", "ALSO_FAST")
    assert mult > 1.0


def test_pace_multiplier_slow_game(loaded_analyzer):
    loaded_analyzer.team_pace = {"SLOW": 90.0, "ALSO_SLOW": 90.0}
    loaded_analyzer.league_avg_pace = 100.0
    mult = loaded_analyzer.compute_pace_multiplier("SLOW", "ALSO_SLOW")
    assert mult < 1.0


def test_pace_multiplier_missing_team_uses_league_avg(loaded_analyzer):
    loaded_analyzer.league_avg_pace = 100.0
    # UNKNOWN not in pace dict → falls back to league avg for both
    mult = loaded_analyzer.compute_pace_multiplier("UNKNOWN", "ALSO_UNKNOWN")
    assert abs(mult - 1.0) < 1e-9


def test_pace_multiplier_zero_league_avg(loaded_analyzer):
    loaded_analyzer.team_pace = {"X": 100.0}
    loaded_analyzer.league_avg_pace = 0.0
    mult = loaded_analyzer.compute_pace_multiplier("X", "X")
    assert mult == 1.0


# ---------------------------------------------------------------------------
# Matchup modifier
# ---------------------------------------------------------------------------

def test_compute_matchup_modifier_returns_all_stats(loaded_analyzer):
    opp_dvp = {"PTS": 22.0, "REB": 4.0, "AST": 7.0}
    lg_avg  = {"PTS": 22.0, "REB": 4.0, "AST": 7.0}
    mods = loaded_analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
    for stat in ["PTS", "REB", "AST", "PTS+REB+AST"]:
        assert stat in mods


def test_compute_matchup_modifier_league_avg_inputs_yield_one(loaded_analyzer):
    """When DvP equals league avg, env factor = 1, pace = 1 → modifier ≈ 1."""
    opp_dvp = {"PTS": 20.0, "REB": 5.0, "AST": 4.0}
    lg_avg  = {"PTS": 20.0, "REB": 5.0, "AST": 4.0}
    mods = loaded_analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
    for stat in ["PTS", "REB", "AST"]:
        assert abs(mods[stat] - 1.0) < 1e-9


def test_compute_matchup_modifier_soft_defense_raises_modifier(loaded_analyzer):
    opp_dvp = {"PTS": 24.0, "REB": 5.0, "AST": 4.0}
    lg_avg  = {"PTS": 20.0, "REB": 5.0, "AST": 4.0}
    mods = loaded_analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
    assert mods["PTS"] > 1.0


def test_compute_matchup_modifier_zero_lg_avg_safe(loaded_analyzer):
    """Zero league-average DvP should not cause ZeroDivisionError."""
    opp_dvp = {"PTS": 0.0, "REB": 0.0, "AST": 0.0}
    lg_avg  = {"PTS": 0.0, "REB": 0.0, "AST": 0.0}
    mods = loaded_analyzer.compute_matchup_modifier(opp_dvp, lg_avg, 110.0, 110.0, 1.0)
    for stat in ["PTS", "REB", "AST"]:
        assert mods[stat] == 0.0


# ---------------------------------------------------------------------------
# project_player_line
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("avg,mod,expected", [
    (25.0, 1.0, 25.0),
    (20.0, 1.1, 22.0),
    (30.0, 0.9, 27.0),
    (15.5, 1.2, 18.6),
])
def test_project_player_line(analyzer, avg, mod, expected):
    result = analyzer.project_player_line(avg, mod)
    assert abs(result - expected) < 0.05


# ---------------------------------------------------------------------------
# flag_discrepancy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("projected,line,expected_rec", [
    (25.0, 22.0, "HIGH VALUE OVER"),    # +13.6% > 12%
    (18.0, 22.0, "HIGH VALUE UNDER"),   # -18.2% < -12%
    (23.5, 22.0, "LEAN OVER"),          # +6.8% (between 5% and 12%)
    (20.5, 22.0, "LEAN UNDER"),         # -6.8%
    (22.5, 22.0, "NO EDGE"),            # +2.3%
])
def test_flag_discrepancy_recommendations(projected, line, expected_rec):
    rec, _ = NBADvPAnalyzer.flag_discrepancy(projected, line)
    assert rec == expected_rec


def test_flag_discrepancy_zero_line_returns_no_line():
    rec, pct = NBADvPAnalyzer.flag_discrepancy(25.0, 0.0)
    assert rec == "NO LINE"
    assert pct == 0.0


def test_flag_discrepancy_advantage_pct_is_correct():
    _, pct = NBADvPAnalyzer.flag_discrepancy(25.0, 20.0)
    assert abs(pct - 25.0) < 0.2  # (25-20)/20 * 100 = 25%


def test_flag_discrepancy_custom_threshold():
    # With 20% threshold, 15% diff should be NO EDGE
    rec, _ = NBADvPAnalyzer.flag_discrepancy(23.0, 20.0, threshold=0.20)
    assert rec == "LEAN OVER"


# ---------------------------------------------------------------------------
# Matchup map
# ---------------------------------------------------------------------------

def test_build_matchup_map(loaded_analyzer):
    m = loaded_analyzer._build_matchup_map()
    assert m["OKC"] == "CLE"
    assert m["CLE"] == "OKC"
    assert m["ATL"] == "BKN"
    assert m["BKN"] == "ATL"


# ---------------------------------------------------------------------------
# Fallback data
# ---------------------------------------------------------------------------

def test_fallback_pace_data_has_all_30_teams(analyzer):
    pace = analyzer._fallback_pace_data()
    assert len(pace) == 30
    assert all(isinstance(v, float) for v in pace.values())


def test_fallback_dvp_data_structure(analyzer):
    dvp = analyzer._fallback_dvp_data()
    assert len(dvp) == 30
    for team_data in dvp.values():
        assert set(team_data.keys()) == set(POSITIONS)
        for pos_data in team_data.values():
            for stat in ["PTS", "REB", "AST"]:
                assert stat in pos_data
                assert pos_data[stat] > 0


def test_fallback_player_baselines_slate_filter(loaded_analyzer):
    # Slate teams: OKC, CLE, ATL, BKN
    players = loaded_analyzer.player_baselines
    teams = {p["team"] for p in players}
    assert teams.issubset({"OKC", "CLE", "ATL", "BKN"})


def test_fallback_player_baselines_combo_stat(loaded_analyzer):
    for p in loaded_analyzer.player_baselines:
        expected = round(p["avg_PTS"] + p["avg_REB"] + p["avg_AST"], 1)
        assert abs(p["avg_PTS+REB+AST"] - expected) < 0.05


# ---------------------------------------------------------------------------
# League average DvP
# ---------------------------------------------------------------------------

def test_compute_league_avg_dvp_returns_three_stats(loaded_analyzer):
    loaded_analyzer.team_dvp = loaded_analyzer._fallback_dvp_data()
    avg = loaded_analyzer._compute_league_avg_dvp()
    assert set(avg.keys()) == {"PTS", "REB", "AST"}
    for v in avg.values():
        assert v > 0


def test_compute_league_avg_dvp_empty_returns_zeros(analyzer):
    analyzer.team_dvp = {}
    avg = analyzer._compute_league_avg_dvp()
    assert avg == {"PTS": 0.0, "REB": 0.0, "AST": 0.0}


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def test_run_analysis_returns_dataframe(loaded_analyzer):
    df = loaded_analyzer.run_analysis(slate_data=SAMPLE_SLATE)
    assert isinstance(df, pd.DataFrame)


def test_run_analysis_has_expected_columns(loaded_analyzer):
    df = loaded_analyzer.run_analysis(slate_data=SAMPLE_SLATE)
    required = {
        "Player", "Position", "Team", "Opponent",
        "Stat_Category", "Season_Avg", "Projected_Line",
        "Sportsbook_Line", "DvP_Advantage_%", "Recommendation",
    }
    assert required.issubset(set(df.columns))


def test_run_analysis_stat_categories(loaded_analyzer):
    df = loaded_analyzer.run_analysis(slate_data=SAMPLE_SLATE)
    assert set(df["Stat_Category"].unique()).issubset(set(STAT_CATEGORIES))


def test_run_analysis_sorted_by_dvp_advantage(loaded_analyzer):
    df = loaded_analyzer.run_analysis(slate_data=SAMPLE_SLATE)
    if len(df) > 1:
        abs_pcts = df["DvP_Advantage_%"].abs().tolist()
        assert abs_pcts == sorted(abs_pcts, reverse=True)


def test_run_analysis_recommendation_values(loaded_analyzer):
    df = loaded_analyzer.run_analysis(slate_data=SAMPLE_SLATE)
    valid = {"HIGH VALUE OVER", "HIGH VALUE UNDER", "LEAN OVER", "LEAN UNDER", "NO EDGE", "NO LINE"}
    assert set(df["Recommendation"].unique()).issubset(valid)


def test_get_high_value_plays_filters_correctly(loaded_analyzer):
    df = loaded_analyzer.run_analysis(slate_data=SAMPLE_SLATE)
    hv = loaded_analyzer.get_high_value_plays(df)
    assert all("HIGH VALUE" in r for r in hv["Recommendation"])


def test_run_analysis_empty_slate_returns_empty_df(analyzer):
    empty_slate = {"date": "2026-02-22", "games": []}
    analyzer.load_slate(empty_slate)
    analyzer.team_pace = analyzer._fallback_pace_data()
    analyzer.league_avg_pace = 100.0
    analyzer.team_dvp = analyzer._fallback_dvp_data()
    analyzer.player_baselines = []
    df = analyzer.run_analysis(slate_data=empty_slate)
    assert df.empty


# ---------------------------------------------------------------------------
# Team name / abbrev helpers
# ---------------------------------------------------------------------------

def test_team_name_to_abbrev_known():
    result = NBADvPAnalyzer._team_name_to_abbrev("Boston Celtics")
    assert result == "BOS"


def test_team_name_to_abbrev_unknown():
    result = NBADvPAnalyzer._team_name_to_abbrev("Nonexistent Team")
    assert result is None


def test_nba_abbrev_to_ours_gsw():
    result = NBADvPAnalyzer._nba_abbrev_to_ours("GSW")
    assert result == "GS"


def test_nba_abbrev_to_ours_unknown():
    result = NBADvPAnalyzer._nba_abbrev_to_ours("ZZZZZ")
    assert result is None


# ---------------------------------------------------------------------------
# Estimate team season totals
# ---------------------------------------------------------------------------

def test_estimate_team_season_totals(loaded_analyzer):
    loaded_analyzer.team_pace = {"LAL": 100.0, "BOS": 98.5}
    loaded_analyzer._estimate_team_season_totals()
    # 100 * 1.12 = 112.0
    assert abs(loaded_analyzer.team_season_avg_totals["LAL"] - 112.0) < 0.5
    assert loaded_analyzer.team_season_avg_totals["BOS"] < loaded_analyzer.team_season_avg_totals["LAL"]
