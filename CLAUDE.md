```markdown
# Sports Data Intelligence Platform — Claude.md

This document defines the quantitative sports betting methodology for this platform. It synthesizes institutional-grade sharp money logic with the existing multi-agent prediction infrastructure.

---

## Architecture Overview

The platform combines five specialized AI agents, Bayesian modeling, XGBoost ML predictions, and market microstructure analysis into a unified pipeline for identifying mathematically positive expected value (+EV) wagers.

```text
Market Data (Odds API, Scrapers)
        ↓
Sharp Signal Detection (RLM, Steam, CLV)
        ↓
Bayesian + Monte Carlo Probability Engine
        ↓
ML Prediction Layer (XGBoost / GNN)
        ↓
Multivariate Kelly Criterion (Correlated Portfolio)
        ↓
Expert Agent Review (Sequential Thinking)
        ↓
Final Slate Recommendations

```

---

## 1. Market Microstructure — Market Makers vs. Retail Books

Understanding the two-tier structure of the betting market is fundamental to all pricing logic.

### Market Makers (Sharp Books)

* **Pinnacle, Circa Sports, BetCRIS** — operate on high-volume, low-margin models.
* Welcome sharp action; use it as informational input for line calibration.
* Lines from these books represent **ground truth / fair market value**.
* Extremely high limits; limits increase as game time approaches.
* The closing line at these books is the most accurate reflection of true event probability.

### Retail / Follower Books

* **FanDuel, DraftKings, Caesars, etc.** — operate on high-margin, risk-averse models.
* Copy lines from market makers then inflate vig to protect against variance.
* Aggressively limit or ban accounts with consistent +CLV (Closing Line Value).
* These are the primary **exploitation targets** for +EV strategies.

### Betting Exchanges / Prediction Markets

* **Sporttrade, Prophet Exchange, Kalshi, Polymarket** — peer-to-peer trading.
* No house edge; participants pay commission on net profit only.
* Continuous double-auction mechanism with transparent order books.
* Optimal destination for institutional capital; no account restrictions.

**Rule:** Always derive the true probability from Pinnacle/market-maker odds (after devigging). Compare against retail book offers to identify +EV. Route large positions to exchanges.

---

## 2. Sharp Money Signal Detection

### 2.1 Reverse Line Movement (RLM)

RLM occurs when odds shift **against** the majority of public ticket volume.

**Signal criteria:**

* Team receives ≥65% of public tickets.
* Spread moves against that team (e.g., -7 to -6.5, or public side -1 to +0.5).
* Minimum 10% gap between ticket% and money% to validate.
* Larger gaps (≥20%) = higher confidence.

**Interpretation:** Institutional syndicate capital is positioned on the unpopular side, forcing market makers to adjust risk exposure despite public liability on the other side.

```python
# RLM Signal Logic
rlm_threshold = 0.65  # Minimum ticket % on public side
gap_threshold = 0.10  # Minimum ticket/money gap
if public_ticket_pct >= rlm_threshold and line_moved_against_public:
    if abs(ticket_pct - money_pct) >= gap_threshold:
        sharp_signal = "STRONG_RLM"

```

### 2.2 Steam Moves

Steam = sudden, coordinated, multi-book odds shift within seconds.

**Detection:**

* Line changes >0.5 points across 3+ sportsbooks within 60 seconds.
* Triggered by syndicate executing max-limit wagers simultaneously.
* Profitable only via latency arbitrage (bet lagging retail book before it adjusts).
* Chasing steam after full market adjustment = negative EV.

**Rule:** Only act on steam if execution latency < 3 seconds vs. lagging retail book.

### 2.3 Line Freeze

A team receives overwhelming public support (≥80% tickets) but the line does **not** move.

**Interpretation:** The sportsbook holds significant liability on the unpopular side and respects the sharp money backing it too much to offer better odds to professionals. The book is effectively frozen.

**Action:** Fade the public; bet the side the book is protecting.

### 2.4 Head Fake Detection (Market Manipulation Filter)

Elite syndicates intentionally move lines in false directions to trap reactive algorithms.

**Filter criteria:**

* Sudden movement that reverses within 15 minutes = potential head fake.
* Cross-reference with fundamental news (injuries, weather) before acting.
* In low-liquidity markets, require 2× standard deviation price jump to validate.

```python
# Head Fake Filter
def is_head_fake(movement, historical_vol, liquidity_index):
    is_low_liq = liquidity_index < 0.3
    is_outlier = abs(movement) > 2 * historical_vol
    reversed_quickly = movement_reversed_within_minutes(15)
    return is_low_liq and is_outlier and reversed_quickly

