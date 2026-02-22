# Sports Data Intelligence Platform — Claude.md

This document defines the quantitative sports betting methodology for this platform. It synthesizes
institutional-grade sharp money logic with the existing multi-agent prediction infrastructure.

---

## Architecture Overview

The platform combines five specialized AI agents, Bayesian modeling, XGBoost ML predictions, and
market microstructure analysis into a unified pipeline for identifying mathematically positive
expected value (+EV) wagers.

```
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
- **Pinnacle, Circa Sports, BetCRIS** — operate on high-volume, low-margin models
- Welcome sharp action; use it as informational input for line calibration
- Lines from these books represent **ground truth / fair market value**
- Extremely high limits; limits increase as game time approaches
- The closing line at these books is the most accurate reflection of true event probability

### Retail / Follower Books
- **FanDuel, DraftKings, Caesars, etc.** — operate on high-margin, risk-averse models
- Copy lines from market makers then inflate vig to protect against variance
- Aggressively limit or ban accounts with consistent +CLV (Closing Line Value)
- These are the primary **exploitation targets** for +EV strategies

### Betting Exchanges / Prediction Markets
- **Sporttrade, Prophet Exchange, Kalshi, Polymarket** — peer-to-peer trading
- No house edge; participants pay commission on net profit only
- Continuous double-auction mechanism with transparent order books
- Optimal destination for institutional capital; no account restrictions

**Rule:** Always derive the true probability from Pinnacle/market-maker odds (after devigging).
Compare against retail book offers to identify +EV. Route large positions to exchanges.

---

## 2. Sharp Money Signal Detection

### 2.1 Reverse Line Movement (RLM)

RLM occurs when odds shift **against** the majority of public ticket volume.

**Signal criteria:**
- Team receives ≥65% of public tickets
- Spread moves against that team (e.g., -7 to -6.5, or public side -1 to +0.5)
- Minimum 10% gap between ticket% and money% to validate
- Larger gaps (≥20%) = higher confidence

**Interpretation:** Institutional syndicate capital is positioned on the unpopular side, forcing
market makers to adjust risk exposure despite public liability on the other side.

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
- Line changes >0.5 points across 3+ sportsbooks within 60 seconds
- Triggered by syndicate executing max-limit wagers simultaneously
- Profitable only via latency arbitrage (bet lagging retail book before it adjusts)
- Chasing steam after full market adjustment = negative EV

**Rule:** Only act on steam if execution latency < 3 seconds vs. lagging retail book.

### 2.3 Line Freeze

A team receives overwhelming public support (≥80% tickets) but the line does **not** move.

**Interpretation:** The sportsbook holds significant liability on the unpopular side and
respects the sharp money backing it too much to offer better odds to professionals.
The book is effectively frozen — it cannot move the line without creating an arbitrage.

**Action:** Fade the public; bet the side the book is protecting.

### 2.4 Head Fake Detection (Market Manipulation Filter)

Elite syndicates intentionally move lines in false directions to trap reactive algorithms.

**Pattern:**
1. Syndicate places max-limit on suboptimal side at visible market maker
2. Automated trackers and retail bots react, moving line in false direction
3. Syndicate executes true position at artificially improved number

**Filter criteria:**
- Sudden movement that reverses within 15 minutes = potential head fake
- Cross-reference with fundamental news (injuries, weather) before acting
- In low-liquidity markets, require 2× standard deviation price jump to validate
- Check historical volatility baseline before assuming genuine steam

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

The true probability is derived by removing the vig from market-maker odds:

```
Pinnacle sides: -110 / -110
Implied prob each: 52.38% each (total 104.76% — 4.76% vig)
Devigged prob: 52.38 / 104.76 = 50% each (fair)

