"""
Sharp Money Detection Service

Identifies professional syndicate activity through market signal analysis:
- Reverse Line Movement (RLM)
- Steam Moves (coordinated multi-book shifts)
- Line Freeze detection
- Head Fake / Market Manipulation filtering
- Closing Line Value (CLV) tracking
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from loguru import logger


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


@dataclass
class CLVRecord:
    """Closing Line Value tracking record"""
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


# ---------------------------------------------------------------------------
# Sharp Money Detector
# ---------------------------------------------------------------------------

class SharpMoneyDetector:
    """
    Analyzes market data streams to detect professional betting activity.

    Based on three primary signals:
    1. Reverse Line Movement (RLM) — line moves against public tickets
    2. Steam Moves — sudden coordinated multi-book shifts
    3. Line Freeze — line static despite heavy public support on one side
    4. Head Fake Filter — identifies and discards manipulation attempts
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
        # Stores historical snapshots per game+market key
        self._snapshots: Dict[str, List[MarketSnapshot]] = {}
        # Tracks historical volatility per game+market
        self._volatility_history: Dict[str, List[float]] = {}
        # CLV records
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
        """
        Record and return CLV for a placed bet.

        CLV > 0 means the bet was placed at better-than-closing odds (positive result).
        CLV is measured in implied probability percentage points.

        Args:
            game_id: Game identifier
            market: Market type
            side: Side bet was placed on
            bet_odds: American odds at time of bet placement
            closing_odds: Pinnacle closing American odds (ground truth)
            game_start: Unix timestamp of game start
            bet_timestamp: When the bet was placed (defaults to now)

        Returns:
            CLVRecord with calculated CLV
        """
        bet_ts = bet_timestamp or time.time()
        implied_bet = self._american_to_implied(bet_odds)
        implied_close = self._american_to_implied(closing_odds)
        clv_pct = (implied_close - implied_bet) * 100  # positive = we got better price

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
            game_start=game_start
        )
        self._clv_records.append(record)

        logger.info(
            f"CLV recorded: {game_id} {market} {side} "
            f"bet={bet_odds:+.0f} close={closing_odds:+.0f} CLV={clv_pct:+.2f}%"
        )
        return record

    def clv_summary(self) -> Dict:
        """Return summary statistics of all CLV records"""
        if not self._clv_records:
            return {'count': 0, 'avg_clv': 0.0, 'pct_positive': 0.0}

        clvs = [r.clv_pct for r in self._clv_records]
        return {
            'count': len(clvs),
            'avg_clv': round(np.mean(clvs), 3),
            'median_clv': round(float(np.median(clvs)), 3),
            'std_clv': round(float(np.std(clvs)), 3),
            'pct_positive': round(sum(1 for c in clvs if c > 0) / len(clvs), 3),
            'cumulative_clv': round(sum(clvs), 3)
        }

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

        Returns a dict with signals, edge, and recommendation.
        """
        signals = []
        sharp_side = None
        confidence_scores = []

        # --- RLM Check ---
        home_is_public_fave = home_ticket_pct >= 0.65
        away_is_public_fave = (1 - home_ticket_pct) >= 0.65

        if home_is_public_fave:
            line_moved_against_home = current_line < open_line  # home got fewer points
            if line_moved_against_home:
                ticket_gap = home_ticket_pct - home_money_pct
                if ticket_gap >= 0.10:
                    conf = min(0.90, 0.55 + ticket_gap * 2.0)
                    signals.append('RLM')
                    sharp_side = away_team
                    confidence_scores.append(conf)

        elif away_is_public_fave:
            away_ticket_pct = 1 - home_ticket_pct
            away_money_pct = 1 - home_money_pct
            line_moved_against_away = current_line > open_line
            if line_moved_against_away:
                ticket_gap = away_ticket_pct - away_money_pct
                if ticket_gap >= 0.10:
                    conf = min(0.90, 0.55 + ticket_gap * 2.0)
                    signals.append('RLM')
                    sharp_side = home_team
                    confidence_scores.append(conf)

        # --- Freeze Check ---
        line_unchanged = abs(current_line - open_line) <= 0.25
        heavy_public = home_ticket_pct >= 0.80 or (1 - home_ticket_pct) >= 0.80
        if heavy_public and line_unchanged:
            signals.append('FREEZE')
            sharp_side = away_team if home_ticket_pct >= 0.80 else home_team
            confidence_scores.append(0.70)

        # --- +EV Calculation ---
        pinnacle_implied = SharpMoneyDetector._american_to_implied_static(pinnacle_home_odds)
        retail_implied = SharpMoneyDetector._american_to_implied_static(retail_home_odds)

        # Devig Pinnacle (assume symmetric market for quick calc)
        # True edge = Pinnacle devigged prob vs retail implied
        devigged_prob = pinnacle_implied  # simplified; full devig requires both sides
        edge = devigged_prob - retail_implied

        avg_confidence = float(np.mean(confidence_scores)) if confidence_scores else 0.0

        return {
            'game_id': game_id,
            'market': market,
            'home_team': home_team,
            'away_team': away_team,
            'open_line': open_line,
            'current_line': current_line,
            'home_ticket_pct': home_ticket_pct,
            'home_money_pct': home_money_pct,
            'line_move': current_line - open_line,
            'sharp_signals': signals,
            'sharp_side': sharp_side,
            'signal_confidence': round(avg_confidence, 3),
            'pinnacle_implied': round(pinnacle_implied, 4),
            'retail_implied': round(retail_implied, 4),
            'ev_edge': round(edge, 4),
            'ev_edge_pct': round(edge * 100, 2),
            'is_positive_ev': edge > 0.03,
        }

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
        return SharpMoneyDetector._american_to_implied_static(american_odds)

    @staticmethod
    def _american_to_implied_static(american_odds: float) -> float:
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)

    @staticmethod
    def devig_odds(odds_side1: float, odds_side2: float) -> Tuple[float, float]:
        """
        Remove the bookmaker vig from a two-sided market.

        Args:
            odds_side1: American odds for side 1 (e.g., home team)
            odds_side2: American odds for side 2 (e.g., away team)

        Returns:
            Tuple of (true_prob_side1, true_prob_side2)
        """
        imp1 = SharpMoneyDetector._american_to_implied_static(odds_side1)
        imp2 = SharpMoneyDetector._american_to_implied_static(odds_side2)
        total = imp1 + imp2
        return imp1 / total, imp2 / total