```

---

## 3. Positive Expected Value (+EV) Logic

### Devigging Market Maker Odds

The true probability is derived by removing the vig from market-maker odds.

```text
Pinnacle sides: -110 / -110
Implied prob each: 52.38% each (total 104.76% — 4.76% vig)
Devigged (Fair) prob: 52.38 / 104.76 = 50.00% true probability

If a retail book offers +105 on the same side (Decimal: 2.05):
Expected Value (EV) = (True Probability × Decimal Odds) - 1
EV = (0.50 × 2.05) - 1 = 1.025 - 1 = +0.025  →  +2.5% EV

```

*Note: We trigger bets based on EV (+2.5%), not just the difference in implied probabilities.*

### Closing Line Value (CLV)

CLV = the difference between odds secured at bet placement vs. Pinnacle closing line.

* `CLV > 0` consistently → profitable strategy confirmed.
* `CLV < 0` consistently → model or timing is providing no edge.

### Minimum Edge Requirements

| Confidence Level | Minimum Edge | Max Kelly Fraction |
| --- | --- | --- |
| Low (model edge only) | ≥3% | 12.5% (quarter-Kelly) |
| Medium (+RLM confirmation) | ≥5% | 25% (half-Kelly) |
| High (+steam/RLM + model) | ≥7% | 37.5% (half-Kelly boosted) |
| Maximum conviction | ≥10% | 50% (half-Kelly max) |

---

## 4. Monte Carlo Simulation Framework

### Stochastic Game Modeling

Each game is simulated 20,000 iterations using random variable sampling.

* `posterior_p` — mean of simulation (point estimate).
* `p05 / p95` — 90% confidence interval.
* `std` — variance (higher = higher uncertainty = reduce Kelly fraction).
* `p_value` — hypothesis test: is edge statistically significant?

### Drawdown Risk (Bankroll Management)

**Rule:** If the Expected Maximum Drawdown (EMDD) > 30% of bankroll, systematically reduce the Kelly fraction across the portfolio until EMDD < 20%.

---

## 5. Predictive Model Architecture

### 5.1 XGBoost (Primary Model — Tabular Data)

**Critical:** Optimize for **probability calibration**, not raw accuracy. A poorly calibrated model that shows 65% accuracy but assigns 80% confidence to 52% true-probability events will cause Kelly to over-bet and bankrupt the account. Apply Platt scaling or isotonic regression on validation sets.

### 5.2 Graph Neural Networks (GNNs) — Spatial-Temporal

**Architecture:** GATv2-TCN. Models player interactions as a topological graph to capture chemistry and formation dynamics. Ideal for player prop markets and live micro-markets using official RFID tracking feeds.

---

## 6. Multivariate Kelly Criterion

### Single Bet (Standard Kelly)

```text
f* = (p × b - q) / b
where: p = prob of winning, q = prob of losing, b = net fractional odds

```

**Always use Fractional Kelly** (Quarter or Half) to survive model calibration errors.

### Correlated Portfolio (Multivariate Kelly)

Treating simultaneous games as independent causes over-leveraging. We solve via constrained convex optimization using the Mean-Variance Taylor approximation of the log-wealth function.

```python
# Multivariate Kelly Portfolio Optimization
import numpy as np
from scipy.optimize import minimize

def multivariate_kelly(expected_returns, covariance_matrix, max_single=0.05):
    n = len(expected_returns)
    mu = np.array(expected_returns)
    V = np.array(covariance_matrix)

    # 2nd-order Taylor approximation of log-growth
    def neg_growth(f):
        return -(np.dot(f, mu) - 0.5 * f @ V @ f)

    constraints = [{'type': 'ineq', 'fun': lambda f: f}]  # f >= 0
    bounds = [(0, max_single)] * n  # No single bet > max_single of bankroll

    result = minimize(neg_growth, x0=np.ones(n) / (n * 10),
                      method='SLSQP', bounds=bounds, constraints=constraints)
    return result.x

```

---

## 7. Data Pipeline and Infrastructure

```text
[Live APIs] → [Apache Kafka] → [Apache Flink] → [Redis] → [WebSocket] → [UI]

```

**Rule:** Never price or bet live markets using data with >5 second latency. The exposure to court-siding and "known outcome" bettors creates catastrophic liability.

---

## 8. Sportsbook Risk Profiling and Behavioral Camouflage

**How Books Profile:** They track CLV, timing patterns, strict fraction stakes (e.g., $412.37), and market selection.
**Camouflage:** - Round Kelly outputs to human-like denominations ($412.37 → $400 or $425).

* Occasionally place small recreational bets (SGPs) to inject noise.
* Blend sharp bets in high-liquidity markets to mask capital.

---

## 9. College Basketball (NCAAB) Specific Notes

NCAAB is highly inefficient due to 363 Division I teams, extreme home court variables, and thin market pricing.

```python
ncaab_adjustments = {
    'home_court': +0.04 to +0.08,   # Up to +0.10 for large crowds
    'altitude':   +0.02,             # Mountain West teams
    'travel':     -0.02 to -0.04,   # Cross-country trips
    'rest':       +0.02 per extra day vs. opponent
}