If retail book offers +105 on the same side:
Implied: 48.78%
Fair value: 50%
Edge: 50% - 48.78% = +1.22%  →  POSITIVE EV
```

### Closing Line Value (CLV)

CLV = the difference between odds secured at bet placement vs. Pinnacle closing line.

**CLV is the definitive long-term measure of betting skill.** A bettor who consistently
beats the closing line is demonstrating genuine alpha regardless of short-term outcomes.

- `CLV > 0` consistently → profitable strategy confirmed
- `CLV < 0` consistently → model or timing is providing no edge
- Track CLV on every wager as the primary performance metric

### Minimum Edge Requirements

| Confidence Level | Minimum Edge | Max Kelly Fraction |
|---|---|---|
| Low (model edge only) | ≥3% | 12.5% (quarter-Kelly) |
| Medium (+RLM confirmation) | ≥5% | 25% (half-Kelly) |
| High (+steam/RLM + model) | ≥7% | 37.5% (half-Kelly boosted) |
| Maximum conviction | ≥10% | 50% (half-Kelly max) |

---

## 4. Monte Carlo Simulation Framework

### Stochastic Game Modeling

Each game is simulated 20,000 iterations using random variable sampling from calibrated
probability distributions for each input feature.

**Process:**
1. Sample win probability from posterior Beta distribution (α, β parameters)
2. Apply random perturbations to each feature (injuries, pace, form, matchup)
3. Accumulate simulated outcomes across all iterations
4. Compute full outcome distribution, not just median

**Key outputs:**
- `posterior_p` — mean of simulation (point estimate)
- `p05 / p95` — 90% confidence interval
- `std` — variance (higher = higher uncertainty = reduce Kelly fraction)
- `p_value` — hypothesis test: is edge statistically significant?

### Drawdown Risk (Bankroll Management)

The simulation also models **bankroll trajectory**:
- Expected Maximum Drawdown (EMDD) — median worst-case drawdown
- Monte Carlo Average Max Drawdown (XMDD) — mean worst-case across all simulations
- Risk of Ruin threshold — bankroll fraction where recovery is statistically improbable

**Rule:** If EMDD > 30% of bankroll, reduce Kelly fraction until EMDD < 20%.

---

## 5. Predictive Model Architecture

### 5.1 XGBoost (Primary Model — Tabular Data)

Gradient-boosted decision trees; handles non-linear feature interactions.

**Current performance:**
- NBA moneyline: ~69% accuracy
- NBA over/under: ~55% accuracy

**Features used:**
- Offensive/defensive efficiency ratings
- Team pace differential
- Rest days and travel distance
- Recent form (last 5-10 games)
- Win percentage (home/away split)
- Injury status of key players

**Critical:** Optimize for **probability calibration**, not raw accuracy. A poorly calibrated
model that shows 65% accuracy but assigns 80% confidence to 52% true-probability events
will cause Kelly to over-bet and bankrupt the account.

Calibration check: Platt scaling or isotonic regression on validation set probabilities.

### 5.2 Graph Neural Networks (GNNs) — Spatial-Temporal

**Architecture:** GATv2-TCN (Graph Attention + Temporal Convolution)

**Purpose:** Model player-to-player interactions as a topological graph where:
- **Nodes** = individual players
- **Edges** = interactions (passes, spatial proximity, defensive pressure, historical matchups)

**Advantage over tabular models:**
- Captures team chemistry and formation dynamics natively
- Temporal convolution layer analyzes multivariate time-series play-by-play data
- Detects momentum shifts invisible to aggregate statistics

**Applications:**
- Player prop markets (intended pass receiver, shot success probability)
- In-game live betting micro-markets
- Counterattack success probability in soccer

**Data requirements:** Official player tracking feeds (RFID, optical cameras) with <1s latency.

---

## 6. Multivariate Kelly Criterion

### Single Bet (Standard Kelly)

```
f* = (p × b - q) / b

where:
  p = probability of winning
  q = 1 - p (probability of losing)
  b = net fractional odds (decimal odds - 1)
```

**Always use Fractional Kelly** in practice:
- Quarter-Kelly (γ = 0.25): conservative, low variance, survives model calibration errors
- Half-Kelly (γ = 0.50): standard professional, balances growth vs. drawdown risk
- Full-Kelly: mathematically optimal but requires perfect calibration; avoid in practice

### Correlated Portfolio (Multivariate Kelly)

When betting multiple games simultaneously (e.g., NCAAB 20-game Saturday), outcomes are
**correlated** (same conferences, shared opponents, systematic biases). Treating as independent
causes over-leveraging and catastrophic ruin risk.

**Multivariate formulation uses covariance matrix V:**

```
g(f) ≈ Σ(fᵢ × μᵢ) - (1/2) × fᵀ V f

