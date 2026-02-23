"""
Telegram Cron Runner

Sends the full betting report to Telegram 3× daily on a schedule,
or on-demand via --send-now.

Usage:
    # Send immediately (one-shot)
    python backend/telegram_cron.py --send-now

    # Run as a persistent scheduler (stays alive, fires 3x daily)
    python backend/telegram_cron.py --daemon

    # Send a picks-only summary (shorter message)
    python backend/telegram_cron.py --send-now --picks-only

Schedule (set in .env):
    TELEGRAM_CRON_MORNING   default: 0 9  * * *  (9:00 AM ET)
    TELEGRAM_CRON_AFTERNOON default: 0 14 * * *  (2:00 PM ET)
    TELEGRAM_CRON_EVENING   default: 0 19 * * *  (7:00 PM ET)
"""

import sys
import os
import argparse
import signal
from datetime import datetime

# Allow imports from backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from loguru import logger
from app.config import settings
from app.services.telegram_service import TelegramService
from app.services.report_formatter import ReportFormatter
from app.services.bet_settlement import BetSettlementEngine
from app.services.bet_tracker import BetTracker
from app.services.analysis_runner import (
    capture_analysis,
    run_orchestrated_analysis,
    run_prop_analysis_pipeline,
    run_dvp_analysis_pipeline,
)


# ---------------------------------------------------------------------------
# Core send logic
# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/telegram_cron.log",
    rotation="7 days",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


# ---------------------------------------------------------------------------
# Core send logic
# ---------------------------------------------------------------------------


def _label_for_hour(hour: int) -> str:
    """Return a report label based on hour of day."""
    if hour < 12:
        return "MORNING"
    if hour < 17:
        return "AFTERNOON"
    return "EVENING"


def send_report(picks_only: bool = False) -> bool:
    """
    Run orchestrated analysis, format, and send live picks to Telegram.

    The orchestrator pipeline:
        1. Settle pending bets from prior days.
        2. Run NCAAB + NBA core analysis (structured data).
        3. Enrich via OrchestratorAgent (sentiment, scraping, expert).
        4. Dynamically size the pick list to the slate.
        5. Format and send.

    Falls back to the legacy ``capture_analysis()`` path if the
    orchestrator fails entirely.

    Args:
        picks_only: If True, send compact picks summary instead of full report

    Returns:
        True if sent successfully
    """
    telegram = TelegramService()
    now = datetime.now()
    label = _label_for_hour(now.hour)

    logger.info(f"Starting {label} report send (picks_only={picks_only})")

    # 1. Settle pending bets from previous days
    settler = BetSettlementEngine()
    try:
        asyncio.run(settler.settle_pending_bets("ncaab"))
        asyncio.run(settler.settle_pending_bets("nba"))
    except Exception as e:
        logger.error(f"Error during bet settlement: {e}")

    # 2. Get performance metrics
    tracker = BetTracker()
    try:
        metrics = tracker.get_performance_metrics()
        logger.info(
            f"Retrieved metrics: {metrics['wins']}-{metrics['losses']} ({metrics['win_rate']:.1%})"
        )
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        metrics = {}

    # 3. Run orchestrated analysis (structured data + agent enrichment)
    data = None
    try:
        data = run_orchestrated_analysis()
        logger.info(
            f"Orchestrated analysis done: {data['total_game_count']} games, "
            f"{len(data['picks'])} picks (max {data['max_picks']})"
        )
    except Exception as e:
        logger.error(f"Orchestrated analysis failed, falling back to legacy: {e}")

    # 4. Format and send
    if data and data.get("picks") is not None:
        # ── Orchestrator path (primary) ──
        if picks_only:
            formatted = ReportFormatter.format_picks_only_live(data)
        else:
            formatted = ReportFormatter.format_live_report(data, metrics=metrics)
        ok = telegram.send_message(formatted)
    else:
        # ── Legacy fallback ──
        logger.warning("Using legacy capture_analysis() fallback")
        raw = capture_analysis()
        if picks_only:
            formatted = ReportFormatter.format_picks_only(raw)
            ok = telegram.send_message(formatted)
        else:
            formatted = ReportFormatter.format_full_report(raw, metrics=metrics)
            ok = telegram.send_report(formatted, label=label)

    if ok:
        logger.info(f"{label} report sent successfully")
    else:
        logger.error(f"{label} report send FAILED")

    # 5. Player props (separate Telegram message)
    try:
        prop_data = run_prop_analysis_pipeline("nba")
        if prop_data and prop_data.get("best_props"):
            prop_msg = ReportFormatter.format_prop_report(prop_data)
            prop_ok = telegram.send_message(prop_msg)
            if prop_ok:
                logger.info(
                    f"Props report sent: {prop_data['positive_ev_count']} +EV props"
                )
            else:
                logger.error("Props report send FAILED")
        else:
            logger.info("No +EV props found — skipping prop report")
    except Exception as e:
        logger.error(f"Prop analysis/send failed (non-fatal): {e}")

    # 6. DvP analysis (separate Telegram message)
    try:
        dvp_data = run_dvp_analysis_pipeline()
        if dvp_data and dvp_data.get("high_value_count", 0) > 0:
            dvp_msg = ReportFormatter.format_dvp_report(dvp_data)
            dvp_ok = telegram.send_message(dvp_msg)
            if dvp_ok:
                logger.info(
                    f"DvP report sent: {dvp_data['high_value_count']} HIGH VALUE plays"
                )
            else:
                logger.error("DvP report send FAILED")
        else:
            logger.info("No HIGH VALUE DvP plays — skipping DvP report")
    except Exception as e:
        logger.error(f"DvP analysis/send failed (non-fatal): {e}")

    return ok


