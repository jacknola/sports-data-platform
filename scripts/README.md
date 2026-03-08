# Standalone Prediction Script

Run NBA player-prop predictions from the command line — **no FastAPI server,
no Redis, no Docker required.**

---

## 1. Install dependencies (one time)

```bash
# From the repo root:
pip install -r scripts/requirements-predict.txt
```

That installs only `numpy`, `scipy`, and `loguru`.  
*(Optionally install `xgboost` and `lightgbm` to use trained models; the script
falls back to calibrated heuristics if they are absent.)*

---

## 2. Predict a single prop

```bash
python3 scripts/predict_props_v2.py \
  --player "Jayson Tatum" \
  --prop points \
  --line 23.5 \
  --odds -120 \
  --dvp 14 \
  --minutes 37
```

### Arguments

| Flag | Required | Description |
|------|----------|-------------|
| `--player` | ✓ | Player name (for display) |
| `--prop` | ✓ | One of: `points`, `rebounds`, `assists`, `threes`, `steals`, `blocks`, `turnovers`, `pts_rebs_asts` |
| `--line` | ✓ | Sportsbook O/U line (e.g. `23.5`) |
| `--odds` | — | American odds (e.g. `-120`, `+136`). Required to get edge / Kelly output. |
| `--dvp` | — | Defense vs Position rank 1–30 (1 = toughest, 30 = softest). Default: 15. |
| `--minutes` | — | Projected minutes. Default: 32. |
| `--total` | — | Implied team total (e.g. `224.0`). Default: 112. |
| `--bankroll` | — | Bankroll in $ for Kelly stake sizing. Default: 1000. |
| `--team` | — | Team abbreviation (display only). |
| `--opponent` | — | Opponent abbreviation (display only). |

### Example output

```
════════════════════════════════════════════════════════════
  Jayson Tatum — POINTS 23.5
════════════════════════════════════════════════════════════

  Projected Value:    23.5
  OVER Probability:   67.4%
  UNDER Probability:  32.6%

  ── Model Breakdown ──
  XGBoost:   63.1%
  LightGBM:  68.2%
  Bayesian:  70.2%
  Ensemble:  67.4%

  Agreement:  STRONG (spread: 7.1%)

  ── Monte Carlo (20,000 sims) ──
  Mean: 23.49  Std: 5.55
  MC Over%: 51.2%

  ── Edge Detection ──
  Edge:    +16.4%
  Rating:  STRONG BET
  Direction: OVER
  Kelly:   1.93% → $19.30
  Composite Score: 0.6842
════════════════════════════════════════════════════════════
```

---

## 3. Batch mode — analyze tonight's slate

Use a JSON file listing every prop you want to analyze.

```bash
python3 scripts/predict_props_v2.py \
  --batch scripts/tonight_march8.json \
  --output results.json
```

### Batch input format

Each entry in the JSON array supports these fields:

```json
{
  "player":  "Jayson Tatum",
  "team":    "BOS",
  "opponent":"CLE",
  "prop":    "points",
  "line":    23.5,
  "odds":    -120,
  "minutes": 37,
  "dvp":     14,
  "total":   224.0,
  "l5_avg":  27.4,
  "l10_avg": 27.0,
  "l20_avg": 26.8,
  "ewma":    27.1,
  "game_logs": [28, 26, 30, 27, 26]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `player`, `prop`, `line` | ✓ | Same as single-prop mode |
| `odds` | — | American odds |
| `minutes` | — | Projected minutes (default: 32) |
| `dvp` | — | DvP rank 1–30 (default: 15) |
| `total` | — | Implied team total (default: 112) |
| `l5_avg` | — | Last-5-game average for this stat |
| `l10_avg` | — | Last-10-game average |
| `l20_avg` | — | Last-20-game average |
| `ewma` | — | Exponentially-weighted moving average |
| `game_logs` | — | Raw game-log values (list of floats) used for Bayesian update and L5 hit-rate scoring |

The ready-made file `scripts/tonight_march8.json` has 30 props from the
March 8 2026 NBA slate and can be used as a template.

---

## 4. Top-N by composite confidence

Add `--top-n` to show only the highest-confidence picks, ranked by:

| Component | Weight |
|-----------|--------|
| Edge magnitude (capped at 20%) | 40% |
| Model agreement | 30% |
| DvP alignment | 20% |
| L5 hit rate | 10% |

```bash
# Show top 30, save full results to JSON
python3 scripts/predict_props_v2.py \
  --batch scripts/tonight_march8.json \
  --top-n 30 \
  --output top30.json
```

---

## 5. Save results to JSON

Pass `--output <file>` (works with or without `--top-n`).  
The output is a JSON array of `PredictionResult` objects — one per prop.

```bash
python3 scripts/predict_props_v2.py \
  --batch scripts/tonight_march8.json \
  --top-n 10 \
  --output /tmp/top10.json
```

---

## 6. Tips

- **No API key needed** — the script runs entirely offline using the features
  you supply. Live odds must be entered manually (or via a batch JSON built
  from your odds source).
- **Heuristic fallback** — if XGBoost/LightGBM are not installed the script
  uses feature-weighted logistic heuristics that are still well-calibrated for
  typical prop distributions.
- **Kelly sizing** — always Quarter-Kelly (capped at 5% of bankroll). Pass
  `--bankroll` to get dollar amounts.
- **Batch template** — copy `scripts/tonight_march8.json` and edit the entries
  for your own slate. Only `player`, `prop`, and `line` are required per entry.
- **Debug output** — add `--verbose` to see model-fallback notices and other
  diagnostics, or set `LOGURU_LEVEL=DEBUG` in your environment.