where:
  fᵢ = fraction bet on game i
  μᵢ = expected return on game i
  V  = N×N covariance matrix of all simultaneous outcomes
```

**Solve via constrained convex optimization** to find optimal allocation vector f* that
maximizes geometric growth rate while penalizing correlated risk exposure.

**Correlation factors to model:**
- Same conference games on same day (0.15-0.25 correlation)
- Same team playing back-to-back (0.30+ correlation)
- Totals and spreads of same game (0.60+ correlation)
- Same game parlays (0.85+ correlation)

```python
# Multivariate Kelly Portfolio Optimization
import numpy as np
from scipy.optimize import minimize

def multivariate_kelly(expected_returns, covariance_matrix, max_single=0.05):
    n = len(expected_returns)
    mu = np.array(expected_returns)
    V = np.array(covariance_matrix)

    def neg_growth(f):
        return -(np.dot(f, mu) - 0.5 * f @ V @ f)

    constraints = [{'type': 'ineq', 'fun': lambda f: f}]  # f >= 0
    bounds = [(0, max_single)] * n  # No single bet > max_single of bankroll

    result = minimize(neg_growth, x0=np.ones(n) / (n * 10),
                      method='SLSQP', bounds=bounds,
                      constraints=constraints)
    return result.x
```

---

## 7. Data Pipeline and Infrastructure

### Streaming Architecture

```
[Live APIs] → [Apache Kafka] → [Apache Flink] → [Redis] → [WebSocket] → [UI]
                (broker)        (stream proc)    (cache)
