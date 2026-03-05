"""
Unit tests for app/services/sharp_money_tracker.py

Covers:
- _score_label helper
- SharpSignal dataclass / to_dict
- SharpMoneyTracker._detect_rlm
- SharpMoneyTracker._get_h2h_prices
- SharpMoneyTracker._get_spread_prices
- SharpMoneyTracker._infer_sharp_side
- SharpMoneyTracker._calc_book_divergence
- SharpMoneyTracker._analyze_game (with mock game data)
- SharpMoneyTracker._compute_line_movement
"""
import pytest

from app.services.sharp_money_tracker import (
    SharpMoneyTracker,
    SharpSignal,
    _score_label,
)
)


# ---------------------------------------------------------------------------
# _score_label
# ---------------------------------------------------------------------------

class TestScoreLabel:
    def test_zero_is_no_signal(self):
        assert _score_label(0) == "no_signal"

    def test_one_is_weak_signal(self):
        assert _score_label(1) == "weak_signal"

    def test_two_is_moderate_signal(self):
        assert _score_label(2) == "moderate_signal"

    def test_three_is_strong_signal(self):
        assert _score_label(3) == "strong_signal"

    def test_four_and_above_is_very_strong(self):
        assert _score_label(4) == "very_strong_signal"
        assert _score_label(10) == "very_strong_signal"


# ---------------------------------------------------------------------------
# SharpSignal.to_dict
# ---------------------------------------------------------------------------

class TestSharpSignal:
    def _make_signal(self, score=2):
        return SharpSignal(
            game_id="game_001",
            home_team="Duke",
            away_team="UNC",
            market="h2h",
            sharp_side="UNC",
            signal_types=["book_divergence"],
            score=score,
            details={"divergence": 0.05},
        )

    def test_to_dict_has_required_keys(self):
        sig = self._make_signal()
        d = sig.to_dict()
        for key in ("game_id", "home_team", "away_team", "market",
                    "sharp_side", "signal_types", "score", "score_label",
                    "details", "created_at"):
            assert key in d

    def test_score_label_matches_score(self):
        sig = self._make_signal(score=3)
        assert sig.score_label == "strong_signal"

    def test_signal_types_preserved(self):
        sig = self._make_signal()
        assert sig.to_dict()["signal_types"] == ["book_divergence"]

    def test_details_preserved(self):
        sig = self._make_signal()
        assert sig.to_dict()["details"]["divergence"] == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# SharpMoneyTracker._detect_rlm
# ---------------------------------------------------------------------------

class TestDetectRLM:
    def setup_method(self):
        self.tracker = SharpMoneyTracker()

    def test_public_heavy_home_but_sharp_favors_away_triggers_rlm(self):
        # 72% public on home, but sharp says home has only 42% prob
        result = self.tracker._detect_rlm(
            home_public_pct=0.72,
            sharp_home_prob=0.42,
            movement_signal=None,
        )
        assert result is not None
        assert result["type"] == "fade_home"

    def test_public_heavy_away_but_sharp_favors_home_triggers_rlm(self):
        # 35% public on home (65% on away), but sharps give home 55% prob
        result = self.tracker._detect_rlm(
            home_public_pct=0.35,
            sharp_home_prob=0.55,
            movement_signal=None,
        )
        assert result is not None
        assert result["type"] == "fade_away"

    def test_movement_against_public_triggers_rlm_signal(self):
        result = self.tracker._detect_rlm(
            home_public_pct=0.75,
            sharp_home_prob=0.55,  # sharps still lean home (won't trigger fade_home)
            movement_signal={"direction": "away_moving_shorter"},
        )
        assert result is not None
        assert result["type"] == "rlm_away"

    def test_balanced_public_with_no_movement_returns_none(self):
        result = self.tracker._detect_rlm(
            home_public_pct=0.50,
            sharp_home_prob=0.50,
            movement_signal=None,
        )
        assert result is None

    def test_below_threshold_home_pct_returns_none(self):
        # 55% public on home — not enough for RLM (threshold is 60%)
        result = self.tracker._detect_rlm(
            home_public_pct=0.55,
            sharp_home_prob=0.40,
            movement_signal=None,
        )
        assert result is None

    def test_rlm_includes_public_pct(self):
        result = self.tracker._detect_rlm(0.72, 0.42, None)
        assert "public_pct_home" in result


# ---------------------------------------------------------------------------
# SharpMoneyTracker._get_h2h_prices
# ---------------------------------------------------------------------------

SHARP_BOOKMAKERS = [
    {
        "key": "pinnacle",
        "markets": [
            {
                "key": "h2h",
                "outcomes": [
                    {"name": "Duke", "price": -138},
                    {"name": "UNC", "price": 120},
                ],
            }
        ],
    }
]

SQUARE_BOOKMAKERS = [
    {
        "key": "fanduel",
        "markets": [
            {
                "key": "h2h",
                "outcomes": [
                    {"name": "Duke", "price": -152},
                    {"name": "UNC", "price": 126},
                ],
            }
        ],
    }
]


