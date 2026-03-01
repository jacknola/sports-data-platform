"""
Unit tests for app/services/cbb_edge_calculator.py

Covers:
- Pure helper functions (american_to_decimal, devig, EV, Kelly)
- CBBEdgeCalculator._extract_market_prices
- CBBEdgeCalculator._consensus_* methods
- CBBEdgeCalculator._find_best_price
- CBBEdgeCalculator._enrich_game (uses mock bookmaker data)
"""
import pytest

from app.services.cbb_edge_calculator import (
    american_to_decimal,
    decimal_to_implied_prob,
    american_to_implied_prob,
    implied_prob_to_american,
    multiplicative_devig,
    additive_devig,
    calculate_ev,
    kelly_criterion,
    CBBEdgeCalculator,
)


# ---------------------------------------------------------------------------
# american_to_decimal
# ---------------------------------------------------------------------------

class TestAmericanToDecimal:
    def test_positive_odds(self):
        # +150 -> 2.50
        assert american_to_decimal(150) == pytest.approx(2.50)

    def test_negative_odds(self):
        # -110 -> 100/110 + 1 = 1.909...
        assert american_to_decimal(-110) == pytest.approx(100 / 110 + 1)

    def test_even_money_positive(self):
        # +100 -> 2.0
        assert american_to_decimal(100) == pytest.approx(2.0)

    def test_heavy_favourite(self):
        # -200 -> 100/200 + 1 = 1.50
        assert american_to_decimal(-200) == pytest.approx(1.50)

    def test_big_underdog(self):
        # +300 -> 4.0
        assert american_to_decimal(300) == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# decimal_to_implied_prob
# ---------------------------------------------------------------------------

class TestDecimalToImpliedProb:
    def test_evens(self):
        assert decimal_to_implied_prob(2.0) == pytest.approx(0.5)

    def test_favourite(self):
        # 1.50 -> 0.6667
        assert decimal_to_implied_prob(1.5) == pytest.approx(1 / 1.5)

    def test_zero_decimal_returns_zero(self):
        assert decimal_to_implied_prob(0.0) == 0.0

    def test_negative_decimal_returns_zero(self):
        assert decimal_to_implied_prob(-1.0) == 0.0


# ---------------------------------------------------------------------------
# american_to_implied_prob
# ---------------------------------------------------------------------------

class TestAmericanToImpliedProb:
    def test_minus_110_is_52_pct(self):
        # Standard spread juice: 110/(110+100) ≈ 0.5238
        prob = american_to_implied_prob(-110)
        assert prob == pytest.approx(110 / 210, rel=1e-4)

    def test_plus_100_is_50_pct(self):
        assert american_to_implied_prob(100) == pytest.approx(0.50)

    def test_minus_200_is_67_pct(self):
        assert american_to_implied_prob(-200) == pytest.approx(200 / 300, rel=1e-4)

    def test_plus_200_is_33_pct(self):
        assert american_to_implied_prob(200) == pytest.approx(100 / 300, rel=1e-4)


# ---------------------------------------------------------------------------
# implied_prob_to_american
# ---------------------------------------------------------------------------

class TestImpliedProbToAmerican:
    def test_50_pct_returns_negative_100(self):
        assert implied_prob_to_american(0.50) == pytest.approx(-100.0, abs=0.5)

    def test_prob_0_returns_zero(self):
        assert implied_prob_to_american(0.0) == 0.0

    def test_prob_1_returns_zero(self):
        assert implied_prob_to_american(1.0) == 0.0

    def test_favourite_is_negative(self):
        # 60% favourite -> negative American odds
        american = implied_prob_to_american(0.60)
        assert american < 0

    def test_underdog_is_positive(self):
        # 40% underdog -> positive American odds
        american = implied_prob_to_american(0.40)
        assert american > 0

    def test_roundtrip_probability(self):
        # Convert prob -> american -> prob and get back close to original
        original = 0.65
        american = implied_prob_to_american(original)
        recovered = american_to_implied_prob(american)
        assert recovered == pytest.approx(original, abs=0.01)