```

**Kafka:** Central event bus, decouples producers (odds feeds) from consumers (pricing engine).
Handles billions of events/day; absorbs traffic spikes at major events.

**Flink:** Stateful stream processing with sub-second latency and exactly-once semantics.
Handles:
- VWAP calculation across multiple books
- Dynamic odds propagation
- Real-time Monte Carlo updates
- Arbitrage anomaly detection
- Event-time windowing for out-of-order data

**Redis:** In-memory cache for immediate retrieval; stores latest odds, model outputs,
sharp signals. TTL-based invalidation per market.

### Official vs. Unofficial Data Feeds

| Feed Type | Latency | Use Case |
|---|---|---|
| Official (RFID, optical tracking) | <1 second | Live micro-markets, GNN input, auto-settlement |
| Semi-official (partner feeds) | 1-5 seconds | In-game spread/total pricing |
| Broadcast scraping | 5-60 seconds | Research only; never live bet on this |
| Manual spotters | Variable | Backup only; exploit court-siding risk |

**Rule:** Never price or bet live markets using data with >5 second latency. The exposure to
court-siding and "known outcome" bettors creates catastrophic liability.

---

## 8. Sportsbook Risk Profiling and Behavioral Camouflage

### How Books Profile Sharp Bettors

Books use AI to analyze:
1. **Closing Line Value (CLV)** — accounts that consistently beat Pinnacle close get flagged
2. **Timing patterns** — bets placed milliseconds after opening lines are published
3. **Market selection** — exclusive targeting of low-liquidity or derivative markets
4. **Stake precision** — exact fractional Kelly amounts ($412.37 instead of $400)
5. **Withdrawal frequency** — consistent net withdrawal pattern

### Behavioral Camouflage Techniques

**Stake normalization:** Round Kelly outputs to human-like denominations.
- $412.37 → $400 or $425
- $1,876.50 → $1,900 or $2,000

**Strategic sub-optimization:** Occasionally place small recreational bets (SGPs, promos)
to inject noise into the risk profiling algorithm. Dilutes sharp profile.

**Market blending:** Place primary sharp bets in high-liquidity, high-volume markets
(NFL Sunday spreads, major conference basketball) where public volume masks sharp capital.

**Account diversification:** Use multiple accounts across multiple books; never max-limit
the same book consistently. Rotate primary books.

**Exchange migration:** Route institutional capital to exchanges (Sporttrade, Prophet)
where commissions are charged on net profit and accounts cannot be limited.

---

## 9. College Basketball (NCAAB) Specific Notes

### Market Inefficiency Profile

NCAAB is among the most inefficient sports betting markets due to:
- 363 Division I teams (books price many games thinly)
- Extreme home court advantage variability (fan environments, travel distance)
- Massive KenPom/Adjusted Efficiency divergence from public perception
- Injury information asymmetry in non-marquee programs
- Conference-specific biases in public betting patterns

### Key Adjustments for NCAAB Bayesian Model

```python
ncaab_adjustments = {
    'home_court': +0.04 to +0.08,   # Varies by venue; large-crowd environments up to +0.10
    'altitude':   +0.02,             # Mountain West teams at home
    'travel':     -0.02 to -0.04,   # Cross-country trips, especially Big East to PAC-12
    'rest':       +0.02 per extra day vs. opponent,
    'fatigue':    -0.03 for 3 games in 5 days,
    'kenpom_adj_eff_diff': primary predictor (coefficient ~0.024 per point differential)
}
```

### Sharp Books for NCAAB

For NCAAB closing lines, use Pinnacle as ground truth. Secondary references:
- Circa Sports (sharp, high limits on major conference games)
- Bookmaker.eu / Heritage Sports (offshore market movers)
- Consensus closing line from DonBest

### NCAAB Market Priority

| Priority | Market | Why |
|---|---|---|
| High | Spread (1H, full game) | Most liquid; CLV signal strongest |
| High | Total (over/under) | Pace-adjusted models outperform public |
| Medium | Team total | Less liquid; higher edge potential |
| Low | Moneyline (big favorites) | Heavy vig destroys edge on chalk |
| Low | Player props | Low limits; sharp action restricted quickly |

---

## 10. Platform Service Map

| Service | File | Purpose |
|---|---|---|
| BayesianAnalyzer | `backend/app/services/bayesian.py` | Posterior probability, Monte Carlo, Kelly |
| SharpMoneyDetector | `backend/app/services/sharp_money_detector.py` | RLM, steam, CLV, head fake filter |
| MultivariateKelly | `backend/app/services/multivariate_kelly.py` | Correlated portfolio optimization |
| NBAMLPredictor | `backend/app/services/nba_ml_predictor.py` | XGBoost predictions (NBA) |
| PropAnalyzer | `backend/app/services/prop_analyzer.py` | Prop RLM, steam, freeze, juice shift detection |
| PropProbabilityModel | `backend/app/services/prop_probability.py` | Normal distribution prop projection + edge |
| SportsAPIService | `backend/app/services/sports_api.py` | Odds ingestion (The Odds API) |
| WebScraper | `backend/app/services/web_scraper.py` | Crawl4AI intelligent extraction |
| **TelegramService** | **`backend/app/services/telegram_service.py`** | **Bot messaging, chunking, retry, rate limit** |
| **ReportFormatter** | **`backend/app/services/report_formatter.py`** | **HTML formatting for Telegram reports** |
| OddsAgent | `backend/app/agents/odds_agent.py` | Value bet identification |
| AnalysisAgent | `backend/app/agents/analysis_agent.py` | Bayesian + ML orchestration |
| ExpertAgent | `backend/app/agents/expert_agent.py` | Sequential thinking final review |

---

## 11. Player Prop Integration

### Prop Pipeline Architecture

```
Prop Odds (Odds API / book scrape)
        ↓
PropProbabilityModel.project()       — Normal distribution projection
  ├─ base_mean = season_avg
  ├─ adjustments: pace, matchup, usage, injury, rest, home/away
  └─ P(over) = 1 - Φ((line - μ_adj) / σ_adj)
        ↓
PropAnalyzer.analyze_prop()          — Sharp signal detection
  ├─ RLM  — line moves against public over/under tickets
  ├─ STEAM — coordinated multi-book prop line shift (≥3 books, 60s)
  ├─ FREEZE — line frozen despite ≥80% public on one side
  └─ JUICE_SHIFT — vig swings ≥10¢ without line move (NEW for props)
        ↓
BayesianAnalyzer.compute_posterior() — Same as game markets
  ├─ devig_prob  = market devigged P(over) (sharp market prior)
  ├─ implied_prob = retail book implied P(over)
  └─ features: injury_status, pace, usage_trend, is_home
        ↓
MultivariateKellyOptimizer           — Correlated portfolio sizing
  └─ market='prop', game_id=actual game ID (cross-prop correlation handled)