class TestGetH2HPrices:
    def setup_method(self):
        self.tracker = SharpMoneyTracker()

    def test_returns_probs_for_both_teams(self):
        result = self.tracker._get_h2h_prices(SHARP_BOOKMAKERS, "Duke", "UNC")
        assert "Duke" in result
        assert "UNC" in result

    def test_probs_are_devigged(self):
        result = self.tracker._get_h2h_prices(SHARP_BOOKMAKERS, "Duke", "UNC")
        # devigged probs should sum to 1 per book
        duke_prob = result["Duke"][0]
        unc_prob = result["UNC"][0]
        assert duke_prob + unc_prob == pytest.approx(1.0, abs=0.001)

    def test_favourite_has_higher_prob(self):
        result = self.tracker._get_h2h_prices(SHARP_BOOKMAKERS, "Duke", "UNC")
        assert result["Duke"][0] > result["UNC"][0]

    def test_empty_bookmakers_returns_empty_lists(self):
        result = self.tracker._get_h2h_prices([], "Duke", "UNC")
        assert result["Duke"] == []
        assert result["UNC"] == []

    def test_non_h2h_market_ignored(self):
        bms = [{
            "key": "pinnacle",
            "markets": [{"key": "spreads", "outcomes": [
                {"name": "Duke", "price": -110, "point": -3.5},
                {"name": "UNC", "price": -110, "point": 3.5},
            ]}],
        }]
        result = self.tracker._get_h2h_prices(bms, "Duke", "UNC")
        assert result["Duke"] == []


# ---------------------------------------------------------------------------
# SharpMoneyTracker._get_spread_prices
# ---------------------------------------------------------------------------

SPREAD_BOOKMAKERS = [
    {
        "key": "pinnacle",
        "markets": [
            {
                "key": "spreads",
                "outcomes": [
                    {"name": "Duke", "price": -108, "point": -3.0},
                    {"name": "UNC", "price": -112, "point": 3.0},
                ],
            }
        ],
    },
    {
        "key": "fanduel",
        "markets": [
            {
                "key": "spreads",
                "outcomes": [
                    {"name": "Duke", "price": -110, "point": -3.5},
                    {"name": "UNC", "price": -110, "point": 3.5},
                ],
            }
        ],
    },
]


class TestGetSpreadPrices:
    def setup_method(self):
        self.tracker = SharpMoneyTracker()

    def test_returns_home_point_avg(self):
        result = self.tracker._get_spread_prices(SPREAD_BOOKMAKERS, "Duke", "UNC")
        assert "home_point_avg" in result

    def test_home_point_avg_is_average_of_books(self):
        result = self.tracker._get_spread_prices(SPREAD_BOOKMAKERS, "Duke", "UNC")
        # (-3.0 + -3.5) / 2 = -3.25
        assert result["home_point_avg"] == pytest.approx(-3.25)

    def test_empty_bookmakers_returns_none_averages(self):
        result = self.tracker._get_spread_prices([], "Duke", "UNC")
        assert result["home_point_avg"] is None
        assert result["away_point_avg"] is None

    def test_single_book(self):
        result = self.tracker._get_spread_prices(SPREAD_BOOKMAKERS[:1], "Duke", "UNC")
        assert result["home_point_avg"] == pytest.approx(-3.0)


# ---------------------------------------------------------------------------
# SharpMoneyTracker._infer_sharp_side
# ---------------------------------------------------------------------------

class TestInferSharpSide:
    def setup_method(self):
        self.tracker = SharpMoneyTracker()

    def test_returns_team_with_higher_sharp_prob(self):
        sharp_h2h = {"Duke": [0.60], "UNC": [0.40]}
        square_h2h = {"Duke": [0.55], "UNC": [0.45]}
        result = self.tracker._infer_sharp_side(sharp_h2h, square_h2h, "Duke", "UNC")
        assert result == "Duke"

    def test_returns_away_when_sharp_prob_lower_for_home(self):
        sharp_h2h = {"Duke": [0.42], "UNC": [0.58]}
        square_h2h = {"Duke": [0.52], "UNC": [0.48]}
        result = self.tracker._infer_sharp_side(sharp_h2h, square_h2h, "Duke", "UNC")
        assert result == "UNC"

    def test_empty_dicts_return_empty_string(self):
        result = self.tracker._infer_sharp_side({}, {}, "Duke", "UNC")
        assert result == ""


# ---------------------------------------------------------------------------
# SharpMoneyTracker._calc_book_divergence
# ---------------------------------------------------------------------------

DIVERGENCE_GAME = {
    "id": "game_001",
    "home_team": "Duke",
    "away_team": "UNC",
    "bookmakers": SHARP_BOOKMAKERS + SQUARE_BOOKMAKERS,
}