# ---------------------------------------------------------------------------
# multiplicative_devig
# ---------------------------------------------------------------------------

class TestMultiplicativeDevig:
    def test_vig_removed(self):
        # Home=0.55, Away=0.55 -> overround=1.10; devigged = 0.50 each
        result = multiplicative_devig([0.55, 0.55])
        assert result[0] == pytest.approx(0.50)
        assert result[1] == pytest.approx(0.50)

    def test_output_sums_to_one(self):
        probs = [0.52, 0.51]  # overround=1.03
        result = multiplicative_devig(probs)
        assert sum(result) == pytest.approx(1.0)

    def test_zero_overround_returns_original(self):
        # guard against zero division
        result = multiplicative_devig([0.0, 0.0])
        assert result == [0.0, 0.0]

    def test_asymmetric_market(self):
        # Heavy favourite market
        probs = [0.70, 0.35]  # overround=1.05
        result = multiplicative_devig(probs)
        assert sum(result) == pytest.approx(1.0)
        assert result[0] > result[1]  # favourite still has higher prob

    def test_three_way_market(self):
        probs = [0.40, 0.35, 0.35]  # 1.10 overround
        result = multiplicative_devig(probs)
        assert sum(result) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# additive_devig
# ---------------------------------------------------------------------------

class TestAdditiveDevig:
    def test_output_sums_to_one(self):
        probs = [0.54, 0.54]
        result = additive_devig(probs)
        assert sum(result) == pytest.approx(1.0)

    def test_all_positive(self):
        probs = [0.54, 0.54]
        result = additive_devig(probs)
        assert all(p > 0 for p in result)

    def test_floors_at_minimum(self):
        # If a prob is tiny, result should be >= 0.001
        probs = [0.99, 0.06]
        result = additive_devig(probs)
        assert all(p >= 0.001 for p in result)


# ---------------------------------------------------------------------------
# calculate_ev
# ---------------------------------------------------------------------------

class TestCalculateEV:
    def test_positive_ev_with_edge(self):
        # true_prob=0.60, decimal_odds=2.0 (even money)
        # EV = 0.60 * 1.0 - 0.40 = 0.20
        ev = calculate_ev(0.60, 2.0)
        assert ev == pytest.approx(0.20)

    def test_negative_ev_without_edge(self):
        # true_prob=0.45 vs implied 0.50
        ev = calculate_ev(0.45, 2.0)
        assert ev < 0

    def test_zero_ev_at_fair_odds(self):
        # When true_prob == implied_prob the EV is 0
        # true_prob=0.50, decimal=2.0 -> EV = 0.50*1 - 0.50 = 0
        ev = calculate_ev(0.50, 2.0)
        assert ev == pytest.approx(0.0)

    def test_formula_accuracy(self):
        # EV = p*(d-1) - (1-p)
        p, d = 0.55, 1.909
        expected = p * (d - 1) - (1 - p)
        assert calculate_ev(p, d) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# kelly_criterion
# ---------------------------------------------------------------------------

class TestKellyCriterion:
    def test_no_edge_returns_zero(self):
        # When true_prob == implied_prob, full Kelly = 0
        assert kelly_criterion(0.50, 2.0) == pytest.approx(0.0, abs=1e-6)

    def test_negative_edge_returns_zero(self):
        assert kelly_criterion(0.40, 2.0) == 0.0

    def test_positive_edge_returns_positive(self):
        stake = kelly_criterion(0.60, 2.0)
        assert stake > 0

    def test_capped_at_10_pct(self):
        # Huge edge should be capped at 0.10
        stake = kelly_criterion(0.99, 2.0)
        assert stake <= 0.10

    def test_fractional_25_pct_applied(self):
        # With 50% win prob on evens -> full Kelly = 0; with 60%:
        # full = (1*0.60 - 0.40)/1 = 0.20; fractional = 0.25*0.20 = 0.05
        stake = kelly_criterion(0.60, 2.0, fraction=0.25)
        assert stake == pytest.approx(0.05, abs=1e-6)

    def test_zero_odds_returns_zero(self):
        assert kelly_criterion(0.60, 1.0) == 0.0  # b=0