```

### Prop-Specific Signal: Juice Shift

Props are frequently adjusted via vig rather than line (books protect the number to avoid half-point exposure). The JUICE_SHIFT signal captures this:

```python
# Juice Shift Logic
JUICE_SHIFT_THRESHOLD = 10  # cents
line_unchanged = abs(current_line - prior_line) <= 0.25
over_shift = abs(current_over_odds - prior_over_odds)
if line_unchanged and over_shift >= JUICE_SHIFT_THRESHOLD:
    sharp_side = 'over' if current_over_odds < prior_over_odds else 'under'
    signal = 'JUICE_SHIFT'
```

### Prop Standard Deviation Factors (Empirical)

| Stat | σ / μ Factor | Notes |
|---|---|---|
| Points | 0.40 | Most consistent; usage-driven |
| Rebounds | 0.45 | Higher variance; opponent-dependent |
| Assists | 0.50 | Pace-sensitive; opportunity-driven |
| Threes | 0.55 | Highest variance; attempt-dependent |
| Blocks/Steals | 0.60 | Most volatile; matchup-dependent |
| PRA | 0.35 | Diversified; lower CV than components |

### Prop API Endpoints

```bash
# All props for a sport (with sharp analysis)
GET /api/v1/props/nba

# Best props by EV (sharps-only filter available)
GET /api/v1/props/nba/best?min_edge=0.03&require_sharp=true

# Full pipeline on a single prop
POST /api/v1/props/analyze
{
  "player_name": "LeBron James",
  "stat_type": "points",
  "line": 25.5,
  "over_odds": -115,
  "under_odds": -105,
  "season_avg": 24.8,
  "last_5_avg": 27.2,
  ...
}
```

### Prop Market Priority

| Priority | Market | Why |
|---|---|---|
| High | Points (stars only) | Most liquid; model calibrates well on usage |
| High | PRA (combo props) | Higher lines = better Normal approx; less noisy |
| Medium | Assists / Rebounds | Pace/matchup adjustments add measurable edge |
| Low | Threes | High variance; model less reliable |
| Low | Blocks / Steals | Lowest volume; sharpest limits, hardest to beat |

---

## 12. Workflow: Running a Game Slate

```bash
# 1. Run NCAAB sharp money analysis for tonight's slate
python backend/run_ncaab_analysis.py

# 2. Full agent-based analysis via API
POST /api/v1/agents/analyze
{"sport": "basketball_ncaab", "date": "today"}

# 3. Get best opportunities after analysis
GET /api/v1/bets?sport=ncaab&min_edge=0.03

# 4. Get best player props
GET /api/v1/props/nba/best?min_edge=0.03&require_sharp=true

# 5. Bayesian deep-dive on specific game
POST /api/v1/bayesian
{"selection_id": "...", "devig_prob": 0.54, "implied_prob": 0.50, "features": {...}}

# 6. Full prop analysis on a specific player
POST /api/v1/props/analyze
{"player_name": "...", "stat_type": "points", "line": 25.5, ...}

# 7. Send report to Telegram immediately (on-demand)
python backend/telegram_cron.py --send-now

# 8. Run Telegram scheduler (3x daily daemon)
python backend/telegram_cron.py --daemon
```

---

## 13. Performance Benchmarks and Thresholds

| Metric | Minimum Acceptable | Target |
|---|---|---|
| Model calibration (Brier score) | < 0.25 | < 0.22 |
| CLV (weekly average) | > 0 | > +1.5% |
| Win rate at -110 | > 52.4% | > 55% |
| ROI (monthly) | > 3% | > 8% |
| p-value for strategy edge | < 5% | < 0.1% |
| Max drawdown (Monte Carlo EMDD) | < 30% | < 20% |
| Sharpe ratio (betting portfolio) | > 1.0 | > 1.5 |

---

---

## 14. Telegram Bot Integration

### Architecture

```
Schedule (cron / APScheduler)
        ↓
telegram_cron.py  →  run_analysis() (captures stdout)
        ↓
ReportFormatter   →  HTML-formatted message
        ↓
TelegramService   →  Telegram Bot API
        ↓
