"""
Player Prop Sharp Money Detection

Applies line-movement and consensus analysis to player prop markets
(over/under totals):

- Line movement tracking      — magnitude and direction of prop line moves
- Juice Shift                  — vig swings without line move (sharp-side pressure)
- CLV tracking                 — reuses CLVRecord from line_movement_analyzer
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from loguru import logger

from app.services.line_movement_analyzer import CLVRecord, LineMovementAnalyzer


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class PropSnapshot:
    """Point-in-time snapshot of a player prop market"""
    timestamp: float
    book: str
    prop_id: str            # '{player_id}:{stat_type}' e.g. 'lebron_james:points'
    player_id: str
    player_name: str
    team: str
    opponent: str
    game_id: str
    stat_type: str          # 'points', 'rebounds', 'assists', 'threes', 'blocks', 'steals', 'pra'
    line: float             # e.g., 25.5
    over_odds: float        # American odds for over  (e.g., -115)
    under_odds: float       # American odds for under (e.g., -105)
    over_ticket_pct: float = 0.0    # % of public tickets on over
    over_money_pct: float = 0.0     # % of public dollars on over


@dataclass
class PropSignal:
    """Detected sharp money signal on a player prop"""
    signal_type: str        # 'RLM', 'STEAM', 'FREEZE', 'JUICE_SHIFT'
    prop_id: str
    player_name: str
    stat_type: str
    sharp_side: str         # 'over' or 'under'
    confidence: float       # 0.0 – 1.0
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


# ---------------------------------------------------------------------------
# Prop Analyzer
# ---------------------------------------------------------------------------

class PropAnalyzer:
    """
    Detects professional betting activity in player prop markets.

    Adapted for over/under prop lines with line-movement analysis:
    - Line movement tracking: magnitude and direction of prop line moves
    - Juice Shift: vig moves ≥ 10 cents without line change (market maker signal)
    """

    # --- Thresholds ---
    RLM_TICKET_THRESHOLD = 0.65
    RLM_GAP_THRESHOLD = 0.10
    RLM_HIGH_CONFIDENCE_GAP = 0.20

    STEAM_LINE_MOVE = 0.5           # half-point on prop total
    STEAM_ODDS_MOVE = 8             # 8-cent odds move counts as steam equivalent
    STEAM_WINDOW_SECONDS = 60
    STEAM_MIN_BOOKS = 3

    FREEZE_TICKET_THRESHOLD = 0.80
    FREEZE_MAX_LINE_MOVE = 0.25

    HEAD_FAKE_REVERSAL_MINUTES = 15
    HEAD_FAKE_VOLATILITY_MULTIPLIER = 2.0

    # --- Prop-specific threshold ---
    JUICE_SHIFT_THRESHOLD = 10      # 10-cent vig swing without line move

    def __init__(self):
        self._snapshots: Dict[str, List[PropSnapshot]] = {}
        self._volatility_history: Dict[str, List[float]] = {}
        self._clv_records: List[CLVRecord] = []

    # ------------------------------------------------------------------
    # Public Interface
    # ------------------------------------------------------------------

    def process_snapshot(self, snapshot: PropSnapshot) -> List[PropSignal]:
        """
        Ingest a new prop snapshot and return any detected sharp signals.

        Args:
            snapshot: Current prop market state from any sportsbook

        Returns:
            List of PropSignal objects (may be empty)
        """
        key = f"{snapshot.prop_id}:{snapshot.book}"
        if key not in self._snapshots:
            self._snapshots[key] = []

        prior = self._snapshots[key][-1] if self._snapshots[key] else None
        self._snapshots[key].append(snapshot)

        signals = []

        if prior is not None:
            line_move = snapshot.line - prior.line
            if line_move != 0:
                self._record_volatility(snapshot.prop_id, abs(line_move))

            # RLM check (requires ticket/money data)
            if snapshot.over_ticket_pct > 0 and snapshot.over_money_pct > 0:
                rlm = self._check_rlm(prior, snapshot)
                if rlm:
                    signals.append(rlm)

            # Juice shift check (no line move needed)
            juice = self._check_juice_shift(prior, snapshot)
            if juice:
                signals.append(juice)

        # Freeze check
        if snapshot.over_ticket_pct >= self.FREEZE_TICKET_THRESHOLD:
            freeze = self._check_freeze(snapshot.prop_id, snapshot)
            if freeze:
                signals.append(freeze)

        return signals

    def detect_steam(
        self,
        snapshots_by_book: Dict[str, PropSnapshot],
        prior_snapshots_by_book: Dict[str, PropSnapshot],
    ) -> Optional[PropSignal]:
        """
        Detect steam moves across multiple books simultaneously.

        Mirrors SharpMoneyDetector.detect_steam() for prop lines.
        """
        if len(snapshots_by_book) < self.STEAM_MIN_BOOKS:
            return None

        moves = []
        direction = None
        ref_snap = None

        for book, snap in snapshots_by_book.items():
            prior = prior_snapshots_by_book.get(book)
            if prior is None:
                continue

            elapsed = snap.timestamp - prior.timestamp
            if elapsed > self.STEAM_WINDOW_SECONDS:
                continue

            move = snap.line - prior.line
            if abs(move) >= self.STEAM_LINE_MOVE:
                d = 'UP' if move > 0 else 'DOWN'
                if direction is None:
                    direction = d
                    ref_snap = snap
                if d == direction:
                    moves.append({'book': book, 'move': move, 'elapsed': elapsed})

        if len(moves) >= self.STEAM_MIN_BOOKS and ref_snap is not None:
            confidence = min(0.95, 0.50 + len(moves) * 0.10)
            sharp_side = 'under' if direction == 'DOWN' else 'over'

            signal = PropSignal(
                signal_type='STEAM',
                prop_id=ref_snap.prop_id,
                player_name=ref_snap.player_name,
                stat_type=ref_snap.stat_type,
                sharp_side=sharp_side,
                confidence=confidence,
                details={
                    'books_moved': [m['book'] for m in moves],
                    'avg_move': round(np.mean([abs(m['move']) for m in moves]), 2),
                    'direction': direction,
                    'max_elapsed_s': max(m['elapsed'] for m in moves),
                }
            )
            logger.info(
                f"PROP STEAM: {ref_snap.player_name} {ref_snap.stat_type} "
                f"({len(moves)} books, confidence={confidence:.2f})"
            )
            return signal

        return None

    def filter_head_fake(self, signal: PropSignal, prop_id: str) -> bool:
        """
        Returns True if the signal is likely a head fake and should be discarded.

        Mirrors SharpMoneyDetector.filter_head_fake() exactly.
        """
        # Aggregate snapshots across all books for this prop_id
        all_snaps = []
        for key, snaps in self._snapshots.items():
            if key.startswith(f"{prop_id}:"):
                all_snaps.extend(snaps)

        all_snaps.sort(key=lambda s: s.timestamp)

        if len(all_snaps) < 4:
            return False

        cutoff = time.time() - self.HEAD_FAKE_REVERSAL_MINUTES * 60
        recent = [s for s in all_snaps if s.timestamp >= cutoff]
        if len(recent) < 2:
            return False

        first_line = recent[0].line
        last_line = recent[-1].line
        max_line = max(s.line for s in recent)
        min_line = min(s.line for s in recent)

        spike_magnitude = max_line - min_line
        net_change = abs(last_line - first_line)

        if net_change == 0 and spike_magnitude > 0:
            hist_vol = self._get_historical_volatility(prop_id)
            if hist_vol > 0 and spike_magnitude >= self.HEAD_FAKE_VOLATILITY_MULTIPLIER * hist_vol:
                logger.warning(
                    f"PROP HEAD FAKE: {prop_id} spike={spike_magnitude:.2f} "
                    f"hist_vol={hist_vol:.2f}"
                )
                return True

        return False

    def record_clv(
        self,
        prop_id: str,
        stat_type: str,
        side: str,
        bet_odds: float,
        closing_odds: float,
        game_start: float,
        bet_timestamp: Optional[float] = None,
    ) -> CLVRecord:
        """
        Record CLV for a placed prop bet. Reuses CLVRecord from sharp_money_detector.

        CLV > 0 means the bet was placed at better-than-closing odds.
        """
        record = LineMovementAnalyzer().record_clv(
            game_id=prop_id,
            market=f"prop_{stat_type}",
            side=side,
            bet_odds=bet_odds,
            closing_odds=closing_odds,
            game_start=game_start,
            bet_timestamp=bet_timestamp,
        )
        self._clv_records.append(record)
        return record

    def clv_summary(self) -> Dict:
        """Return summary statistics of all prop CLV records"""
        if not self._clv_records:
            return {'count': 0, 'avg_clv': 0.0, 'pct_positive': 0.0}

        clvs = [r.clv_pct for r in self._clv_records]
        return {
            'count': len(clvs),
            'avg_clv': round(float(np.mean(clvs)), 3),
            'median_clv': round(float(np.median(clvs)), 3),
            'std_clv': round(float(np.std(clvs)), 3),
            'pct_positive': round(sum(1 for c in clvs if c > 0) / len(clvs), 3),
            'cumulative_clv': round(sum(clvs), 3),
        }

    # ------------------------------------------------------------------
    # Standalone Analysis (mirrors analyze_game)
    # ------------------------------------------------------------------

    @staticmethod
    def analyze_prop(
        prop_id: str,
        player_name: str,
        stat_type: str,
        open_line: float,
        current_line: float,
        over_ticket_pct: float,
        over_money_pct: float,
        open_over_odds: float,
        current_over_odds: float,
        open_under_odds: float,
        current_under_odds: float,
        pinnacle_over_odds: Optional[float] = None,
        retail_over_odds: Optional[float] = None,
    ) -> Dict:
        """
        Static one-shot analysis of a player prop given snapshot data.

        Mirrors SharpMoneyDetector.analyze_game() — same signal logic,
        same return shape, adapted for over/under props.

        Returns a dict with signals, edge, and recommendation.
        """
        signals = []
        sharp_side = None
        confidence_scores = []

        under_ticket_pct = 1.0 - over_ticket_pct
        under_money_pct = 1.0 - over_money_pct

        # --- RLM Check ---
        over_is_public_fave = over_ticket_pct >= PropAnalyzer.RLM_TICKET_THRESHOLD
        under_is_public_fave = under_ticket_pct >= PropAnalyzer.RLM_TICKET_THRESHOLD

        if over_is_public_fave:
            line_moved_against_over = current_line < open_line  # line dropped = books fading over
            if line_moved_against_over:
                ticket_gap = over_ticket_pct - over_money_pct
                if ticket_gap >= PropAnalyzer.RLM_GAP_THRESHOLD:
                    conf = min(0.90, 0.55 + ticket_gap * 2.0)
                    signals.append('RLM')
                    sharp_side = 'under'
                    confidence_scores.append(conf)

        elif under_is_public_fave:
            line_moved_against_under = current_line > open_line  # line rose = books fading under
            if line_moved_against_under:
                ticket_gap = under_ticket_pct - under_money_pct
                if ticket_gap >= PropAnalyzer.RLM_GAP_THRESHOLD:
                    conf = min(0.90, 0.55 + ticket_gap * 2.0)
                    signals.append('RLM')
                    sharp_side = 'over'
                    confidence_scores.append(conf)

        # --- Freeze Check ---
        line_unchanged = abs(current_line - open_line) <= PropAnalyzer.FREEZE_MAX_LINE_MOVE
        heavy_public_over = over_ticket_pct >= PropAnalyzer.FREEZE_TICKET_THRESHOLD
        heavy_public_under = under_ticket_pct >= PropAnalyzer.FREEZE_TICKET_THRESHOLD

        if (heavy_public_over or heavy_public_under) and line_unchanged:
            signals.append('FREEZE')
            sharp_side = 'under' if heavy_public_over else 'over'
            confidence_scores.append(0.70)

        # --- Juice Shift Check ---
        over_odds_move = abs(current_over_odds - open_over_odds)
        under_odds_move = abs(current_under_odds - open_under_odds)
        if max(over_odds_move, under_odds_move) >= PropAnalyzer.JUICE_SHIFT_THRESHOLD and line_unchanged:
            signals.append('JUICE_SHIFT')
            # Vig swung toward over → sharp money on under (books protecting themselves)
            sharp_side = 'under' if over_odds_move > under_odds_move else 'over'
            conf = min(0.85, 0.55 + max(over_odds_move, under_odds_move) / 50)
            confidence_scores.append(conf)

        # --- EV Calculation ---
        # Devig the current prop market to get true probabilities
        true_over_prob, true_under_prob = PropAnalyzer.devig_prop(
            current_over_odds, current_under_odds
        )

        # Edge vs. retail implied probability
        over_edge = 0.0
        under_edge = 0.0
        if retail_over_odds is not None:
            retail_over_implied = PropAnalyzer._american_to_implied(retail_over_odds)
            retail_under_implied = 1.0 - retail_over_implied
            over_edge = true_over_prob - retail_over_implied
            under_edge = true_under_prob - retail_under_implied
        elif pinnacle_over_odds is not None:
            pinnacle_over_prob, _ = PropAnalyzer.devig_prop(
                pinnacle_over_odds, current_under_odds
            )
            over_edge = pinnacle_over_prob - PropAnalyzer._american_to_implied(current_over_odds)
            under_edge = -over_edge

        avg_confidence = float(np.mean(confidence_scores)) if confidence_scores else 0.0
        best_side = 'over' if over_edge >= under_edge else 'under'
        best_edge = max(over_edge, under_edge)

        return {
            'prop_id': prop_id,
            'player_name': player_name,
            'stat_type': stat_type,
            'open_line': open_line,
            'current_line': current_line,
            'line_move': round(current_line - open_line, 2),
            'over_ticket_pct': over_ticket_pct,
            'over_money_pct': over_money_pct,
            'sharp_signals': signals,
            'sharp_side': sharp_side,
            'signal_confidence': round(avg_confidence, 3),
            'true_over_prob': round(true_over_prob, 4),
            'true_under_prob': round(true_under_prob, 4),
            'over_edge': round(over_edge, 4),
            'under_edge': round(under_edge, 4),
            'best_side': best_side,
            'ev_edge': round(best_edge, 4),
            'ev_edge_pct': round(best_edge * 100, 2),
            'is_positive_ev': best_edge > 0.03,
        }

    # ------------------------------------------------------------------
    # Private Helpers (mirror SharpMoneyDetector exactly)
    # ------------------------------------------------------------------

    def _check_rlm(
        self, prior: PropSnapshot, current: PropSnapshot
    ) -> Optional[PropSignal]:
        """Detect Reverse Line Movement on a prop between two snapshots"""
        over_ticket_pct = current.over_ticket_pct
        over_money_pct = current.over_money_pct
        over_is_public_fave = over_ticket_pct >= self.RLM_TICKET_THRESHOLD

        if not over_is_public_fave:
            # Check under side
            under_ticket_pct = 1.0 - over_ticket_pct
            under_money_pct = 1.0 - over_money_pct
            if under_ticket_pct < self.RLM_TICKET_THRESHOLD:
                return None
            line_moved_against_under = current.line > prior.line
            if not line_moved_against_under:
                return None
            ticket_gap = under_ticket_pct - under_money_pct
            sharp_side = 'over'
        else:
            line_moved_against_over = current.line < prior.line
            if not line_moved_against_over:
                return None
            ticket_gap = over_ticket_pct - over_money_pct
            sharp_side = 'under'

        if ticket_gap < self.RLM_GAP_THRESHOLD:
            return None

        if ticket_gap >= self.RLM_HIGH_CONFIDENCE_GAP:
            confidence = min(0.90, 0.70 + (ticket_gap - 0.20) * 1.0)
        else:
            confidence = 0.50 + (ticket_gap - 0.10) * 2.0

        signal = PropSignal(
            signal_type='RLM',
            prop_id=current.prop_id,
            player_name=current.player_name,
            stat_type=current.stat_type,
            sharp_side=sharp_side,
            confidence=round(confidence, 3),
            details={
                'over_ticket_pct': round(over_ticket_pct, 3),
                'over_money_pct': round(over_money_pct, 3),
                'ticket_money_gap': round(ticket_gap, 3),
                'line_moved_from': prior.line,
                'line_moved_to': current.line,
                'line_change': round(current.line - prior.line, 2),
            }
        )
        logger.info(
            f"PROP RLM: {current.player_name} {current.stat_type} "
            f"tickets={over_ticket_pct:.0%} money={over_money_pct:.0%} "
            f"sharp={sharp_side} confidence={confidence:.2f}"
        )
        return signal

    def _check_freeze(self, prop_id: str, snapshot: PropSnapshot) -> Optional[PropSignal]:
        """Detect prop line freeze despite heavy public action"""
        # Collect snapshots for this prop_id across all books
        all_snaps = []
        for key, snaps in self._snapshots.items():
            if key.startswith(f"{prop_id}:"):
                all_snaps.extend(snaps)

        if len(all_snaps) < 2:
            return None

        all_snaps.sort(key=lambda s: s.timestamp)
        earliest = all_snaps[0]
        line_change = abs(snapshot.line - earliest.line)

        if line_change <= self.FREEZE_MAX_LINE_MOVE:
            public_fave_over = snapshot.over_ticket_pct >= self.FREEZE_TICKET_THRESHOLD
            sharp_side = 'under' if public_fave_over else 'over'

            signal = PropSignal(
                signal_type='FREEZE',
                prop_id=prop_id,
                player_name=snapshot.player_name,
                stat_type=snapshot.stat_type,
                sharp_side=sharp_side,
                confidence=0.70,
                details={
                    'over_ticket_pct': round(snapshot.over_ticket_pct, 3),
                    'open_line': earliest.line,
                    'current_line': snapshot.line,
                    'line_change': round(line_change, 2),
                }
            )
            logger.info(
                f"PROP FREEZE: {snapshot.player_name} {snapshot.stat_type} "
                f"public={snapshot.over_ticket_pct:.0%} frozen at {snapshot.line}"
            )
            return signal

        return None

    def _check_juice_shift(
        self, prior: PropSnapshot, current: PropSnapshot
    ) -> Optional[PropSignal]:
        """
        Detect significant vig movement without a line change.

        A juice shift (e.g., over -110 → over -130 with line unchanged) signals
        that the market maker is absorbing sharp money on one side by repricing
        the vig rather than moving the number.
        """
        line_unchanged = abs(current.line - prior.line) <= self.FREEZE_MAX_LINE_MOVE
        if not line_unchanged:
            return None

        over_shift = current.over_odds - prior.over_odds
        under_shift = current.under_odds - prior.under_odds

        max_shift = max(abs(over_shift), abs(under_shift))
        if max_shift < self.JUICE_SHIFT_THRESHOLD:
            return None

        # If over got more expensive (over_shift more negative), sharp money is on over
        # If under got more expensive (under_shift more negative), sharp money is on under
        if abs(over_shift) >= abs(under_shift):
            sharp_side = 'over' if over_shift < 0 else 'under'
            shift_amount = abs(over_shift)
        else:
            sharp_side = 'under' if under_shift < 0 else 'over'
            shift_amount = abs(under_shift)

        confidence = min(0.85, 0.55 + shift_amount / 50)

        signal = PropSignal(
            signal_type='JUICE_SHIFT',
            prop_id=current.prop_id,
            player_name=current.player_name,
            stat_type=current.stat_type,
            sharp_side=sharp_side,
            confidence=round(confidence, 3),
            details={
                'over_odds_from': prior.over_odds,
                'over_odds_to': current.over_odds,
                'under_odds_from': prior.under_odds,
                'under_odds_to': current.under_odds,
                'shift_cents': round(shift_amount, 1),
                'line': current.line,
            }
        )
        logger.info(
            f"PROP JUICE SHIFT: {current.player_name} {current.stat_type} "
            f"sharp={sharp_side} shift={shift_amount:.0f}¢ confidence={confidence:.2f}"
        )
        return signal

    def _record_volatility(self, prop_id: str, move: float):
        if prop_id not in self._volatility_history:
            self._volatility_history[prop_id] = []
        self._volatility_history[prop_id].append(move)
        self._volatility_history[prop_id] = self._volatility_history[prop_id][-50:]

    def _get_historical_volatility(self, prop_id: str) -> float:
        hist = self._volatility_history.get(prop_id, [])
        if len(hist) < 3:
            return 0.5
        return float(np.std(hist))

    @staticmethod
    def devig_prop(over_odds: float, under_odds: float) -> Tuple[float, float]:
        """
        Remove bookmaker vig from a two-sided prop market.

        Wrapper around LineMovementAnalyzer.devig_odds() for clarity.

        Returns:
            (true_over_prob, true_under_prob)
        """
        return LineMovementAnalyzer.devig_odds(over_odds, under_odds)

    @staticmethod
    def _american_to_implied(american_odds: float) -> float:
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)
