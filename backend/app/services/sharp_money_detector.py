"""
Sharp Money Detection Service  (DEPRECATED)

This module is preserved for backward compatibility.  New code should import
from ``app.services.line_movement_analyzer`` instead, which replaces
signal-detection heuristics (RLM, Steam, Freeze) with practical
line-movement and multi-book consensus analysis.

Re-exported symbols:
    CLVRecord, SharpMoneyDetector (thin wrapper around LineMovementAnalyzer)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from loguru import logger

# Re-export the new canonical types so existing ``from sharp_money_detector
# import CLVRecord`` still works.
from app.services.line_movement_analyzer import (  # noqa: F401
    CLVRecord as _CLVRecord,
    LineMovementAnalyzer,
)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class MarketSnapshot:
    """Point-in-time snapshot of a betting market"""
    timestamp: float
    book: str
    game_id: str
    market: str          # 'spread', 'total', 'moneyline'
    side: str            # team name or 'over'/'under'
    odds: float          # American odds
    line: float          # point spread or total number
    ticket_pct: float = 0.0   # % of public tickets on this side
    money_pct: float = 0.0    # % of public dollars on this side


@dataclass
class SharpSignal:
    """Detected sharp money signal"""
    signal_type: str        # 'RLM', 'STEAM', 'FREEZE', 'HEAD_FAKE'
    game_id: str
    market: str
    sharp_side: str         # side identified as having sharp action
    confidence: float       # 0.0 - 1.0
    details: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.80:
            return "VERY HIGH"
        elif self.confidence >= 0.65:
            return "HIGH"
        elif self.confidence >= 0.50:
            return "MEDIUM"
        else:
            return "LOW"


# Re-export CLVRecord from the new module for backward compatibility
CLVRecord = _CLVRecord


# ---------------------------------------------------------------------------
# Sharp Money Detector
# ---------------------------------------------------------------------------

class SharpMoneyDetector:
    """
    DEPRECATED — use ``LineMovementAnalyzer`` from
    ``app.services.line_movement_analyzer`` for new code.

    This class is preserved for backward compatibility.  Key public methods
    now delegate to ``LineMovementAnalyzer``.
    """

    # Minimum public ticket % to be considered "one-sided"
    RLM_TICKET_THRESHOLD = 0.65
    # Minimum ticket/money gap to validate sharp signal
    RLM_GAP_THRESHOLD = 0.10
    # RLM gap for high confidence (≥20%)
    RLM_HIGH_CONFIDENCE_GAP = 0.20

    # Steam: line must move ≥ this amount within STEAM_WINDOW_SECONDS
    STEAM_LINE_MOVE_SPREAD = 0.5    # half-point on spread
    STEAM_LINE_MOVE_TOTAL = 1.0     # full point on totals
    STEAM_ODDS_MOVE = 8             # 8 cents on moneyline
    STEAM_WINDOW_SECONDS = 60       # within 60 seconds
    STEAM_MIN_BOOKS = 3             # across at least 3 books

    # Freeze: this many % of tickets with no line movement
    FREEZE_TICKET_THRESHOLD = 0.80
    FREEZE_MAX_LINE_MOVE = 0.25     # line has moved less than this amount despite heavy action

    # Head fake: reversed within this many minutes
    HEAD_FAKE_REVERSAL_MINUTES = 15
    HEAD_FAKE_VOLATILITY_MULTIPLIER = 2.0  # ≥ 2σ move

    def __init__(self):
        self._delegate = LineMovementAnalyzer()
        # Legacy stores kept for any remaining callers
        self._snapshots: Dict[str, List[MarketSnapshot]] = {}
        self._volatility_history: Dict[str, List[float]] = {}
        self._clv_records: List[CLVRecord] = []

    # ------------------------------------------------------------------
    # Public Interface
    # ------------------------------------------------------------------

    def process_snapshot(self, snapshot: MarketSnapshot) -> List[SharpSignal]:
        """
        Ingest a new market snapshot and return any detected sharp signals.

        Args:
            snapshot: Current market state from any sportsbook

        Returns:
            List of SharpSignal objects (may be empty)
        """
        key = f"{snapshot.game_id}:{snapshot.market}:{snapshot.side}"
        if key not in self._snapshots:
            self._snapshots[key] = []

        prior = self._snapshots[key][-1] if self._snapshots[key] else None
        self._snapshots[key].append(snapshot)

        signals = []

        if prior is not None:
            # Check for steam on this single book (cross-book steam needs multi-snapshot)
            line_move = snapshot.line - prior.line
            if line_move != 0:
                self._record_volatility(key, abs(line_move))

        # RLM check requires ticket/money data
        if snapshot.ticket_pct > 0 and snapshot.money_pct > 0 and prior is not None:
            rlm = self._check_rlm(prior, snapshot)
            if rlm:
                signals.append(rlm)

        # Freeze check
        if snapshot.ticket_pct >= self.FREEZE_TICKET_THRESHOLD:
            freeze = self._check_freeze(key, snapshot)
            if freeze:
                signals.append(freeze)

        return signals

    def detect_steam(
        self,
        snapshots_by_book: Dict[str, MarketSnapshot],
        prior_snapshots_by_book: Dict[str, MarketSnapshot]
    ) -> Optional[SharpSignal]:
        """
        Detect steam moves across multiple books simultaneously.

        Args:
            snapshots_by_book: Latest snapshot per book {book_name: snapshot}
            prior_snapshots_by_book: Previous snapshot per book

        Returns:
            SharpSignal if steam detected, else None
        """
        if len(snapshots_by_book) < self.STEAM_MIN_BOOKS:
            return None

        moves = []
        direction = None
        game_id = None
        market = None
        side = None

        for book, snap in snapshots_by_book.items():
            prior = prior_snapshots_by_book.get(book)
            if prior is None:
                continue

            game_id = snap.game_id
            market = snap.market
            side = snap.side
            elapsed = snap.timestamp - prior.timestamp
            if elapsed > self.STEAM_WINDOW_SECONDS:
                continue

            # Determine threshold by market type
            if market == 'spread':
                threshold = self.STEAM_LINE_MOVE_SPREAD
            elif market == 'total':
                threshold = self.STEAM_LINE_MOVE_TOTAL
            else:
                threshold = self.STEAM_ODDS_MOVE  # moneyline

            move = snap.line - prior.line
            if abs(move) >= threshold:
                d = 'UP' if move > 0 else 'DOWN'
                if direction is None:
                    direction = d
                if d == direction:
                    moves.append({'book': book, 'move': move, 'elapsed': elapsed})

        if len(moves) >= self.STEAM_MIN_BOOKS:
            confidence = min(0.95, 0.50 + len(moves) * 0.10)
            signal = SharpSignal(
                signal_type='STEAM',
                game_id=game_id,
                market=market,
                sharp_side=side,
                confidence=confidence,
                details={
                    'books_moved': [m['book'] for m in moves],
                    'avg_move': np.mean([abs(m['move']) for m in moves]),
                    'direction': direction,
                    'max_elapsed_s': max(m['elapsed'] for m in moves)
                }
            )
            logger.info(
                f"STEAM detected: {game_id} {market} {side} "
                f"({len(moves)} books, confidence={confidence:.2f})"
            )
            return signal

        return None

    def filter_head_fake(self, signal: SharpSignal, key: str) -> bool:
        """
        Returns True if the signal is likely a head fake and should be discarded.

        Args:
            signal: The SharpSignal to evaluate
            key: game_id:market:side key for volatility lookup

        Returns:
            True = discard (head fake), False = genuine signal
        """
        snaps = self._snapshots.get(key, [])
        if len(snaps) < 4:
            return False  # Not enough history to detect reversal

        # Check if line reversed within HEAD_FAKE_REVERSAL_MINUTES
        cutoff = time.time() - self.HEAD_FAKE_REVERSAL_MINUTES * 60
        recent = [s for s in snaps if s.timestamp >= cutoff]
        if len(recent) < 2:
            return False

        first_line = recent[0].line
        last_line = recent[-1].line
        max_line = max(s.line for s in recent)
        min_line = min(s.line for s in recent)

        # If line spiked and came back, flag as potential head fake
        spike_magnitude = max_line - min_line
        net_change = abs(last_line - first_line)

        if net_change == 0 and spike_magnitude > 0:
            # Line returned to start — classic reversal pattern
            hist_vol = self._get_historical_volatility(key)
            if hist_vol > 0 and spike_magnitude >= self.HEAD_FAKE_VOLATILITY_MULTIPLIER * hist_vol:
                logger.warning(
                    f"HEAD FAKE filter triggered: {key} spike={spike_magnitude:.2f} "
                    f"hist_vol={hist_vol:.2f}"
                )
                return True

        return False

    def record_clv(
        self,
        game_id: str,
        market: str,
        side: str,
        bet_odds: float,
        closing_odds: float,
        game_start: float,
        bet_timestamp: Optional[float] = None
    ) -> CLVRecord:
        """DEPRECATED — delegates to LineMovementAnalyzer.record_clv."""
        return self._delegate.record_clv(
            game_id=game_id,
            market=market,
            side=side,
            bet_odds=bet_odds,
            closing_odds=closing_odds,
            game_start=game_start,
            bet_timestamp=bet_timestamp,
        )

    def clv_summary(self) -> Dict:
        """DEPRECATED — delegates to LineMovementAnalyzer.clv_summary."""
        return self._delegate.clv_summary()

    # ------------------------------------------------------------------
    # Standalone Analysis (for use without streaming)
    # ------------------------------------------------------------------

    @staticmethod
    def analyze_game(
        game_id: str,
        market: str,
        home_team: str,
        away_team: str,
        open_line: float,
        current_line: float,
        home_ticket_pct: float,
        home_money_pct: float,
        pinnacle_home_odds: float,
        retail_home_odds: float,
    ) -> Dict:
        """
        Static analysis for a single game given snapshot data.

        DEPRECATED — delegates to ``LineMovementAnalyzer.analyze_game``.
        """
        return LineMovementAnalyzer.analyze_game(
            game_id=game_id,
            market=market,
            home_team=home_team,
            away_team=away_team,
            open_line=open_line,
            current_line=current_line,
            pinnacle_home_odds=pinnacle_home_odds,
            retail_home_odds=retail_home_odds,
            home_ticket_pct=home_ticket_pct,
            home_money_pct=home_money_pct,
        )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _check_rlm(
        self, prior: MarketSnapshot, current: MarketSnapshot
    ) -> Optional[SharpSignal]:
        """Detect Reverse Line Movement between two snapshots"""
        # Determine which side is the public side
        public_side_pct = current.ticket_pct
        money_side_pct = current.money_pct

        home_is_public_fave = public_side_pct >= self.RLM_TICKET_THRESHOLD

        if not home_is_public_fave:
            return None

        line_moved_against_public = current.line < prior.line
        if not line_moved_against_public:
            return None

        ticket_gap = public_side_pct - money_side_pct
        if ticket_gap < self.RLM_GAP_THRESHOLD:
            return None

        # Confidence scales with gap size
        if ticket_gap >= self.RLM_HIGH_CONFIDENCE_GAP:
            confidence = min(0.90, 0.70 + (ticket_gap - 0.20) * 1.0)
        else:
            confidence = 0.50 + (ticket_gap - 0.10) * 2.0

        signal = SharpSignal(
            signal_type='RLM',
            game_id=current.game_id,
            market=current.market,
            sharp_side=f"AGAINST_{current.side}",
            confidence=round(confidence, 3),
            details={
                'public_ticket_pct': round(public_side_pct, 3),
                'money_pct': round(money_side_pct, 3),
                'ticket_money_gap': round(ticket_gap, 3),
                'line_moved_from': prior.line,
                'line_moved_to': current.line,
                'line_change': round(current.line - prior.line, 2)
            }
        )
        logger.info(
            f"RLM detected: {current.game_id} {current.market} "
            f"tickets={public_side_pct:.0%} money={money_side_pct:.0%} "
            f"confidence={confidence:.2f}"
        )
        return signal

    def _check_freeze(self, key: str, snapshot: MarketSnapshot) -> Optional[SharpSignal]:
        """Detect line freeze despite heavy public action"""
        snaps = self._snapshots.get(key, [])
        if len(snaps) < 2:
            return None

        earliest = snaps[0]
        line_change = abs(snapshot.line - earliest.line)

        if line_change <= self.FREEZE_MAX_LINE_MOVE:
            # Line frozen despite heavy public support
            signal = SharpSignal(
                signal_type='FREEZE',
                game_id=snapshot.game_id,
                market=snapshot.market,
                sharp_side=f"AGAINST_{snapshot.side}",
                confidence=0.70,
                details={
                    'public_ticket_pct': round(snapshot.ticket_pct, 3),
                    'open_line': earliest.line,
                    'current_line': snapshot.line,
                    'line_change': round(line_change, 2)
                }
            )
            logger.info(
                f"LINE FREEZE detected: {snapshot.game_id} {snapshot.market} "
                f"public={snapshot.ticket_pct:.0%} freeze"
            )
            return signal

        return None

    def _record_volatility(self, key: str, move: float):
        if key not in self._volatility_history:
            self._volatility_history[key] = []
        self._volatility_history[key].append(move)
        # Keep last 50 observations
        self._volatility_history[key] = self._volatility_history[key][-50:]

    def _get_historical_volatility(self, key: str) -> float:
        hist = self._volatility_history.get(key, [])
        if len(hist) < 3:
            return 0.5  # default half-point volatility assumption
        return float(np.std(hist))

    @staticmethod
    def _american_to_implied(american_odds: float) -> float:
        return LineMovementAnalyzer._american_to_implied(american_odds)

    @staticmethod
    def _american_to_implied_static(american_odds: float) -> float:
        return LineMovementAnalyzer._american_to_implied(american_odds)

    @staticmethod
    def devig_odds(odds_side1: float, odds_side2: float) -> Tuple[float, float]:
        """DEPRECATED — delegates to LineMovementAnalyzer.devig_odds."""
        return LineMovementAnalyzer.devig_odds(odds_side1, odds_side2)
