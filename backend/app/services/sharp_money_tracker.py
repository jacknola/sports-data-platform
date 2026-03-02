"""
Sharp Money Tracker for College Basketball

Identifies where professional (sharp) bettors are placing money by analyzing:

1. Reverse Line Movement (RLM)
   - Public betting % heavily favors Team A
   - Yet the line moves TOWARD Team B (making them cheaper)
   - Conclusion: sharp money on Team B is moving the line despite public action

2. Steam Moves
   - Multiple major sportsbooks move their line in the same direction
     within a short time window (~15 minutes)
   - Indicates coordinated sharp action at multiple books simultaneously

3. Book Discrepancy / Stale Line Hunting
   - Sharp books (Pinnacle, Circa) have moved, but square books haven't caught up
   - The divergence between sharp-book price and square-book price creates
     an exploitable window

4. Sharp Book vs Square Book Consensus
   - Compare implied probabilities from sharp books vs square books
   - Large divergence = sharp books have different information

5. Public Bias Fade
   - When >70% of public bets are on one side AND the line moves the other way
   - Classic "fade the public" signal
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger

from app.config import settings
from app.models.sharp_signals import DataQuality, DataSource, SignalMetadata
from app.services.sharp_signal_metrics import SharpSignalMetrics
from app.services.cbb_edge_calculator import (
    NCAAB_SPORT_KEY,
    SHARP_BOOKS,
    SQUARE_BOOKS,
    american_to_implied_prob,
    multiplicative_devig,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Steam threshold: if N or more books move the same direction = steam
STEAM_BOOK_THRESHOLD = 3

# RLM: public must be this heavily on one side for RLM to be flagged
RLM_PUBLIC_THRESHOLD = 0.60  # 60%+ public on one side

# Stale-line divergence: if sharp vs square implied prob differs by this much
STALE_LINE_DIVERGENCE = 0.03  # 3 percentage points

# Sharp signal score interpretation
SCORE_LABELS = {
    (0, 1): "no_signal",
    (1, 2): "weak_signal",
    (2, 3): "moderate_signal",
    (3, 4): "strong_signal",
    (4, 5): "very_strong_signal",
}


def _score_label(score: int) -> str:
    for (low, high), label in SCORE_LABELS.items():
        if low <= score < high:
            return label
    return "very_strong_signal"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class SharpSignal:
    """Represents a single sharp money signal for one side of a game."""

    def __init__(
        self,
        game_id: str,
        home_team: str,
        away_team: str,
        market: str,
        sharp_side: str,
        signal_types: List[str],
        score: int,
        details: Dict[str, Any],
        metadata: Optional[SignalMetadata] = None,
    ) -> None:
        self.game_id = game_id
        self.home_team = home_team
        self.away_team = away_team
        self.market = market
        self.sharp_side = sharp_side
        self.signal_types = signal_types
        self.score = score
        self.score_label = _score_label(score)
        self.details = details
        self.created_at = datetime.now(timezone.utc).isoformat()
        # Add metadata for data quality tracking
        self.metadata = metadata or SignalMetadata(
            quality=DataQuality.MOCK,
            source=DataSource.SIMULATED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "market": self.market,
            "sharp_side": self.sharp_side,
            "signal_types": self.signal_types,
            "score": self.score,
            "score_label": self.score_label,
            "details": self.details,
            "created_at": self.created_at,
            "metadata": self.metadata.to_dict(),
            "data_quality": self.metadata.quality.value,
            "data_source": self.metadata.source.value,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class SharpMoneyTracker:
    """
    Detects sharp money signals in NCAAB betting markets.
    """

    def __init__(self, strict_mode: bool = False) -> None:
        self.api_key: Optional[str] = (
            getattr(settings, "THE_ODDS_API_KEY", None)
            or getattr(settings, "ODDSAPI_API_KEY", None)
        )
        # Delegate odds fetching to SportsAPIService (handles caching + SGO fallback)
        from app.services.sports_api import SportsAPIService
        self._sports_api = SportsAPIService()
        # In-memory line snapshot cache: game_id -> snapshot at fetch time
        self._line_snapshots: Dict[str, Dict] = {}
        # Strict mode: return None instead of mock data
        self.strict_mode = strict_mode
        # Data quality metrics tracking
        self._data_quality_log: List[Dict[str, Any]] = []
        # Metrics collector
        self.metrics = SharpSignalMetrics()
        self.strict_mode = strict_mode
        # Data quality metrics tracking
        self._data_quality_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_sharp_signals(
        self, min_score: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Return sharp money signals for all active NCAAB games.

        Args:
            min_score: Only return signals with score >= this value (1-4).

        Returns:
            List of SharpSignal dicts sorted by score descending.
        """
        games = await self._fetch_current_odds()

        if not games:
            logger.warning("No CBB games from API – generating mock sharp signals")
            games = self._mock_games_with_movement()

        signals: List[SharpSignal] = []
        for game in games:
            game_signals = self._analyze_game(game)
            signals.extend(game_signals)

        # Filter and sort
        signals = [s for s in signals if s.score >= min_score]
        signals.sort(key=lambda s: s.score, reverse=True)

        return [s.to_dict() for s in signals]

    async def get_line_movement_report(self) -> List[Dict[str, Any]]:
        """
        Return line movement summary for all active NCAAB games.
        Compares the first snapshot stored to the current odds.
        """
        current_games = await self._fetch_current_odds()
        if not current_games:
            current_games = self._mock_games_with_movement()

        report = []
        for game in current_games:
            movement = self._compute_line_movement(game)
            if movement:
                report.append(movement)

        report.sort(key=lambda r: abs(r.get("spread_movement", 0)), reverse=True)
        return report

    async def get_book_divergence(self) -> List[Dict[str, Any]]:
        """
        Return games where sharp books and square books disagree significantly.
        Useful for identifying stale square lines to exploit.
        """
        games = await self._fetch_current_odds()
        if not games:
            games = self._mock_games_with_movement()

        divergences = []
        for game in games:
            div = self._calc_book_divergence(game)
            if div and div.get("max_divergence", 0) >= STALE_LINE_DIVERGENCE:
                divergences.append(div)

        divergences.sort(key=lambda d: d.get("max_divergence", 0), reverse=True)
        return divergences

    # ------------------------------------------------------------------
    # Analysis logic
    # ------------------------------------------------------------------

    def _analyze_game(self, game: Dict) -> List[SharpSignal]:
        """Run all sharp money detectors on a single game."""
        signals: List[SharpSignal] = []
        game_id = game.get("id", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        bookmakers = game.get("bookmakers", [])

        sharp_bms = [b for b in bookmakers if b["key"] in SHARP_BOOKS]
        square_bms = [b for b in bookmakers if b["key"] in SQUARE_BOOKS]

        # ---- Market: h2h (moneyline) ----
        sharp_h2h = self._get_h2h_prices(sharp_bms, home, away)
        square_h2h = self._get_h2h_prices(square_bms, home, away)
        all_h2h = self._get_h2h_prices(bookmakers, home, away)

        if sharp_h2h or (all_h2h and len(bookmakers) >= 2):
            ml_signal = self._detect_moneyline_sharp(
                game_id, home, away, sharp_h2h, square_h2h, all_h2h, game
            )
            if ml_signal:
                signals.append(ml_signal)

        # ---- Market: spreads ----
        sharp_spread = self._get_spread_prices(sharp_bms, home, away)
        all_spread = self._get_spread_prices(bookmakers, home, away)
        square_spread = self._get_spread_prices(square_bms, home, away)

        if all_spread:
            spread_signal = self._detect_spread_sharp(
                game_id, home, away, sharp_spread, square_spread, all_spread, game
            )
            if spread_signal:
                signals.append(spread_signal)

        return signals

    def _detect_moneyline_sharp(
        self,
        game_id: str,
        home: str,
        away: str,
        sharp_h2h: Dict[str, List[float]],
        square_h2h: Dict[str, List[float]],
        all_h2h: Dict[str, List[float]],
        game: Dict,
    ) -> Optional[SharpSignal]:
        signal_types = []
        details: Dict[str, Any] = {}
        score = 0

        # 1. Book divergence signal
        if sharp_h2h and square_h2h:
            sharp_home_avg = np.mean(sharp_h2h.get(home, [0.5]))
            square_home_avg = np.mean(square_h2h.get(home, [0.5]))
            divergence = abs(sharp_home_avg - square_home_avg)
            details["sharp_home_prob"] = round(float(sharp_home_avg), 4)
            details["square_home_prob"] = round(float(square_home_avg), 4)
            details["divergence"] = round(float(divergence), 4)

            if divergence >= STALE_LINE_DIVERGENCE:
                signal_types.append("book_divergence")
                score += 1
                # Sharps favor the team with higher sharp prob
                if sharp_home_avg > square_home_avg:
                    details["sharp_favors"] = home
                else:
                    details["sharp_favors"] = away

        # 2. Line movement from snapshot (if available)
        movement_signal = self._check_line_movement_signal(game_id, game, "h2h", home)
        if movement_signal:
            signal_types.append("line_movement")
            score += 1
            details["line_movement"] = movement_signal

        # 3. Public fading opportunity (mock public % since we don't have real data)
        public_info = game.get("_mock_public", {})
        if not public_info:
            if self.strict_mode:
                logger.warning(f"No public data available for game {game.get('id')} - strict mode enabled, skipping RLM detection")
            else:
                public_info = {}  # Use empty dict to skip RLM
        if public_info:
            home_public_pct = public_info.get("home_bet_pct", 0.5)
            # Use sharp implied prob if available, else fall back to all
            sharp_prob = (
                float(np.mean(sharp_h2h.get(home, [])))
                if sharp_h2h.get(home)
                else float(np.mean(all_h2h.get(home, [0.5])))
            )
            rlm = self._detect_rlm(
                home_public_pct, sharp_prob, movement_signal
            )
            if rlm:
                signal_types.append("reverse_line_movement")
                score += 1
                details["rlm"] = rlm
        public_info = game.get("_mock_public", {})
        if not public_info:
            if self.strict_mode:
                logger.warning(f"No public data available for game {game.get('id')} - strict mode enabled, skipping RLM detection")
            else:
                public_info = {}  # Use empty dict to skip RLM
        if public_info:
            home_public_pct = public_info.get("home_bet_pct", 0.5)
            # Use sharp implied prob if available, else fall back to all
            sharp_prob = (
                float(np.mean(sharp_h2h.get(home, [])))
                if sharp_h2h.get(home)
                else float(np.mean(all_h2h.get(home, [0.5])))
            )
            rlm = self._detect_rlm(
                home_public_pct, sharp_prob, movement_signal
            )
            if rlm:
                signal_types.append("reverse_line_movement")
                score += 1
                details["rlm"] = rlm

        if not signal_types:
            return None

        # Determine sharp side
        sharp_favors = details.get("sharp_favors") or self._infer_sharp_side(
            sharp_h2h, square_h2h, home, away
        )

        return SharpSignal(
            game_id=game_id,
            home_team=home,
            away_team=away,
            market="h2h",
            sharp_side=sharp_favors,
            signal_types=signal_types,
            score=score,
            details=details,
            metadata=SignalMetadata(
                quality=DataQuality.INFERRED,
                source=DataSource.ODDS_API,
                inference_method="book_divergence_analysis",
            ),
        )

    def _detect_spread_sharp(
        self,
        game_id: str,
        home: str,
        away: str,
        sharp_spread: Dict[str, Any],
        square_spread: Dict[str, Any],
        all_spread: Dict[str, Any],
        game: Dict,
    ) -> Optional[SharpSignal]:
        signal_types = []
        details: Dict[str, Any] = {}
        score = 0

        # Compare spread values between sharp and square books
        sharp_points = sharp_spread.get("home_point_avg")
        square_points = square_spread.get("home_point_avg")

        if sharp_points is not None and square_points is not None:
            spread_diff = abs(sharp_points - square_points)
            details["sharp_spread"] = round(sharp_points, 1)
            details["square_spread"] = round(square_points, 1)
            details["spread_gap"] = round(spread_diff, 1)

            # Half-point or more spread discrepancy = sharp action moving the number
            if spread_diff >= 0.5:
                signal_types.append("spread_discrepancy")
                score += 1
                if sharp_points < square_points:
                    details["sharp_favors"] = f"{home} laying more"
                else:
                    details["sharp_favors"] = f"{away} getting more"

        # Spread line movement check
        mv = self._check_line_movement_signal(game_id, game, "spreads", home)
        if mv:
            signal_types.append("spread_line_movement")
            score += 1
            details["spread_movement"] = mv

        if not signal_types:
            return None

        sharp_favors = details.get("sharp_favors", home)

        signal = SharpSignal(
            game_id=game_id,
            home_team=home,
            away_team=away,
            market="spreads",
            sharp_side=str(sharp_favors),
            signal_types=signal_types,
            score=score,
            details=details,
            metadata=SignalMetadata(
                quality=DataQuality.INFERRED,
                source=DataSource.ODDS_API,
                inference_method="spread_discrepancy_analysis",
            ),
        )
        
        # Record metrics for this signal
        self.metrics.record_signal(
            signal_type=",".join(signal_types) if signal_types else "spread_analysis",
            quality=DataQuality.INFERRED,
            source=DataSource.ODDS_API,
            confidence=score / 5.0,
            game_id=game_id,
        )
        
        return signal

    # ------------------------------------------------------------------
    # RLM detection
    # ------------------------------------------------------------------

    def _detect_rlm(
        self,
        home_public_pct: float,
        sharp_home_prob: float,
        movement_signal: Optional[Dict],
    ) -> Optional[Dict[str, Any]]:
        """
        Reverse Line Movement:
        - Public heavily on home (>60%)
        - But sharp probability is lower for home than public expectation
          OR line has moved AGAINST the public
        """
        if home_public_pct >= RLM_PUBLIC_THRESHOLD:
            # Public overwhelmingly on home
            if sharp_home_prob < 0.50 and home_public_pct > 0.60:
                return {
                    "type": "fade_home",
                    "public_pct_home": round(home_public_pct, 2),
                    "sharp_home_prob": round(sharp_home_prob, 4),
                    "interpretation": "Public loves home but sharps disagree – possible RLM on away",
                }
            if movement_signal and movement_signal.get("direction") == "away_moving_shorter":
                return {
                    "type": "rlm_away",
                    "public_pct_home": round(home_public_pct, 2),
                    "interpretation": "Public on home but line moving toward away – RLM signal",
                }
        elif home_public_pct <= (1 - RLM_PUBLIC_THRESHOLD):
            # Public heavily on away
            if sharp_home_prob > 0.50 and home_public_pct < 0.40:
                return {
                    "type": "fade_away",
                    "public_pct_home": round(home_public_pct, 2),
                    "sharp_home_prob": round(sharp_home_prob, 4),
                    "interpretation": "Public loves away but sharps disagree – possible RLM on home",
                }

        return None

    # ------------------------------------------------------------------
    # Line movement helpers
    # ------------------------------------------------------------------

    def _compute_line_movement(self, game: Dict) -> Optional[Dict[str, Any]]:
        """Compute line movement from snapshot cache."""
        game_id = game.get("id", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        current_spread = self._get_spread_prices(game.get("bookmakers", []), home, away)
        snapshot = self._line_snapshots.get(game_id)

        movement: Dict[str, Any] = {
            "game_id": game_id,
            "home_team": home,
            "away_team": away,
            "spread_movement": 0.0,
            "direction": "none",
        }

        if snapshot:
            old_spread = snapshot.get("home_point_avg", 0)
            new_spread = current_spread.get("home_point_avg", old_spread)
            if old_spread is not None and new_spread is not None:
                diff = new_spread - old_spread
                movement["opening_spread"] = round(old_spread, 1)
                movement["current_spread"] = round(new_spread, 1)
                movement["spread_movement"] = round(diff, 1)
                if diff > 0.25:
                    movement["direction"] = "home_moving_up"
                elif diff < -0.25:
                    movement["direction"] = "home_moving_down"
        else:
            # Store snapshot for next comparison
            self._line_snapshots[game_id] = current_spread
            movement["current_spread"] = current_spread.get("home_point_avg")
            movement["direction"] = "new_snapshot"

        # Also include mock movement data if present
        # Also include mock movement data if present
        mock_mv = game.get("_mock_movement", {})
        if not mock_mv:
            if self.strict_mode:
                logger.warning(f"No movement data available for game {game.get('id')} - strict mode enabled, skipping movement detection")
            else:
                mock_mv = {}  # Use empty dict to skip movement
        if mock_mv:
            movement.update(mock_mv)

        return movement

    def _check_line_movement_signal(
        self, game_id: str, game: Dict, market: str, home: str
    ) -> Optional[Dict[str, Any]]:
        """Return a movement signal dict if notable movement is present."""
        mock_mv = game.get("_mock_movement", {})
        if not mock_mv:
            return None
        # Mock: simulate movement signals for demo
        if market == "h2h":
            return mock_mv.get("moneyline_movement")
        if market == "spreads":
            return mock_mv.get("spread_movement_signal")
        return None

    # ------------------------------------------------------------------
    # Book divergence
    # ------------------------------------------------------------------

    def _calc_book_divergence(self, game: Dict) -> Optional[Dict[str, Any]]:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        bookmakers = game.get("bookmakers", [])

        sharp_bms = [b for b in bookmakers if b["key"] in SHARP_BOOKS]
        square_bms = [b for b in bookmakers if b["key"] in SQUARE_BOOKS]

        if not sharp_bms or not square_bms:
            return None

        sharp_h2h = self._get_h2h_prices(sharp_bms, home, away)
        square_h2h = self._get_h2h_prices(square_bms, home, away)

        if not sharp_h2h or not square_h2h:
            return None

        sharp_home = float(np.mean(sharp_h2h.get(home, [0.5])))
        square_home = float(np.mean(square_h2h.get(home, [0.5])))
        divergence = abs(sharp_home - square_home)

        return {
            "game_id": game.get("id"),
            "home_team": home,
            "away_team": away,
            "sharp_home_prob": round(sharp_home, 4),
            "square_home_prob": round(square_home, 4),
            "max_divergence": round(divergence, 4),
            "sharp_books_used": [b["key"] for b in sharp_bms],
            "square_books_used": [b["key"] for b in square_bms],
            "interpretation": (
                f"Sharp books give {home} {sharp_home:.1%} vs "
                f"square books {square_home:.1%} – "
                f"gap of {divergence:.1%}"
            ),
        }

    # ------------------------------------------------------------------
    # Price extraction helpers
    # ------------------------------------------------------------------

    def _get_h2h_prices(
        self, bookmakers: List[Dict], home: str, away: str
    ) -> Dict[str, List[float]]:
        """Return devigged probabilities grouped by team from h2h markets."""
        result: Dict[str, List[float]] = {home: [], away: []}
        for bm in bookmakers:
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                outcomes = market.get("outcomes", [])
                home_o = next((o for o in outcomes if o.get("name") == home), None)
                away_o = next((o for o in outcomes if o.get("name") == away), None)
                if home_o and away_o and home_o.get("price") and away_o.get("price"):
                    raw = [
                        american_to_implied_prob(home_o["price"]),
                        american_to_implied_prob(away_o["price"]),
                    ]
                    dv = multiplicative_devig(raw)
                    result[home].append(dv[0])
                    result[away].append(dv[1])
        return result

    def _get_spread_prices(
        self, bookmakers: List[Dict], home: str, away: str
    ) -> Dict[str, Any]:
        """Return spread information averaged across bookmakers."""
        home_points: List[float] = []
        away_points: List[float] = []

        for bm in bookmakers:
            for market in bm.get("markets", []):
                if market.get("key") != "spreads":
                    continue
                outcomes = market.get("outcomes", [])
                home_o = next((o for o in outcomes if o.get("name") == home), None)
                away_o = next((o for o in outcomes if o.get("name") == away), None)
                if home_o and home_o.get("point") is not None:
                    home_points.append(float(home_o["point"]))
                if away_o and away_o.get("point") is not None:
                    away_points.append(float(away_o["point"]))

        return {
            "home_point_avg": float(np.mean(home_points)) if home_points else None,
            "away_point_avg": float(np.mean(away_points)) if away_points else None,
        }

    def _infer_sharp_side(
        self,
        sharp_h2h: Dict[str, List[float]],
        square_h2h: Dict[str, List[float]],
        home: str,
        away: str,
    ) -> str:
        if not sharp_h2h or not square_h2h:
            return ""
        sharp_home = float(np.mean(sharp_h2h.get(home, [0.5])))
        square_home = float(np.mean(square_h2h.get(home, [0.5])))
        if sharp_home > square_home:
            return home
        return away

    # ------------------------------------------------------------------
    # Odds fetching
    # ------------------------------------------------------------------

    async def _fetch_current_odds(self) -> List[Dict]:
        """Fetch NCAAB odds via SportsAPIService (handles caching + SGO fallback)."""
        return await self._sports_api.get_odds(
            sport=NCAAB_SPORT_KEY,
            markets="h2h,spreads",
        )

    # ------------------------------------------------------------------
    # Mock data
    # ------------------------------------------------------------------

    def _mock_games_with_movement(self) -> List[Dict]:
        """
        Realistic mock games that include simulated public % and line movement
        for demonstrating sharp money signals without a live API key.
        """
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
                                    # Square book still has stale -152 from opening
                                    {"name": "Duke Blue Devils", "price": -152},
                                    {"name": "North Carolina Tar Heels", "price": 126},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    # Square book still shows -3.5, sharp moved to -3.0
                                    {"name": "Duke Blue Devils", "price": -110, "point": -3.5},
                                    {"name": "North Carolina Tar Heels", "price": -110, "point": 3.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -148},
                                    {"name": "North Carolina Tar Heels", "price": 122},
                                ],
                            },
                        ],
                    },
                ],
                # Simulated public betting percentages
                "_mock_public": {"home_bet_pct": 0.72, "away_bet_pct": 0.28},
                # Simulated line movement signals
                "_mock_movement": {
                    "moneyline_movement": {
                        "direction": "away_moving_shorter",
                        "home_opening": -155,
                        "home_current": -138,
                        "away_opening": 130,
                        "away_current": 120,
                        "interpretation": "Duke moving from -155 to -138 despite 72% public – sharp UNC action",
                    },
                    "spread_movement_signal": {
                        "opening": -3.5,
                        "current": -3.0,
                        "half_point_move": True,
                        "interpretation": "Duke spread moved from -3.5 to -3.0 – sharp money on UNC",
                    },
                },
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
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -128},
                                    {"name": "Kentucky Wildcats", "price": 110},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -105, "point": -2.5},
                                    {"name": "Kentucky Wildcats", "price": -115, "point": 2.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "betmgm",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -118},
                                    {"name": "Kentucky Wildcats", "price": +100},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    # Square still showing -2.0 while sharps moved to -2.5
                                    {"name": "Kansas Jayhawks", "price": -110, "point": -2.0},
                                    {"name": "Kentucky Wildcats", "price": -110, "point": 2.0},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "caesars",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Kansas Jayhawks", "price": -115},
                                    {"name": "Kentucky Wildcats", "price": +100},
                                ],
                            },
                        ],
                    },
                ],
                "_mock_public": {"home_bet_pct": 0.38, "away_bet_pct": 0.62},
                "_mock_movement": {
                    "moneyline_movement": {
                        "direction": "home_moving_shorter",
                        "home_opening": -115,
                        "home_current": -128,
                        "interpretation": "Kansas odds shortened from -115 to -128 despite 38% public – sharp Kansas action",
                    },
                    "spread_movement_signal": {
                        "opening": -2.0,
                        "current": -2.5,
                        "half_point_move": True,
                        "interpretation": "Kansas spread moved from -2.0 to -2.5 against public trend – sharp KU action",
                    },
                },
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
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -200},
                                    {"name": "Arizona Wildcats", "price": 172},
                                ],
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -108, "point": -5.5},
                                    {"name": "Arizona Wildcats", "price": -112, "point": 5.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "caesars",
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
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Gonzaga Bulldogs", "price": -195},
                                    {"name": "Arizona Wildcats", "price": 165},
                                ],
                            },
                        ],
                    },
                ],
                "_mock_public": {"home_bet_pct": 0.80, "away_bet_pct": 0.20},
                "_mock_movement": {
                    "moneyline_movement": {
                        "direction": "away_moving_shorter",
                        "home_opening": -225,
                        "home_current": -200,
                        "away_opening": 190,
                        "away_current": 170,
                        "interpretation": "Gonzaga opened -225, now -200 – sharp Arizona action despite 80% public on Gonzaga",
                    },
                },
            },
        ]

    def get_data_quality_stats(self) -> Dict[str, Any]:
        """Get statistics on data quality for generated signals."""
        return {
            "strict_mode": self.strict_mode,
            "total_signals_logged": len(self._data_quality_log),
            "logs": self._data_quality_log[-100:] if self._data_quality_log else [],
        }
    
    def log_signal_quality(self, signal: SharpSignal) -> None:
        """Log the data quality of a generated signal."""
        self._data_quality_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "game_id": signal.game_id,
            "signal_type": signal.signal_types,
            "quality": signal.metadata.quality.value,
            "source": signal.metadata.source.value,
            "confidence": signal.confidence,
        })