# ---------------------------------------------------------------------------
# CBBEdgeCalculator._extract_market_prices
# ---------------------------------------------------------------------------

SAMPLE_BOOKMAKERS = [
    {
        "key": "pinnacle",
        "markets": [
            {
                "key": "h2h",
                "outcomes": [
                    {"name": "Duke", "price": -140},
                    {"name": "UNC", "price": 120},
                ],
            },
            {
                "key": "spreads",
                "outcomes": [
                    {"name": "Duke", "price": -110, "point": -3.5},
                    {"name": "UNC", "price": -110, "point": 3.5},
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
                    {"name": "Duke", "price": -150},
                    {"name": "UNC", "price": 126},
                ],
            },
        ],
    },
]


class TestExtractMarketPrices:
    def setup_method(self):
        self.calc = CBBEdgeCalculator()

    def test_extracts_h2h_prices(self):
        prices = self.calc._extract_market_prices("h2h", SAMPLE_BOOKMAKERS)
        assert len(prices) == 4  # 2 books × 2 outcomes

    def test_extracts_spreads_only_from_matching_books(self):
        prices = self.calc._extract_market_prices("spreads", SAMPLE_BOOKMAKERS)
        # Only pinnacle has spreads
        assert len(prices) == 2

    def test_totals_returns_empty_when_none_present(self):
        prices = self.calc._extract_market_prices("totals", SAMPLE_BOOKMAKERS)
        assert prices == []

    def test_price_record_has_required_keys(self):
        prices = self.calc._extract_market_prices("h2h", SAMPLE_BOOKMAKERS)
        for p in prices:
            assert "book" in p
            assert "name" in p
            assert "price" in p


# ---------------------------------------------------------------------------
# CBBEdgeCalculator._consensus_h2h
# ---------------------------------------------------------------------------

class TestConsensusH2H:
    def setup_method(self):
        self.calc = CBBEdgeCalculator()

    def _build_prices(self, home_price, away_price, book="pinnacle"):
        return [
            {"book": book, "name": "Duke", "price": home_price, "point": None},
            {"book": book, "name": "UNC", "price": away_price, "point": None},
        ]

    def test_returns_dict_with_both_teams(self):
        prices = self._build_prices(-140, 120)
        result = self.calc._consensus_h2h(prices, "Duke", "UNC")
        assert "Duke" in result
        assert "UNC" in result

    def test_probabilities_sum_to_one(self):
        prices = self._build_prices(-140, 120)
        result = self.calc._consensus_h2h(prices, "Duke", "UNC")
        assert sum(result.values()) == pytest.approx(1.0, abs=0.01)

    def test_favourite_has_higher_probability(self):
        prices = self._build_prices(-200, 170)
        result = self.calc._consensus_h2h(prices, "Duke", "UNC")
        assert result["Duke"] > result["UNC"]

    def test_empty_prices_returns_none(self):
        result = self.calc._consensus_h2h([], "Duke", "UNC")
        assert result is None

    def test_averages_across_multiple_books(self):
        prices = (
            self._build_prices(-140, 120, "pinnacle")
            + self._build_prices(-150, 126, "fanduel")
        )
        result = self.calc._consensus_h2h(prices, "Duke", "UNC")
        # Should average both books' devigged probs
        assert result is not None
        assert sum(result.values()) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# CBBEdgeCalculator._consensus_totals
# ---------------------------------------------------------------------------

