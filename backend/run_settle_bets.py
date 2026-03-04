#!/usr/bin/env python3
"""
Settle Pending Bets & Update Google Sheets

Fetches final scores from the Odds API, grades all pending bets as
won/lost/push, then refreshes the BetTracker tab in Google Sheets.

Usage:
    python3 backend/run_settle_bets.py              # Settle + export
    python3 backend/run_settle_bets.py --dry-run    # Preview without saving
    python3 backend/run_settle_bets.py --days 5     # Look back further for scores
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.services.bet_settlement import BetSettlementEngine
from app.services.bet_tracker import BetTracker


def settle_all(days: int = 3, dry_run: bool = False):
    """Settle pending bets for both NBA and NCAAB, then export to Sheets."""
    tracker = BetTracker()
    settler = BetSettlementEngine()

    # ── Show pending state ──
    pending_ncaab = tracker.get_pending_bets(sport="ncaab")
    pending_nba = tracker.get_pending_bets(sport="nba")
    logger.info(f"Pending bets: {len(pending_ncaab)} NCAAB, {len(pending_nba)} NBA")

    if not pending_ncaab and not pending_nba:
        logger.info("No pending bets to settle.")
        return

    if dry_run:
        logger.info("[DRY RUN] Would settle the above bets — skipping.")
        return

    # ── Settle ──
    for sport in ["ncaab", "nba"]:
        try:
            logger.info(f"Settling {sport.upper()} bets (looking back {days} days)...")
            asyncio.run(settler.settle_pending_bets(sport))
        except Exception as e:
            logger.error(f"Settlement error for {sport}: {e}")

    # ── Summary ──
    metrics = tracker.get_performance_metrics()
    logger.info(
        f"Settlement complete — "
        f"W/L: {metrics.get('wins', 0)}/{metrics.get('losses', 0)}, "
        f"Win Rate: {metrics.get('win_rate', 0):.1%}, "
        f"ROI: {metrics.get('roi', 0):.1%}"
    )

    still_pending = len(tracker.get_pending_bets("ncaab")) + len(tracker.get_pending_bets("nba"))
    if still_pending:
        logger.info(f"{still_pending} bets still pending (games may not have finished yet)")

    # ── Export to Google Sheets ──
    try:
        from app.config import settings as _settings
        from app.services.google_sheets import GoogleSheetsService

        sid = getattr(_settings, "GOOGLE_SPREADSHEET_ID", None)
        if not sid:
            logger.warning("GOOGLE_SPREADSHEET_ID not set — skipping Sheets export")
            return

        sheets = GoogleSheetsService()
        if not sheets.is_configured:
            logger.warning("Google Sheets not configured — skipping export")
            return

        result = sheets.export_bet_tracker(sid)
        if result.get("status") == "success":
            logger.info(
                f"✅ BetTracker sheet updated — {result.get('rows_written', 0)} rows written"
            )
        else:
            logger.error(f"BetTracker export failed: {result}")

    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Settle bets and update Google Sheets")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--days", type=int, default=3, help="Days to look back for scores (default: 3)")
    args = parser.parse_args()

    settle_all(days=args.days, dry_run=args.dry_run)