```

---

## 10. Platform Service Map

| Service | File | Purpose |
| --- | --- | --- |
| BayesianAnalyzer | `backend/app/services/bayesian.py` | Posterior prob, Monte Carlo, Kelly |
| SharpMoneyDetector | `backend/app/services/sharp_money_detector.py` | RLM, steam, CLV, head fake |
| MultivariateKelly | `backend/app/services/multivariate_kelly.py` | Correlated portfolio optimization |
| NBAMLPredictor | `backend/app/services/nba_ml_predictor.py` | XGBoost predictions |
| TelegramService | `backend/app/services/telegram_service.py` | Bot messaging, rate limiting |
| OddsAgent | `backend/app/agents/odds_agent.py` | Value bet identification |

---

## 11. Player Prop Integration

**Prop-Specific Signal: Juice Shift**
Props are frequently adjusted via vig rather than the line to avoid half-point exposure.

```python
JUICE_SHIFT_THRESHOLD = 10  # cents
line_unchanged = abs(current_line - prior_line) <= 0.25
over_shift = abs(current_over_odds - prior_over_odds)
if line_unchanged and over_shift >= JUICE_SHIFT_THRESHOLD:
    signal = 'JUICE_SHIFT'

```

---

## 12. Workflow: Running a Game Slate

```bash
# Full agent-based analysis via API
POST /api/v1/agents/analyze {"sport": "basketball_ncaab", "date": "today"}

# Get best opportunities after analysis
GET /api/v1/bets?sport=ncaab&min_edge=0.03

# Run Telegram scheduler (3x daily daemon)
python backend/telegram_cron.py --daemon

```

---

## 13. Performance Benchmarks and Thresholds

| Metric | Minimum Acceptable | Target |
| --- | --- | --- |
| Model calibration (Brier score) | < 0.25 | < 0.22 |
| CLV (weekly average) | > 0 | > +1.5% |
| Win rate at -110 | > 52.4% | > 55% |
| ROI (monthly) | > 3% | > 8% |
| Max drawdown (Monte Carlo EMDD) | < 30% | < 20% |

---

## 14. Telegram Bot Integration

**Constraints:** 4096 chars max, HTML parse mode required, 30 messages/sec limit.
**Environment Variables Required:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_TIMEZONE`.

Each scheduled send includes: Header (Bankroll), Top Plays (Composite Score), Game-by-Game metrics, Portfolio Summary, and Risk Reminders (EMDD).

---

## 15. Slash Commands (Claude Code Skills)

These project-level skills are available in Claude Code via `/` prefix. Stored in `.claude/commands/`.

| Command | Description |
| --- | --- |
| `/run-analysis` | Run NCAAB sharp money analysis for tonight's slate |
| `/check-ev` | Calculate EV, devig, and Kelly given Pinnacle + retail odds |
| `/add-game` | Add a new game to the NCAAB slate interactively |
| `/new-slate` | Clear TONIGHT_GAMES and start fresh for a new date |
| `/send-report` | Send the betting report to Telegram on-demand |
| `/setup-telegram` | Scaffold the full Telegram service, formatter, and cron runner |

---

## 16. Implementation & Developer Guidelines

* **Dependency Management:** Core dependencies are `numpy, scipy, pandas, xgboost, httpx, loguru`. Keep heavy ML dependencies (e.g., `torch`) commented out in base environments to speed up non-inference deployments.
* **Path Resolution:** Always use explicit path resolution for environment files (`os.path.join(os.path.dirname(__file__), "..", ".env")`) to ensure cron scripts don't fail based on execution directory.
* **Python Path Setup:** Use `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` at the top of executable scripts to ensure internal module imports resolve correctly from the command line.
* **Script Execution Priorities:** - Main Script: `python3 backend/run_ncaab_analysis.py`
* Cron Service: `python3 backend/telegram_cron.py --send-now`



---

## References

1. Pinnacle / Circa / BetCRIS — market maker ground truth for devigging
2. KenPom Adjusted Efficiency — primary NCAAB predictive metric
3. The Odds API — multi-book odds ingestion
4. DonBest — sharp consensus line tracking
5. Action Network / Pregame — public ticket and money percentage data
6. Telegram Bot API — `https://core.telegram.org/bots/api`

```

```