class TestConsensusTotals:
    def setup_method(self):
        self.calc = CBBEdgeCalculator()

    def _build_total_prices(self, over_price, under_price, point=152.5, book="pinnacle"):
        return [
            {"book": book, "name": "Over", "price": over_price, "point": point},
            {"book": book, "name": "Under", "price": under_price, "point": point},
        ]

    def test_returns_over_and_under(self):
        prices = self._build_total_prices(-108, -112)
        result = self.calc._consensus_totals(prices)
        assert result is not None
        assert len(result) == 2

    def test_probabilities_sum_to_one(self):
        prices = self._build_total_prices(-110, -110)
        result = self.calc._consensus_totals(prices)
        assert sum(result.values()) == pytest.approx(1.0, abs=0.01)

    def test_empty_prices_returns_none(self):
        result = self.calc._consensus_totals([])
        assert result is None


# ---------------------------------------------------------------------------
# CBBEdgeCalculator._find_best_price
# ---------------------------------------------------------------------------

class TestFindBestPrice:
    def setup_method(self):
        self.calc = CBBEdgeCalculator()

    def _make_prices(self, entries):
        """entries: list of (name, price, book)"""
        return [{"name": n, "price": p, "book": b} for n, p, b in entries]

    def test_returns_highest_american_odds(self):
        prices = self._make_prices([
            ("Duke", -140, "pinnacle"),
            ("Duke", -148, "fanduel"),
            ("Duke", -145, "draftkings"),
        ])
        best_price, best_book = self.calc._find_best_price("Duke", prices)
        assert best_price == -140  # least-negative = best for bettor
        assert best_book == "pinnacle"

    def test_no_match_returns_none(self):
        prices = self._make_prices([("UNC", -110, "pinnacle")])
        best_price, best_book = self.calc._find_best_price("Duke", prices)
        assert best_price is None
        assert best_book == ""

    def test_positive_odds_picked_over_negative(self):
        prices = self._make_prices([
            ("UNC", 120, "pinnacle"),
            ("UNC", -110, "fanduel"),
        ])
        best_price, _ = self.calc._find_best_price("UNC", prices)
        assert best_price == 120


# ---------------------------------------------------------------------------
# CBBEdgeCalculator._enrich_game
# ---------------------------------------------------------------------------

MOCK_GAME = {
    "id": "game_001",
    "home_team": "Duke Blue Devils",
    "away_team": "UNC Tar Heels",
    "commence_time": "2026-03-01T19:00:00Z",
    "bookmakers": [
        {
            "key": "pinnacle",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Duke Blue Devils", "price": -140},
                        {"name": "UNC Tar Heels", "price": 120},
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
                        {"name": "Duke Blue Devils", "price": -150},
                        {"name": "UNC Tar Heels", "price": 126},
                    ],
                },
            ],
        },
    ],
}


class TestEnrichGame:
    def setup_method(self):
        self.calc = CBBEdgeCalculator()

    def test_enriched_game_has_required_keys(self):
        # Use min_edge=-1.0: real vig produces small negative edges; we just test structure
        result = self.calc._enrich_game(MOCK_GAME, min_edge=-1.0)
        assert result is not None
        for key in ("game_id", "home_team", "away_team", "best_edge", "markets"):
            assert key in result

    def test_game_with_no_bookmakers_returns_none(self):
        game = {**MOCK_GAME, "bookmakers": []}
        result = self.calc._enrich_game(game, min_edge=-1.0)
        assert result is None

    def test_best_edge_is_float(self):
        result = self.calc._enrich_game(MOCK_GAME, min_edge=-1.0)
        assert isinstance(result["best_edge"], float)

    def test_min_edge_filter_applied(self):
        # Standard vig on mock data yields edges well below 0.10 → filtered out
        result = self.calc._enrich_game(MOCK_GAME, min_edge=0.10)
        assert result is None

    def test_bookmaker_count_recorded(self):
        result = self.calc._enrich_game(MOCK_GAME, min_edge=-1.0)
        assert result["bookmaker_count"] == 2