Your Chat / Group / Channel
```

### Environment Variables

| Variable | Description | Required |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `TELEGRAM_CHAT_ID` | Your personal / group / channel ID | Yes |
| `TELEGRAM_TIMEZONE` | Timezone for schedule (default: `America/New_York`) | No |
| `TELEGRAM_CRON_MORNING` | Morning send cron (default: `0 9 * * *`) | No |
| `TELEGRAM_CRON_AFTERNOON` | Afternoon send cron (default: `0 14 * * *`) | No |
| `TELEGRAM_CRON_EVENING` | Evening send cron (default: `0 19 * * *`) | No |

**Getting your Chat ID:** Message `@userinfobot` on Telegram — it replies instantly with your numeric ID.

### Key Constraints (Telegram Bot API)

- **Message length:** 4096 characters max per message — auto-chunk long reports
- **Parse mode:** Use `HTML` (not Markdown) — more predictable with betting symbols like `+`, `-`, `%`
- **Rate limit:** ~30 messages/second to different chats; ~1 message/second to same chat
- **Allowed HTML tags:** `<b>`, `<i>`, `<u>`, `<code>`, `<pre>`, `<a href="...">`

### Report Format (3x Daily)

Each scheduled send includes:
1. **Header** — date, report type (Morning/Afternoon/Evening), bankroll snapshot
2. **Top Plays** — ranked by composite score (edge × signal confidence)
3. **Game-by-Game** — devig probs, edge, sharp signals, Kelly allocation
4. **Portfolio Summary** — total exposure, expected growth rate, active bet count
5. **Risk Reminders** — CLV tracking reminder, EMDD warning if exposure is high

### Suggested Feature Additions (Future)

| Feature | Implementation Note |
|---|---|
| `/picks` command | Bot listens for messages via webhook or polling; runs analysis on demand |
| `/bankroll <amount>` | Update BANKROLL in run_ncaab_analysis.py dynamically |
| `/clv <bet_odds> <closing_odds>` | Quick CLV calculator returned inline |
| Result tracking | After games finish, bot sends P&L update with actual outcomes |
| Alert on sharp steam | Real-time steam detection triggers immediate Telegram alert |
| Inline keyboard | Telegram inline buttons: [Run Analysis] [Send Now] [CLV Check] |

---

## 15. Slash Commands (Claude Code Skills)

These project-level skills are available in Claude Code via `/` prefix. Stored in `.claude/commands/`.

| Command | Description | When to Use |
|---|---|---|
| `/run-analysis` | Run NCAAB sharp money analysis for tonight's slate | Check tonight's plays |
| `/check-ev` | Calculate EV, devig, and Kelly given Pinnacle + retail odds | Evaluating any specific bet |
| `/add-game` | Add a new game to the NCAAB slate interactively | Updating tonight's game list |
| `/new-slate` | Clear TONIGHT_GAMES and start fresh for a new date | Each new betting day |
| `/send-report` | Send the betting report to Telegram on-demand | Ad-hoc report delivery |
| `/setup-telegram` | Scaffold the full Telegram service, formatter, and cron runner | Initial Telegram setup |

### Usage Examples

```
/run-analysis
→ Runs python backend/run_ncaab_analysis.py and summarizes top plays

/check-ev
→ Prompts for Pinnacle odds, retail odds, model prob → returns edge table

/add-game
→ Walks through all required fields and appends to TONIGHT_GAMES

/new-slate
→ Clears TONIGHT_GAMES, updates date in docstring, ready for /add-game

/send-report
→ Runs analysis, formats it, sends to TELEGRAM_CHAT_ID immediately

/setup-telegram
→ Creates telegram_service.py, report_formatter.py, telegram_cron.py
```

---

## References

1. Pinnacle / Circa / BetCRIS — market maker ground truth for devigging
2. KenPom Adjusted Efficiency — primary NCAAB predictive metric
3. The Odds API — multi-book odds ingestion
4. DonBest — sharp consensus line tracking
5. Action Network / Pregame — public ticket and money percentage data
6. OddsJam / Unabated / Outlier — +EV opportunity scanning
7. Sporttrade / Prophet Exchange — exchange routing for institutional capital
8. Telegram Bot API — `https://core.telegram.org/bots/api`
9. @BotFather — create and manage Telegram bots
10. @userinfobot — get your Telegram Chat ID