# ---------------------------------------------------------------------------
# Scheduler (daemon mode)
# ---------------------------------------------------------------------------


def _parse_cron_hour(cron_expr: str) -> int:
    """Extract the hour from a simple 'M H * * *' cron expression."""
    parts = cron_expr.strip().split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    raise ValueError(f"Cannot parse hour from cron expression: {cron_expr!r}")


def _parse_cron_minute(cron_expr: str) -> int:
    """Extract the minute from a simple 'M H * * *' cron expression."""
    parts = cron_expr.strip().split()
    if len(parts) >= 1:
        try:
            return int(parts[0])
        except ValueError:
            pass
    raise ValueError(f"Cannot parse minute from cron expression: {cron_expr!r}")


def run_daemon(picks_only: bool = False) -> None:
    """
    Run as a persistent scheduler. Fires three times daily per .env config.
    Handles SIGTERM/SIGINT gracefully.
    """
    try:
        import schedule
        import time
        import pytz
    except ImportError:
        logger.error(
            "Missing packages: pip install schedule pytz\n"
            "Or run: pip install -r backend/requirements.txt"
        )
        sys.exit(1)

    tz = pytz.timezone(settings.TELEGRAM_TIMEZONE)

    # Parse schedule times from .env
    schedule_times = []
    for label, cron_expr in [
        ("MORNING", settings.TELEGRAM_CRON_MORNING),
        ("AFTERNOON", settings.TELEGRAM_CRON_AFTERNOON),
        ("EVENING", settings.TELEGRAM_CRON_EVENING),
    ]:
        try:
            h = _parse_cron_hour(cron_expr)
            m = _parse_cron_minute(cron_expr)
            time_str = f"{h:02d}:{m:02d}"
            schedule_times.append((label, time_str))
        except ValueError as e:
            logger.warning(f"Skipping {label}: {e}")

    if not schedule_times:
        logger.error("No valid schedule times found. Check TELEGRAM_CRON_* in .env")
        sys.exit(1)

    for label, time_str in schedule_times:
        schedule.every().day.at(time_str).do(send_report, picks_only=picks_only)
        logger.info(
            f"Scheduled {label} report at {time_str} {settings.TELEGRAM_TIMEZONE}"
        )

    # Graceful shutdown
    _running = [True]

    def _shutdown(sig, frame):
        logger.info("Shutdown signal received — stopping scheduler")
        _running[0] = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Telegram cron daemon started. Ctrl+C to stop.")

    while _running[0]:
        schedule.run_pending()
        time.sleep(30)

    logger.info("Telegram cron daemon stopped.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Send betting reports to Telegram")
    parser.add_argument(
        "--send-now",
        action="store_true",
        help="Send report immediately and exit",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as persistent 3x-daily scheduler",
    )
    parser.add_argument(
        "--picks-only",
        action="store_true",
        help="Send compact picks summary instead of full report",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test ping to verify bot token and chat ID",
    )

    args = parser.parse_args()

    if args.test:
        telegram = TelegramService()
        ok = telegram.test_connection()
        sys.exit(0 if ok else 1)

    if args.send_now:
        ok = send_report(picks_only=args.picks_only)
        sys.exit(0 if ok else 1)

    if args.daemon:
        run_daemon(picks_only=args.picks_only)
        sys.exit(0)

    # Default: show help if no args given
    parser.print_help()


if __name__ == "__main__":
    main()