NO_DIVERGENCE_GAME = {
    "id": "game_002",
    "home_team": "Kansas",
    "away_team": "Kentucky",
    # Only sharp books — no square books
    "bookmakers": SHARP_BOOKMAKERS,
}


class TestCalcBookDivergence:
    def setup_method(self):
        self.tracker = SharpMoneyTracker()

    def test_returns_dict_with_divergence(self):
        result = self.tracker._calc_book_divergence(DIVERGENCE_GAME)
        assert result is not None
        assert "max_divergence" in result

    def test_divergence_is_positive(self):
        result = self.tracker._calc_book_divergence(DIVERGENCE_GAME)
        assert result["max_divergence"] >= 0.0

    def test_game_without_square_books_returns_none(self):
        result = self.tracker._calc_book_divergence(NO_DIVERGENCE_GAME)
        assert result is None

    def test_home_and_away_teams_recorded(self):
        result = self.tracker._calc_book_divergence(DIVERGENCE_GAME)
        assert result["home_team"] == "Duke"
        assert result["away_team"] == "UNC"


# ---------------------------------------------------------------------------
# SharpMoneyTracker._analyze_game
# ---------------------------------------------------------------------------

MOCK_GAME_WITH_SIGNALS = {
    "id": "game_001",
    "home_team": "Duke Blue Devils",
    "away_team": "North Carolina Tar Heels",
    "bookmakers": [
        {
            "key": "pinnacle",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Duke Blue Devils", "price": -138},
                        {"name": "North Carolina Tar Heels", "price": 120},
                    ],
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Duke Blue Devils", "price": -108, "point": -3.0},
                        {"name": "North Carolina Tar Heels", "price": -112, "point": 3.0},
                    ],
                },
            ],
        },
        {
            "key": "fanduel",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Duke Blue Devils", "price": -155},
                        {"name": "North Carolina Tar Heels", "price": 130},
                    ],
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Duke Blue Devils", "price": -110, "point": -3.5},
                        {"name": "North Carolina Tar Heels", "price": -110, "point": 3.5},
                    ],
                },
            ],
        },
    ],
    "_mock_public": {"home_bet_pct": 0.72, "away_bet_pct": 0.28},
    "_mock_movement": {
        "moneyline_movement": {
            "direction": "away_moving_shorter",
            "interpretation": "Sharp UNC action",
        },
        "spread_movement_signal": {
            "opening": -3.5,
            "current": -3.0,
        },
    },
}


class TestAnalyzeGame:
    def setup_method(self):
        self.tracker = SharpMoneyTracker()

    def test_returns_list_of_sharp_signals(self):
        signals = self.tracker._analyze_game(MOCK_GAME_WITH_SIGNALS)
        assert isinstance(signals, list)
        assert all(isinstance(s, SharpSignal) for s in signals)

    def test_game_with_divergence_generates_signals(self):
        signals = self.tracker._analyze_game(MOCK_GAME_WITH_SIGNALS)
        assert len(signals) > 0

    def test_all_signals_have_positive_score(self):
        signals = self.tracker._analyze_game(MOCK_GAME_WITH_SIGNALS)
        assert all(s.score >= 1 for s in signals)

    def test_empty_bookmakers_returns_empty_list(self):
        game = {
            "id": "x",
            "home_team": "A",
            "away_team": "B",
            "bookmakers": [],
        }
        signals = self.tracker._analyze_game(game)
        assert signals == []


# ---------------------------------------------------------------------------
# SharpMoneyTracker._compute_line_movement
# ---------------------------------------------------------------------------

class TestComputeLineMovement:
    def setup_method(self):
        self.tracker = SharpMoneyTracker()

    def _simple_game(self, game_id="g1", spread_point=-3.5, book="fanduel"):
        return {
            "id": game_id,
            "home_team": "Kansas",
            "away_team": "Kentucky",
            "bookmakers": [
                {
                    "key": book,
                    "markets": [
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Kansas", "price": -110, "point": spread_point},
                                {"name": "Kentucky", "price": -110, "point": -spread_point},
                            ],
                        }
                    ],
                }
            ],
        }

    def test_first_call_stores_snapshot_and_is_new(self):
        game = self._simple_game("new_game_1")
        result = self.tracker._compute_line_movement(game)
        assert result["direction"] == "new_snapshot"

    def test_second_call_detects_line_movement(self):
        game_id = "movement_test_1"
        # First call: snapshot at -3.5
        self.tracker._compute_line_movement(self._simple_game(game_id, -3.5))
        # Second call: line moved to -4.0
        result = self.tracker._compute_line_movement(self._simple_game(game_id, -4.0))
        assert result["spread_movement"] == pytest.approx(-0.5)
        assert result["direction"] == "home_moving_down"

    def test_no_movement_has_direction_none(self):
        game_id = "no_move_1"
        self.tracker._compute_line_movement(self._simple_game(game_id, -3.5))
        result = self.tracker._compute_line_movement(self._simple_game(game_id, -3.5))
        assert result["direction"] == "none"
