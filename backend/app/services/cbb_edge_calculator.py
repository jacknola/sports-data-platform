"""
College Basketball Edge Calculator

Calculates betting edge by:
1. Fetching live CBB odds from The Odds API (basketball_ncaab)
2. Devigging multiple bookmaker lines to derive true probabilities
3. Computing edge, expected value, and Kelly criterion per market
4. Tracking line movement to surface sharp action signals
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from loguru import logger

from app.config import settings


# Sharp / square book classification
SHARP_BOOKS = {"pinnacle", "betcris", "circa", "betonlineag", "bookmaker", "lowvig"}
SQUARE_BOOKS = {"draftkings", "fanduel", "betmgm", "caesars", "pointsbet", "barstool"}

# The Odds API sport key for NCAAB
NCAAB_SPORT_KEY = "basketball_ncaab"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def american_to_decimal(american: float) -> float:
    """Convert American odds to decimal odds."""
    if american >= 100:
        return (american / 100) + 1
    else:
        return (100 / abs(american)) + 1


def decimal_to_implied_prob(decimal: float) -> float:
    """Convert decimal odds to raw implied probability (includes vig)."""
    if decimal <= 0:
        return 0.0
    return 1 / decimal


def american_to_implied_prob(american: float) -> float:
    return decimal_to_implied_prob(american_to_decimal(american))


def implied_prob_to_american(prob: float) -> float:
    """Convert probability to American odds."""
    if prob <= 0 or prob >= 1:
        return 0.0
    if prob >= 0.5:
        return -round(100 * prob / (1 - prob), 1)
    return round(100 * (1 - prob) / prob, 1)


def multiplicative_devig(probs: List[float]) -> List[float]:
    """
    Remove bookmaker margin using the multiplicative method.
    Each raw implied prob is divided by the overround.

    Example: home=0.55, away=0.55 → overround=1.10
    Devigged: home=0.5, away=0.5
    """
    overround = sum(probs)
    if overround <= 0:
        return probs
    return [p / overround for p in probs]


def additive_devig(probs: List[float]) -> List[float]:
    """
    Remove bookmaker margin using the additive (equal distribution) method.
    Subtract half the vig from each side.
    """
    overround = sum(probs)
    vig = overround - 1.0
    vig_per_side = vig / len(probs)
    return [max(0.001, p - vig_per_side) for p in probs]


def calculate_ev(true_prob: float, decimal_odds: float) -> float:
    """
    Expected value per unit staked.
    EV = (true_prob * profit) - (1 - true_prob) * stake
       = true_prob * (decimal_odds - 1) - (1 - true_prob)
    """
    return true_prob * (decimal_odds - 1) - (1 - true_prob)


def kelly_criterion(true_prob: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """
    Fractional Kelly bet size as % of bankroll.
    Full Kelly = (b*p - q) / b  where b = decimal_odds - 1, p = win prob, q = 1-p
    Capped at fraction * full Kelly for risk management.
    """
    b = decimal_odds - 1
    if b <= 0:
        return 0.0
    q = 1 - true_prob
    full_kelly = (b * true_prob - q) / b
    return max(0.0, min(full_kelly * fraction, 0.05))  # max 5% of bankroll (per platform policy)


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------

class CBBEdgeCalculator:
    """
    Fetches live NCAAB odds and calculates edge for each game/market.
    """

    def __init__(self) -> None:
        self.api_key: Optional[str] = getattr(settings, "THE_ODDS_API_KEY", None) or \
                                      getattr(settings, "ODDSAPI_API_KEY", None)
        # Delegate odds fetching to SportsAPIService (handles caching + SGO fallback)
        from app.services.sports_api import SportsAPIService
        self._sports_api = SportsAPIService()

    @property
    def has_live_data_source(self) -> bool:
        """True if either The Odds API or SportsGameOdds is configured."""
        if self.api_key:
            return True
        try:
            from app.services.sports_game_odds import SportsGameOddsService
            return SportsGameOddsService().is_configured
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_games_with_edge(
        self,
        min_edge: float = 0.02,
        markets: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Return all NCAAB games enriched with edge metrics.

        Args:
            min_edge: Only return bets where edge >= this threshold.
            markets: List of market types: ['h2h', 'spreads', 'totals']

        Returns:
            List of game dicts sorted by best available edge descending.
        """
        if markets is None:
            markets = ["h2h", "spreads", "totals"]

        raw_games = await self._fetch_odds(markets=markets)

        if not raw_games:
            logger.warning("No CBB games returned from odds API – using mock data")
            raw_games = self._mock_games()

        results = []
        for game in raw_games:
            enriched = self._enrich_game(game, min_edge)
            if enriched:
                results.append(enriched)

        results.sort(key=lambda g: g.get("best_edge", 0), reverse=True)
        return results

    async def get_line_history(self, game_id: str) -> Dict[str, Any]:
        """
        Fetch opening and historical lines for a specific game.
        Returns line movement data.
        """
        raw = await self._fetch_historical_lines(game_id)
        return raw

    # ------------------------------------------------------------------
    # Odds fetching
    # ------------------------------------------------------------------

    async def _fetch_odds(self, markets: List[str]) -> List[Dict[str, Any]]:
        """Fetch NCAAB odds via SportsAPIService (handles caching + SGO fallback)."""
        markets_param = ",".join(markets)
        bookmakers = ",".join([
            "pinnacle", "betcris", "betonlineag", "bookmaker",
            "draftkings", "fanduel", "betmgm", "caesars",
            "pointsbet", "williamhill_us",
        ])
        data = await self._sports_api.get_odds(
            sport=NCAAB_SPORT_KEY,
            markets=markets_param,
            bookmakers=bookmakers,
        )
        if data:
            logger.info(f"Fetched {len(data)} NCAAB games via SportsAPIService")
        return data

    async def _fetch_historical_lines(self, game_id: str) -> Dict[str, Any]:
        """Fetch opening line data for line movement tracking."""
        if not self.api_key:
            return {}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                url = f"{self.BASE_URL}/sports/{NCAAB_SPORT_KEY}/odds-history"
                response = await client.get(
                    url,
                    params={
                        "apiKey": self.api_key,
                        "regions": "us",
                        "markets": "h2h,spreads",
                        "oddsFormat": "american",
                        "eventIds": game_id,
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.error(f"Failed to fetch line history for {game_id}: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    def _enrich_game(
        self, game: Dict[str, Any], min_edge: float
    ) -> Optional[Dict[str, Any]]:
        """Compute edge metrics for every market in a game."""
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")
        commence_time = game.get("commence_time", "")
        game_id = game.get("id", "")

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            return None

        # Separate sharp and square lines
        sharp_lines = [b for b in bookmakers if b["key"] in SHARP_BOOKS]
        all_lines = bookmakers

        # Build per-market edge data
        markets_data: Dict[str, Any] = {}

        for market_type in ("h2h", "spreads", "totals"):
            edge_info = self._calc_market_edge(
                market_type, home_team, away_team, sharp_lines, all_lines
            )
            if edge_info:
                markets_data[market_type] = edge_info

        if not markets_data:
            return None

        # Best edge across all markets
        all_edges = [
            bet["edge"]
            for m in markets_data.values()
            for bet in m.get("bets", [])
        ]
        best_edge = max(all_edges) if all_edges else 0.0

        if best_edge < min_edge:
            return None

        return {
            "game_id": game_id,
            "home_team": home_team,
            "away_team": away_team,
            "commence_time": commence_time,
            "sport": "NCAAB",
            "best_edge": round(best_edge, 4),
            "markets": markets_data,
            "bookmaker_count": len(bookmakers),
            "sharp_book_count": len(sharp_lines),
        }

    def _calc_market_edge(
        self,
        market_type: str,
        home_team: str,
        away_team: str,
        sharp_lines: List[Dict],
        all_lines: List[Dict],
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate edge for a specific market type across bookmakers.

        Strategy:
        - Use SHARP book consensus probability as "true" probability.
        - Compare against the BEST available price on any book.
        - Edge = true_prob - market_implied_prob_at_best_price
        """
        # Gather sharp book prices for this market
        sharp_prices = self._extract_market_prices(market_type, sharp_lines)
        all_prices = self._extract_market_prices(market_type, all_lines)

        if not all_prices:
            return None

        # Use sharp book consensus if available, else full market consensus
        source_prices = sharp_prices if len(sharp_prices) >= 2 else all_prices

        # Derive consensus true probabilities from devigged sharp lines
        consensus = self._build_consensus(market_type, source_prices, home_team, away_team)
        if not consensus:
            return None

        # Find best available price on any book for each side
        bets = []
        for side_key, true_prob in consensus.items():
            best_american, best_book = self._find_best_price(side_key, all_prices)
            if best_american is None:
                continue

            best_decimal = american_to_decimal(best_american)
            market_implied = decimal_to_implied_prob(best_decimal)
            edge = true_prob - market_implied
            ev = calculate_ev(true_prob, best_decimal)
            kelly = kelly_criterion(true_prob, best_decimal)
            fair_american = implied_prob_to_american(true_prob)

            bets.append({
                "side": side_key,
                "true_prob": round(true_prob, 4),
                "fair_odds": round(fair_american, 1),
                "best_available_odds": best_american,
                "best_book": best_book,
                "market_implied_prob": round(market_implied, 4),
                "edge": round(edge, 4),
                "ev_per_unit": round(ev, 4),
                "kelly_fraction": round(kelly, 4),
                "is_positive_ev": ev > 0,
            })

        bets.sort(key=lambda b: b["edge"], reverse=True)

        return {
            "market_type": market_type,
            "bets": bets,
            "best_edge": bets[0]["edge"] if bets else 0.0,
        }

    # ------------------------------------------------------------------
    # Price extraction helpers
    # ------------------------------------------------------------------

    def _extract_market_prices(
        self, market_type: str, bookmakers: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Extract a flat list of {book, outcome_name, price, point} records
        for a given market type from a list of bookmaker objects.
        """
        prices = []
        for bm in bookmakers:
            book_key = bm.get("key", "")
            for market in bm.get("markets", []):
                if market.get("key") != market_type:
                    continue
                for outcome in market.get("outcomes", []):
                    prices.append({
                        "book": book_key,
                        "name": outcome.get("name", ""),
                        "price": outcome.get("price"),
                        "point": outcome.get("point"),
                    })
        return prices

    def _build_consensus(
        self,
        market_type: str,
        prices: List[Dict],
        home_team: str,
        away_team: str,
    ) -> Optional[Dict[str, float]]:
        """
        Compute consensus true probabilities for all sides of a market
        by averaging devigged probabilities across source books.
        """
        if market_type == "h2h":
            return self._consensus_h2h(prices, home_team, away_team)
        elif market_type == "spreads":
            return self._consensus_spreads(prices, home_team, away_team)
        elif market_type == "totals":
            return self._consensus_totals(prices)
        return None

    def _devig_two_way_prices(
        self,
        prices: List[Dict],
        side_a_name: str,
        side_b_name: str,
    ) -> Tuple[List[float], List[float]]:
        """
        Compute per-book devigged probabilities for a two-way market.

        Groups prices by book, finds the matching outcome for each side, and
        applies multiplicative devigging to each pair.

        Args:
            prices:       Flat list of {book, name, price, point} records.
            side_a_name:  Outcome name to match as side A (e.g. home team).
            side_b_name:  Outcome name to match as side B (e.g. away team).

        Returns:
            Tuple of (side_a_probs, side_b_probs) — one entry per book that
            had complete pricing for both sides.
        """
        a_probs: List[float] = []
        b_probs: List[float] = []
        for book in {p["book"] for p in prices}:
            book_prices = [p for p in prices if p["book"] == book]
            side_a = next((p for p in book_prices if p["name"] == side_a_name), None)
            side_b = next((p for p in book_prices if p["name"] == side_b_name), None)
            if side_a and side_b and side_a["price"] and side_b["price"]:
                raw = [
                    american_to_implied_prob(side_a["price"]),
                    american_to_implied_prob(side_b["price"]),
                ]
                devigged = multiplicative_devig(raw)
                a_probs.append(devigged[0])
                b_probs.append(devigged[1])
        return a_probs, b_probs

    def _consensus_h2h(
        self, prices: List[Dict], home: str, away: str
    ) -> Optional[Dict[str, float]]:
        home_probs, away_probs = self._devig_two_way_prices(prices, home, away)
        if not home_probs:
            return None
        return {
            home: float(np.mean(home_probs)),
            away: float(np.mean(away_probs)),
        }

    def _consensus_spreads(
        self, prices: List[Dict], home: str, away: str
    ) -> Optional[Dict[str, float]]:
        home_probs, away_probs = self._devig_two_way_prices(prices, home, away)
        if not home_probs:
            return None
        return {
            f"{home} spread": float(np.mean(home_probs)),
            f"{away} spread": float(np.mean(away_probs)),
        }

    def _consensus_totals(self, prices: List[Dict]) -> Optional[Dict[str, float]]:
        over_probs: List[float] = []
        under_probs: List[float] = []

        books = {p["book"] for p in prices}
        for book in books:
            book_prices = [p for p in prices if p["book"] == book]
            over_p = next((p for p in book_prices if p["name"] == "Over"), None)
            under_p = next((p for p in book_prices if p["name"] == "Under"), None)
            if over_p and under_p and over_p["price"] and under_p["price"]:
                raw = [
                    american_to_implied_prob(over_p["price"]),
                    american_to_implied_prob(under_p["price"]),
                ]
                devigged = multiplicative_devig(raw)
                over_probs.append(devigged[0])
                under_probs.append(devigged[1])

        if not over_probs:
            return None

        total_line = prices[0]["point"] if prices else 0
        label = f"o{total_line}" if total_line else "over"
        return {
            label: float(np.mean(over_probs)),
            f"u{total_line}" if total_line else "under": float(np.mean(under_probs)),
        }

    def _find_best_price(
        self, side_key: str, all_prices: List[Dict]
    ) -> Tuple[Optional[float], str]:
        """
        Find the best (most favorable) American odds for a given side
        across all bookmakers.

        For positive EV the best price = highest American odds for the side.
        """
        candidates = []
        for p in all_prices:
            name = p.get("name", "")
            # Match by checking if the name is contained in the side key or vice versa
            if name in side_key or side_key.startswith(name):
                if p.get("price") is not None:
                    candidates.append((p["price"], p["book"]))

        if not candidates:
            return None, ""

        # Best price = highest American odds (least negative / most positive)
        best = max(candidates, key=lambda x: x[0])
        return best[0], best[1]

    # ------------------------------------------------------------------
    # Mock data (used when API key not configured)
    # ------------------------------------------------------------------

    def _mock_games(self) -> List[Dict[str, Any]]:
        """Return realistic mock CBB games for development/demo purposes."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": "mock_game_001",
                "sport_key": "basketball_ncaab",
                "commence_time": now,
                "home_team": "Duke Blue Devils",
                "away_team": "North Carolina Tar Heels",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -145},
                                    {"name": "North Carolina Tar Heels", "price": 125},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -110, "point": -3.5},
                                    {"name": "North Carolina Tar Heels", "price": -110, "point": 3.5},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": -108, "point": 152.5},
                                    {"name": "Under", "price": -112, "point": 152.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "fanduel",
                        "title": "FanDuel",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -152},
                                    {"name": "North Carolina Tar Heels", "price": 126},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -112, "point": -3.5},
                                    {"name": "North Carolina Tar Heels", "price": -108, "point": 3.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "draftkings",
                        "title": "DraftKings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -148},
                                    {"name": "North Carolina Tar Heels", "price": 122},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": -115, "point": 152.5},
                                    {"name": "Under", "price": -105, "point": 152.5},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "id": "mock_game_002",
                "sport_key": "basketball_ncaab",
                "commence_time": now,
                "home_team": "Kansas Jayhawks",
                "away_team": "Kentucky Wildcats",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -120},
                                    {"name": "Kentucky Wildcats", "price": 102},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -108, "point": -2.0},
                                    {"name": "Kentucky Wildcats", "price": -112, "point": 2.0},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": -110, "point": 145.5},
                                    {"name": "Under", "price": -110, "point": 145.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "fanduel",
                        "title": "FanDuel",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -125},
                                    {"name": "Kentucky Wildcats", "price": 106},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -110, "point": -2.0},
                                    {"name": "Kentucky Wildcats", "price": -110, "point": 2.0},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "betmgm",
                        "title": "BetMGM",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -118},
                                    {"name": "Kentucky Wildcats", "price": +100},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": -112, "point": 145.5},
                                    {"name": "Under", "price": -108, "point": 145.5},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "id": "mock_game_003",
                "sport_key": "basketball_ncaab",
                "commence_time": now,
                "home_team": "Gonzaga Bulldogs",
                "away_team": "Arizona Wildcats",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -200},
                                    {"name": "Arizona Wildcats", "price": 170},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -112, "point": -5.5},
                                    {"name": "Arizona Wildcats", "price": -108, "point": 5.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "caesars",
                        "title": "Caesars",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -210},
                                    {"name": "Arizona Wildcats", "price": 175},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -115, "point": -5.5},
                                    {"name": "Arizona Wildcats", "price": -105, "point": 5.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "draftkings",
                        "title": "DraftKings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -195},
                                    {"name": "Arizona Wildcats", "price": 165},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": -110, "point": 158.0},
                                    {"name": "Under", "price": -110, "point": 158.0},
                                ],
                            },
                        ],
                    },
                ],
            },
        ]
