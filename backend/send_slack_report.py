"""
Send All Picks to Slack — Unified Report

Runs NCAAB, NBA, and Player Prop analysis, then sends a single
formatted Slack message with all picks sectioned by sport.

Usage:
    python backend/send_slack_report.py              # Full report
    python backend/send_slack_report.py --nba-only   # NBA only
    python backend/send_slack_report.py --no-props   # Skip props
    python backend/send_slack_report.py --test       # Test webhook
"""

import sys
import os
import argparse
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.services.slack_service import SlackService
from app.services.slack_formatter import format_unified_slack_report


os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/slack_send.log",
    rotation="7 days",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

BANKROLL = 25.0


# ---------------------------------------------------------------------------
# NBA pipeline
# ---------------------------------------------------------------------------


async def _run_nba() -> tuple:
    """Run NBA ML analysis. Returns (predictions, bets)."""
    from app.services.nba_ml_predictor import NBAMLPredictor

    logger.info("Running NBA ML analysis...")
    predictor = NBAMLPredictor()
    predictions = await predictor.predict_today_games("nba")

    if not predictions:
        logger.warning("No NBA games found today")
        return [], []

    bets: List[Dict[str, Any]] = []

    for p in predictions:
        if "error" in p:
            continue

        ev = p["expected_value"]
        best_bet = ev["best_bet"]
        home_edge = ev.get("home_ev", 0)
        away_edge = ev.get("away_ev", 0)
        kelly_fraction = p.get("kelly_criterion", 0)

        best_side_team = p["home_team"] if best_bet == "home" else p["away_team"]
        best_side_odds = ev["home_odds"] if best_bet == "home" else ev["away_odds"]
        best_side_edge = home_edge if best_bet == "home" else away_edge

        if kelly_fraction > 0.001 and best_side_edge > 0.025:
            bets.append({
                "game_id": f"NBA_{p['home_team']}_{p['away_team']}_{datetime.now().strftime('%Y%m%d')}".replace(" ", ""),
                "sport": "nba",
                "side": best_side_team,
                "market": "moneyline",
                "odds": best_side_odds,
                "edge": best_side_edge,
                "bet_size": kelly_fraction * BANKROLL,
            })

        # Totals
        uo = p.get("underover_prediction")
        if uo:
            uo_prob = uo["over_prob"] if uo["recommendation"] == "over" else uo["under_prob"]
            uo_decimal = 1.909
            uo_ev = (uo_prob * (uo_decimal - 1)) - (1 - uo_prob)
            if uo_ev > 0.025:
                uo_kelly = (uo_ev / (uo_decimal - 1)) * 0.25
                uo_bet_size = uo_kelly * BANKROLL
                if uo_bet_size > 0.5:
                    bets.append({
                        "game_id": f"NBA_TOTAL_{p['home_team']}_{p['away_team']}_{datetime.now().strftime('%Y%m%d')}".replace(" ", ""),
                        "sport": "nba",
                        "side": f"{uo['recommendation'].upper()} {uo['total_points']}",
                        "market": "total",
                        "odds": -110,
                        "edge": uo_ev,
                        "bet_size": uo_bet_size,
                    })

    logger.info(f"NBA: {len(predictions)} games, {len(bets)} qualifying bets")
    return predictions, bets


# ---------------------------------------------------------------------------
# NCAAB pipeline
# ---------------------------------------------------------------------------


async def _run_ncaab() -> Optional[Dict[str, Any]]:
    """Run NCAAB sharp money analysis. Returns structured result dict.

    Runs in a thread executor because run_analysis() internally calls
    asyncio.run() which can't be nested in an existing event loop.
    """
    import concurrent.futures

    def _sync_ncaab() -> Dict[str, Any]:
        from run_ncaab_analysis import run_analysis as run_ncaab
        return run_ncaab()

    try:
        logger.info("Running NCAAB analysis...")
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, _sync_ncaab)
        logger.info(
            f"NCAAB: {result['game_count']} games, "
            f"{len(result.get('bets', []))} bets, "
            f"{len(result.get('scored_plays', []))} scored plays"
        )
        return result
    except Exception as e:
        logger.error(f"NCAAB analysis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Props pipeline
# ---------------------------------------------------------------------------


async def _run_props() -> Optional[Dict[str, Any]]:
    """Run player prop analysis. Returns structured result dict."""
    try:
        from app.routers.props import run_prop_analysis

        logger.info("Running player prop analysis...")
        result = await run_prop_analysis("nba")
        ev_count = result.get("positive_ev_count", 0)
        logger.info(f"Props: {result.get('total_props', 0)} scanned, {ev_count} +EV")
        return result
    except Exception as e:
        logger.error(f"Prop analysis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_and_send(
    include_ncaab: bool = True,
    include_nba: bool = True,
    include_props: bool = True,
) -> bool:
    """Run all analysis pipelines and send unified report to Slack."""
    slack = SlackService()

    ncaab_data: Optional[Dict[str, Any]] = None
    nba_predictions: List[Dict[str, Any]] = []
    nba_bets: List[Dict[str, Any]] = []
    prop_data: Optional[Dict[str, Any]] = None

    # Run pipelines
    if include_ncaab:
        ncaab_data = await _run_ncaab()

    if include_nba:
        nba_predictions, nba_bets = await _run_nba()

    if include_props:
        prop_data = await _run_props()

    # Check if we have anything
    has_ncaab = ncaab_data and ncaab_data.get("game_analyses")
    has_nba = bool(nba_predictions)
    has_props = prop_data and prop_data.get("best_props")

    if not has_ncaab and not has_nba and not has_props:
        logger.warning("No data from any pipeline")
        return slack.send_text("⚪ No games or props found on today's slate.")

    # Format unified report
    blocks = format_unified_slack_report(
        ncaab_data=ncaab_data,
        nba_predictions=nba_predictions,
        nba_bets=nba_bets,
        prop_data=prop_data,
        min_prop_tier="low",
    )

    # Build summary for notification text
    parts = []
    if has_ncaab:
        parts.append(f"{ncaab_data['game_count']} NCAAB")
    if has_nba:
        parts.append(f"{len(nba_predictions)} NBA")
    if has_props:
        parts.append(f"{prop_data['positive_ev_count']} props")
    summary = " + ".join(parts)

    ok = slack.send_blocks(blocks, text=f"📊 Daily Picks — {summary}")
    if ok:
        logger.info(f"Slack unified report sent: {summary}")
    else:
        logger.error("Slack report send FAILED")

    return ok


def main():
    parser = argparse.ArgumentParser(description="Send all picks to Slack")
    parser.add_argument("--test", action="store_true", help="Test webhook connection")
    parser.add_argument("--nba-only", action="store_true", help="NBA games only")
    parser.add_argument("--ncaab-only", action="store_true", help="NCAAB games only")
    parser.add_argument("--no-props", action="store_true", help="Skip player props")
    args = parser.parse_args()

    if args.test:
        slack = SlackService()
        ok = slack.test_connection()
        sys.exit(0 if ok else 1)

    include_ncaab = not args.nba_only
    include_nba = not args.ncaab_only
    include_props = not args.no_props and not args.ncaab_only

    ok = asyncio.run(run_and_send(
        include_ncaab=include_ncaab,
        include_nba=include_nba,
        include_props=include_props,
    ))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
