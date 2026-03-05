"""
Walk-Forward Backtester for NBA Player Props.

Simulates the full ML pipeline day-by-day through an NBA season.
On each loop date D the inference service receives a `date_limit=D`
parameter which restricts Qdrant to only neighbours whose game_date < D,
guaranteeing zero data leakage.

Data requirements
─────────────────
  • player_game_logs populated (run_backfill_pipeline.py)
  • sync_qdrant.py run once to build the vector index + scaler
  • PostgreSQL (window functions used in daily query)

Prop lines
──────────
  Actual sportsbook lines should ideally be stored in scenario JSON
  as {"prop_line": 24.5, "over_implied_prob": 0.524, ...}.
  When these fields are absent the script falls back to a season-average
  proxy (season_pts_rate * expected_mins) so the backtest can still run.

Usage
─────
  cd backend
  python -m app.scripts.backtest
  python -m app.scripts.backtest --start 2024-11-01 --end 2025-04-14
  python -m app.scripts.backtest --bankroll 10000 --edge-threshold 0.03 --export-sheets

Output (stdout + optional Google Sheets)
─────────────────────────────────────────
  Final bankroll, ROI, Brier score, Max drawdown, Win rate
  Daily equity curve (Date | Bankroll | PnL | Bets | Wins)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger
from sqlalchemy import text

ROOT = Path(__file__).parent.parent.parent          # → backend/
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal                # noqa: E402
from app.services.inference_service import PropInferenceService   # noqa: E402
from app.services.sheets_service import SheetsService             # noqa: E402

# ── Daily prop query (point-in-time safe, PostgreSQL required) ────────────────
_DAILY_SQL = text("""
WITH pit AS (
    SELECT
        pgl.id                                                              AS log_id,
        pgl.game_date,
        pgl.pts                                                             AS actual_points_scored,
        p.name                                                              AS player_name,

        COALESCE(
            AVG(pgl.pts)  OVER w_s
            / NULLIF(AVG(pgl.min) OVER w_s, 0) * 36.0,
            18.0
        )                                                                   AS usage_rate_season,
        COALESCE(VAR_SAMP(pgl.pts) OVER w_l5, 25.0)                        AS l5_form_variance,
        COALESCE(AVG(pgl.min) OVER w_s, 24.0)                              AS expected_mins,
        COALESCE(
            EXTRACT(EPOCH FROM (
                pgl.game_date
                - LAG(pgl.game_date) OVER (
                    PARTITION BY pgl.player_id ORDER BY pgl.game_date
                )
            )) / 86400.0,
            2.0
        )                                                                   AS rest_advantage,

        COALESCE((pgl.scenario->>'opp_pace')::float,          100.0)       AS opp_pace,
        COALESCE((pgl.scenario->>'opp_def_rtg')::float,       112.0)       AS opp_def_rtg,
        COALESCE((pgl.scenario->>'def_vs_position')::float,     0.0)       AS def_vs_position,
        COALESCE((pgl.scenario->>'implied_team_total')::float, 112.5)      AS implied_team_total,
        COALESCE((pgl.scenario->>'spread')::float,              0.0)       AS spread,
        COALESCE((pgl.scenario->>'prop_line')::float,           0.0)       AS prop_line,
        COALESCE((pgl.scenario->>'over_implied_prob')::float,   0.524)     AS implied_prob,
        CASE WHEN t.name = g.home_team THEN 1 ELSE 0 END                   AS is_home

    FROM  player_game_logs  pgl
    JOIN  players           p   ON p.id  = pgl.player_id
    JOIN  games             g   ON g.id  = pgl.game_id
    JOIN  teams             t   ON t.id  = pgl.team_id

    WHERE DATE(pgl.game_date) = :game_date
      AND pgl.pts  IS NOT NULL
      AND pgl.min  > 0

    WINDOW
        w_s  AS (PARTITION BY pgl.player_id ORDER BY pgl.game_date
                 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
        w_l5 AS (PARTITION BY pgl.player_id ORDER BY pgl.game_date
                 ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING)
)
SELECT * FROM pit
WHERE  usage_rate_season > 0
""")


# ── Kelly sizing ──────────────────────────────────────────────────────────────

def calculate_kelly_units(
    posterior_mean: float,
    implied_prob: float,
    bankroll: float,
    fraction: float = 0.25,
    cap: float = 0.10,
) -> float:
    """
    Fractional Quarter-Kelly bet size in dollars.

    Parameters
    ----------
    posterior_mean : Model probability of the OVER.
    implied_prob :   Market implied probability.
    bankroll :       Current bankroll in dollars.
    fraction :       Kelly fraction (0.25 = Quarter-Kelly).
    cap :            Maximum fraction of bankroll per bet.

    Returns
    -------
    Dollar bet size, 0.0 if edge is negative.
    """
    if implied_prob <= 0.0 or implied_prob >= 1.0:
        return 0.0

    b = (1.0 / implied_prob) - 1.0     # decimal odds − 1
    q = 1.0 - posterior_mean
    kelly = (b * posterior_mean - q) / b

    if kelly <= 0.0:
        return 0.0

    return round(min(fraction * kelly, cap) * bankroll, 2)


# ── Brier score ───────────────────────────────────────────────────────────────

def brier_score(probs: list[float], actuals: list[int]) -> float:
    """Mean squared error between predicted probabilities and binary outcomes."""
    if not probs:
        return float("nan")
    return float(np.mean([(p - a) ** 2 for p, a in zip(probs, actuals)]))


# ── Main simulation ───────────────────────────────────────────────────────────

def run_backtest(
    start: date,
    end: date,
    initial_bankroll: float = 10_000.0,
    edge_threshold: float = 0.03,
    export_sheets: bool = False,
) -> dict[str, Any]:
    """
    Walk-forward simulation from start to end (inclusive).

    Returns
    -------
    dict with keys: summary (overall stats) and daily_log (per-day records).
    """
    inference = PropInferenceService()
    db = SessionLocal()

    bankroll      = initial_bankroll
    peak_bankroll = initial_bankroll
    max_drawdown  = 0.0
    total_bets    = 0
    total_won     = 0

    all_probs:   list[float] = []
    all_actuals: list[int]   = []
    daily_log:   list[dict]  = []

    # Header row for Google Sheets equity curve
    equity_curve: list[list[Any]] = [
        ["Date", "Bankroll", "Daily PnL", "Bets", "Wins"]
    ]

    current = start
    while current <= end:
        dt = datetime(current.year, current.month, current.day)

        try:
            rows = db.execute(_DAILY_SQL, {"game_date": current}).fetchall()
        except Exception as exc:
            logger.warning(f"{current}: DB query failed — {exc}")
            current += timedelta(days=1)
            continue

        if not rows:
            current += timedelta(days=1)
            continue

        day_pnl  = 0.0
        day_bets = 0
        day_wins = 0

        for row in rows:
            prop_line    = float(row.prop_line or 0.0)
            implied_prob = float(row.implied_prob or 0.524)
            actual_pts   = float(row.actual_points_scored)

            # Fallback prop line: season scoring rate * expected minutes
            if prop_line <= 0.0:
                rate = float(row.usage_rate_season or 18.0) / 36.0
                prop_line = rate * float(row.expected_mins or 24.0)
                if prop_line <= 0.0:
                    continue

            features = {
                "usage_rate_season":  float(row.usage_rate_season),
                "l5_form_variance":   float(row.l5_form_variance),
                "expected_mins":      float(row.expected_mins),
                "opp_pace":           float(row.opp_pace),
                "opp_def_rtg":        float(row.opp_def_rtg),
                "def_vs_position":    float(row.def_vs_position),
                "implied_team_total": float(row.implied_team_total),
                "spread":             float(row.spread),
                "rest_advantage":     float(row.rest_advantage),
                "is_home":            float(row.is_home),
            }

            try:
                result = inference.predict(
                    features=features,
                    prop_line=prop_line,
                    implied_prob=implied_prob,
                    date_limit=dt,   # ← prevents Qdrant from seeing today's games
                )
            except (ValueError, RuntimeError) as exc:
                logger.debug(f"  {row.player_name}: {exc}")
                continue

            posterior_mean = result["posterior_mean"]
            edge           = result["edge"]
            rec            = result["recommendation"]

            # Track all predictions for Brier score (regardless of whether we bet)
            is_over = int(actual_pts > prop_line)
            all_probs.append(posterior_mean)
            all_actuals.append(is_over)

            # Skip if edge below threshold or model says PASS
            if abs(edge) < edge_threshold or rec == "PASS":
                continue

            bet_size = calculate_kelly_units(posterior_mean, implied_prob, bankroll)
            if bet_size <= 0.0:
                continue

            # Settle the bet
            bet_on_over = (rec == "OVER")
            won = (bet_on_over and is_over == 1) or (not bet_on_over and is_over == 0)

            if won:
                decimal_odds = 1.0 / implied_prob
                profit = bet_size * (decimal_odds - 1.0)
            else:
                profit = -bet_size

            bankroll  += profit
            day_pnl   += profit
            total_bets += 1
            day_bets   += 1

            if won:
                total_won += 1
                day_wins  += 1

            peak_bankroll = max(peak_bankroll, bankroll)
            dd = (peak_bankroll - bankroll) / peak_bankroll
            max_drawdown = max(max_drawdown, dd)

        daily_log.append({
            "date":     str(current),
            "bankroll": round(bankroll, 2),
            "pnl":      round(day_pnl, 2),
            "bets":     day_bets,
            "wins":     day_wins,
        })
        equity_curve.append(
            [str(current), round(bankroll, 2), round(day_pnl, 2), day_bets, day_wins]
        )

        logger.info(
            f"{current}  bankroll=${bankroll:>10,.2f}  "
            f"pnl={day_pnl:>+8.2f}  bets={day_bets}  wins={day_wins}"
        )
        current += timedelta(days=1)

    db.close()

    roi      = (bankroll - initial_bankroll) / initial_bankroll * 100.0
    win_rate = (total_won / total_bets * 100.0) if total_bets else 0.0
    bs       = brier_score(all_probs, all_actuals)

    summary = {
        "start":             str(start),
        "end":               str(end),
        "initial_bankroll":  initial_bankroll,
        "final_bankroll":    round(bankroll, 2),
        "roi_pct":           round(roi, 2),
        "total_bets":        total_bets,
        "total_won":         total_won,
        "win_rate_pct":      round(win_rate, 2),
        "brier_score":       round(bs, 4),
        "max_drawdown_pct":  round(max_drawdown * 100.0, 2),
        "total_predictions": len(all_probs),
    }

    _print_summary(summary)

    if export_sheets:
        sheets = SheetsService()
        sheets.push(equity_curve, sheet_name="Backtest Equity Curve")
        sheets.push(
            [list(summary.keys()), list(summary.values())],
            sheet_name="Backtest Summary",
        )
        logger.info("Results exported to Google Sheets")

    return {"summary": summary, "daily_log": daily_log}


def _print_summary(summary: dict) -> None:
    logger.info("")
    logger.info("=" * 56)
    logger.info("  BACKTEST RESULTS")
    logger.info("=" * 56)
    for k, v in summary.items():
        logger.info(f"  {k:<26} {v}")
    logger.info("=" * 56)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Walk-Forward NBA Player Prop Backtester"
    )
    parser.add_argument("--start",          default="2024-11-01",
                        help="Season start date YYYY-MM-DD")
    parser.add_argument("--end",            default="2025-04-14",
                        help="Season end date YYYY-MM-DD")
    parser.add_argument("--bankroll",       type=float, default=10_000.0,
                        help="Starting bankroll in dollars")
    parser.add_argument("--edge-threshold", type=float, default=0.03,
                        help="Minimum |edge| required to place a bet")
    parser.add_argument("--export-sheets",  action="store_true",
                        help="Export equity curve and summary to Google Sheets")
    args = parser.parse_args()

    run_backtest(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        initial_bankroll=args.bankroll,
        edge_threshold=args.edge_threshold,
        export_sheets=args.export_sheets,
    )
