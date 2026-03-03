"""
Line Movement Analyzer — Predictive Analysis via Odds Data

Replaces signal-detection approaches (RLM, Steam, Freeze) that require
expensive ticket/money-percentage subscriptions with practical line-movement
features derived entirely from publicly available multi-book odds data
(The Odds API, ESPN, etc.).

Core capabilities:
    1. **Market consensus probability** — weighted devigged average across books
    2. **Line movement features** — direction, magnitude, velocity as ML inputs
    3. **CLV tracking** — closing-line-value history for model calibration
    4. **Devigging** — remove bookmaker vig from two-sided markets

Theory:
    Line movement encodes the aggregate opinion of the market.  A line that
    moves from -3 to -4.5 tells us the same information as "sharp money is
    on the favorite" — without needing proprietary ticket-split data.

    Market consensus across N books (weighted by sharpness) gives a more
    robust true probability than any single book's number:
        p_consensus = Σ w_i · devig(book_i) / Σ w_i
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class LineSnapshot:
    """Point-in-time odds snapshot from a single book."""
    timestamp: float
    book: str
    game_id: str
    market: str          # 'spread', 'total', 'moneyline'
    side: str            # team name or 'over'/'under'
    odds: float          # American odds
    line: float          # point spread or total number


@dataclass
class CLVRecord:
    """Closing Line Value tracking record."""
    game_id: str
    market: str
    side: str
    bet_odds: float          # Odds at time of bet
    closing_odds: float      # Pinnacle closing line odds
    clv_pct: float           # CLV in percentage points
    implied_at_bet: float    # Implied probability at bet time
    implied_closing: float   # Implied probability at close
    bet_timestamp: float
    game_start: float


@dataclass
class LineMovementFeatures:
    """Extracted line-movement features for a single game/market."""
    game_id: str
    market: str
    open_line: float
    current_line: float
    line_move: float              # current - open (signed)
    line_move_abs: float          # |current - open|
    move_direction: str           # 'TOWARD_HOME', 'TOWARD_AWAY', 'STABLE'
    consensus_true_prob: float    # Weighted market-consensus probability
    consensus_edge: float         # consensus_true_prob - retail implied
    books_agreeing: int           # How many books moved in same direction
    total_books: int
    confidence: float             # 0.0–1.0 derived from consensus agreement


# ---------------------------------------------------------------------------
# Book-Sharpness Weights
# ---------------------------------------------------------------------------

# Pinnacle and Circa are market-makers; their lines carry more signal.
# Retail books follow market-makers, so their lines carry less independent info.
BOOK_WEIGHTS: Dict[str, float] = {
    "pinnacle": 1.00,
    "circa": 0.90,
    "bet365": 0.50,
    "draftkings": 0.45,
    "fanduel": 0.45,
    "betmgm": 0.40,
    "caesars": 0.40,
    "bovada": 0.35,
}
DEFAULT_BOOK_WEIGHT: float = 0.30


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class LineMovementAnalyzer:
    """
    Analyzes line movement and multi-book consensus to derive predictive
    features and true probabilities from publicly available odds data.

    Usage:
        analyzer = LineMovementAnalyzer()
        result = LineMovementAnalyzer.analyze_game(
            game_id="cbb_123", market="spread",
            home_team="Home", away_team="Away",
            open_line=-3.5, current_line=-4.5,
            pinnacle_home_odds=-110, retail_home_odds=-105,
        )
    """

    def __init__(self) -> None:
        self._clv_records: List[CLVRecord] = []

    # ------------------------------------------------------------------
    # Public: Static Game Analysis
    # ------------------------------------------------------------------

    @staticmethod
    def analyze_game(
        game_id: str,
        market: str,
        home_team: str,
        away_team: str,
        open_line: float,
        current_line: float,
        pinnacle_home_odds: float,
        retail_home_odds: float,
        additional_book_odds: Optional[Dict[str, float]] = None,
        home_ticket_pct: float = 0.0,
        home_money_pct: float = 0.0,
    ) -> Dict:
        """
        Static analysis for a single game using line movement and
        multi-book consensus instead of ticket/money signal detection.

        Returns a dict compatible with the previous sharp-money interface
        so downstream code (run_ncaab_analysis, etc.) needs minimal changes.

        Args:
            game_id:               Game identifier
            market:                Market type ('spread', 'total', 'moneyline')
            home_team:             Home team name
            away_team:             Away team name
            open_line:             Opening point spread / total
            current_line:          Current point spread / total
            pinnacle_home_odds:    Pinnacle American odds for home side
            retail_home_odds:      Retail book American odds for home side
            additional_book_odds:  Optional {book_name: american_odds} for
                                   multi-book consensus (e.g. {'draftkings': -108})
            home_ticket_pct:       Accepted but not required (ignored)
            home_money_pct:        Accepted but not required (ignored)

        Returns:
            Dict with keys: game_id, market, home_team, away_team, open_line,
            current_line, line_move, line_move_direction, consensus_prob,
            ev_edge, ev_edge_pct, is_positive_ev, confidence, sharp_side,
            sharp_signals (list — may contain 'LINE_MOVE' for backward compat).
        """
        # --- Line movement analysis ---
        line_move = current_line - open_line
        abs_move = abs(line_move)

        # Determine which team the line moved toward
        if abs_move < 0.5:
            move_direction = "STABLE"
            favored_side = None
        elif line_move < 0:
            # Spread decreased → home team getting fewer points → market
            # is giving away side more credit (or home got stronger)
            move_direction = "TOWARD_AWAY"
            favored_side = away_team
        else:
            move_direction = "TOWARD_HOME"
            favored_side = home_team

        # --- Multi-book consensus probability ---
        consensus_prob = LineMovementAnalyzer._compute_consensus(
            pinnacle_home_odds, additional_book_odds
        )

        # --- Pinnacle-only devigged probability (single-book fallback) ---
        pinnacle_home_implied = LineMovementAnalyzer._american_to_implied(
            pinnacle_home_odds
        )
        total_vig_estimate = 0.025  # Pinnacle typical ~2.5% total overround
        devigged_home = pinnacle_home_implied / (1.0 + total_vig_estimate)

        # Use consensus when we have multi-book data, else single-book devig
        true_prob = consensus_prob if consensus_prob > 0 else devigged_home

        retail_implied = LineMovementAnalyzer._american_to_implied(
            retail_home_odds
        )
        edge = true_prob - retail_implied

        # --- Confidence from line movement + consensus agreement ---
        confidence = LineMovementAnalyzer._movement_confidence(
            abs_move, additional_book_odds
        )

        # --- Backward-compatible signal list ---
        signals: List[str] = []
        if abs_move >= 1.0:
            signals.append("LINE_MOVE")
        if consensus_prob > 0 and additional_book_odds and len(additional_book_odds) >= 2:
            signals.append("CONSENSUS")

        return {
            "game_id": game_id,
            "market": market,
            "home_team": home_team,
            "away_team": away_team,
            "open_line": open_line,
            "current_line": current_line,
            "home_ticket_pct": home_ticket_pct,
            "home_money_pct": home_money_pct,
            "line_move": round(line_move, 2),
            "line_move_direction": move_direction,
            "consensus_prob": round(true_prob, 4),
            "sharp_signals": signals,
            "sharp_side": favored_side,
            "signal_confidence": round(confidence, 3),
            "pinnacle_implied": round(pinnacle_home_implied, 4),
            "retail_implied": round(retail_implied, 4),
            "ev_edge": round(edge, 4),
            "ev_edge_pct": round(edge * 100, 2),
            "is_positive_ev": edge > 0.03,
        }

    # ------------------------------------------------------------------
    # Public: Multi-book Consensus Probability
    # ------------------------------------------------------------------

    @staticmethod
    def compute_market_consensus(
        book_odds: Dict[str, float],
    ) -> float:
        """
        Compute a sharpness-weighted market consensus true probability
        from multiple books' American odds for one side.

        Each book's implied probability is devigged (assuming a symmetric
        market with ~2.5% total overround) and then weighted by the book's
        sharpness score.

        Args:
            book_odds: {book_name: american_odds} for one side

        Returns:
            Weighted-average true probability (0–1)
        """
        if not book_odds:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        vig = 0.025

        for book, odds in book_odds.items():
            implied = LineMovementAnalyzer._american_to_implied(odds)
            devigged = implied / (1.0 + vig)
            weight = BOOK_WEIGHTS.get(book.lower(), DEFAULT_BOOK_WEIGHT)
            weighted_sum += devigged * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    # ------------------------------------------------------------------
    # Public: Extract Line Features (for ML pipeline)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_line_features(
        game_id: str,
        market: str,
        open_line: float,
        current_line: float,
        book_odds: Optional[Dict[str, float]] = None,
        retail_implied: float = 0.0,
    ) -> LineMovementFeatures:
        """
        Extract structured line-movement features suitable for ML models.

        Args:
            game_id:        Game identifier
            market:         Market type
            open_line:      Opening line
            current_line:   Current line
            book_odds:      Optional multi-book odds for consensus
            retail_implied: Retail book implied probability

        Returns:
            LineMovementFeatures dataclass
        """
        line_move = current_line - open_line
        abs_move = abs(line_move)

        if abs_move < 0.5:
            direction = "STABLE"
        elif line_move < 0:
            direction = "TOWARD_AWAY"
        else:
            direction = "TOWARD_HOME"

        consensus = 0.0
        books_agreeing = 0
        total_books = 0
        if book_odds:
            consensus = LineMovementAnalyzer.compute_market_consensus(book_odds)
            total_books = len(book_odds)
            # Count books where devigged implies same direction as line move
            for _book, odds in book_odds.items():
                imp = LineMovementAnalyzer._american_to_implied(odds)
                if (line_move < 0 and imp < 0.50) or (line_move > 0 and imp > 0.50):
                    books_agreeing += 1

        edge = consensus - retail_implied if consensus > 0 and retail_implied > 0 else 0.0

        confidence = LineMovementAnalyzer._movement_confidence(
            abs_move, book_odds
        )

        return LineMovementFeatures(
            game_id=game_id,
            market=market,
            open_line=open_line,
            current_line=current_line,
            line_move=round(line_move, 2),
            line_move_abs=round(abs_move, 2),
            move_direction=direction,
            consensus_true_prob=round(consensus, 4),
            consensus_edge=round(edge, 4),
            books_agreeing=books_agreeing,
            total_books=total_books,
            confidence=round(confidence, 3),
        )

    # ------------------------------------------------------------------
    # Public: CLV Tracking (preserved from SharpMoneyDetector)
    # ------------------------------------------------------------------

    def record_clv(
        self,
        game_id: str,
        market: str,
        side: str,
        bet_odds: float,
        closing_odds: float,
        game_start: float,
        bet_timestamp: Optional[float] = None,
    ) -> CLVRecord:
        """
        Record and return CLV for a placed bet.

        CLV > 0 means the bet was placed at better-than-closing odds.
        Measured in implied-probability percentage points.
        """
        bet_ts = bet_timestamp or time.time()
        implied_bet = self._american_to_implied(bet_odds)
        implied_close = self._american_to_implied(closing_odds)
        clv_pct = (implied_close - implied_bet) * 100

        record = CLVRecord(
            game_id=game_id,
            market=market,
            side=side,
            bet_odds=bet_odds,
            closing_odds=closing_odds,
            clv_pct=clv_pct,
            implied_at_bet=implied_bet,
            implied_closing=implied_close,
            bet_timestamp=bet_ts,
            game_start=game_start,
        )
        self._clv_records.append(record)

        logger.info(
            f"CLV recorded: {game_id} {market} {side} "
            f"bet={bet_odds:+.0f} close={closing_odds:+.0f} CLV={clv_pct:+.2f}%"
        )
        return record

    def clv_summary(self) -> Dict:
        """Return summary statistics of all CLV records."""
        if not self._clv_records:
            return {"count": 0, "avg_clv": 0.0, "pct_positive": 0.0}

        clvs = [r.clv_pct for r in self._clv_records]
        return {
            "count": len(clvs),
            "avg_clv": round(np.mean(clvs), 3),
            "median_clv": round(float(np.median(clvs)), 3),
            "std_clv": round(float(np.std(clvs)), 3),
            "pct_positive": round(sum(1 for c in clvs if c > 0) / len(clvs), 3),
            "cumulative_clv": round(sum(clvs), 3),
        }

    # ------------------------------------------------------------------
    # Public: Devigging (preserved from SharpMoneyDetector)
    # ------------------------------------------------------------------

    @staticmethod
    def devig_odds(odds_side1: float, odds_side2: float) -> Tuple[float, float]:
        """
        Remove the bookmaker vig from a two-sided market.

        Args:
            odds_side1: American odds for side 1
            odds_side2: American odds for side 2

        Returns:
            Tuple of (true_prob_side1, true_prob_side2) summing to 1.0
        """
        imp1 = LineMovementAnalyzer._american_to_implied(odds_side1)
        imp2 = LineMovementAnalyzer._american_to_implied(odds_side2)
        total = imp1 + imp2
        return imp1 / total, imp2 / total

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _american_to_implied(american_odds: float) -> float:
        """Convert American odds to implied probability."""
        if american_odds > 0:
            return 100.0 / (american_odds + 100.0)
        else:
            return abs(american_odds) / (abs(american_odds) + 100.0)

    # Keep this alias so callers that used the old name still work.
    _american_to_implied_static = _american_to_implied

    @staticmethod
    def _compute_consensus(
        pinnacle_odds: float,
        additional_book_odds: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute weighted consensus from Pinnacle + any extra books."""
        book_odds: Dict[str, float] = {"pinnacle": pinnacle_odds}
        if additional_book_odds:
            book_odds.update(additional_book_odds)

        if len(book_odds) < 2:
            # Only Pinnacle — fall back to single-book devig
            return 0.0

        return LineMovementAnalyzer.compute_market_consensus(book_odds)

    @staticmethod
    def _movement_confidence(
        abs_move: float,
        additional_book_odds: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Derive a 0–1 confidence score from line movement magnitude and
        multi-book consensus availability.

        - abs_move contributes up to 0.50 (capped at 3-point move)
        - Multi-book consensus contributes up to 0.40
        - Baseline = 0.10
        """
        # Line-movement component (bigger move → more signal)
        move_score = min(0.50, abs_move / 3.0 * 0.50)

        # Consensus component (more books → more reliable)
        n_books = len(additional_book_odds) if additional_book_odds else 0
        consensus_score = min(0.40, n_books * 0.10)

        return round(min(0.95, 0.10 + move_score + consensus_score), 3)
