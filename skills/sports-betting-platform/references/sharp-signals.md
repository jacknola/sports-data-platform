# Sharp Money Signal Detection Reference

## Reverse Line Movement (RLM)
Line moves **against** public ticket majority = sharp money on unpopular side.

**Criteria:**
- Team gets ≥65% of public tickets
- Spread moves against that team
- ≥10% gap between ticket% and money%
- Larger gaps (≥20%) = higher confidence

```python
rlm_threshold = 0.65
gap_threshold = 0.10
if public_ticket_pct >= rlm_threshold and line_moved_against_public:
    if abs(ticket_pct - money_pct) >= gap_threshold:
        sharp_signal = "STRONG_RLM"
```

**Action:** Bet the side the sharp money is on (the unpopular side).

## Steam Moves
Sudden, coordinated multi-book shift within seconds.

**Detection:**
- Line change >0.5 points across 3+ books within 60 seconds
- Triggered by syndicates executing max-limit wagers simultaneously

**Rule:** Only act if execution latency < 3 seconds vs. lagging retail book. Chasing after full adjustment = negative EV.

## Line Freeze
Public overwhelms one side (≥80% tickets) but line doesn't move.

**Interpretation:** Book holds liability on unpopular side because sharp money backs it.

**Action:** Fade the public; bet the side the book is protecting.

## Head Fake Detection (Market Manipulation Filter)
Elite syndicates move lines in false directions to trap reactive algorithms.

**Filter:**
- Sudden movement that reverses within 15 minutes = potential fake
- Cross-reference with fundamental news (injuries, weather)
- In low-liquidity markets, require 2× std dev price jump

```python
def is_head_fake(movement, historical_vol, liquidity_index):
    is_low_liq = liquidity_index < 0.3
    is_outlier = abs(movement) > 2 * historical_vol
    reversed_quickly = movement_reversed_within_minutes(15)
    return is_low_liq and is_outlier and reversed_quickly
```

## Closing Line Value (CLV)
CLV = difference between odds at bet placement vs. Pinnacle closing line.
- `CLV > 0` consistently → profitable strategy
- `CLV < 0` consistently → no edge

## Juice Shift (Player Props)
Props adjusted via vig rather than line to avoid half-point exposure.

```python
JUICE_SHIFT_THRESHOLD = 10  # cents
line_unchanged = abs(current_line - prior_line) <= 0.25
over_shift = abs(current_over_odds - prior_over_odds)
if line_unchanged and over_shift >= JUICE_SHIFT_THRESHOLD:
    signal = 'JUICE_SHIFT'
```

## NCAAB-Specific Adjustments
Highly inefficient market (363 D1 teams).
- Home court: +4% to +8% (up to +10% large crowds)
- Altitude: +2% (Mountain West)
- Travel: -2% to -4% (cross-country)
- Rest: +2% per extra day vs. opponent

## Implementation
- `backend/app/services/sharp_money_detector.py` — RLM, steam, CLV, head fake
- `backend/app/services/bayesian.py` — Posterior probability integration
