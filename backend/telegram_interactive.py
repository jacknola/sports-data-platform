import sys
import os
from loguru import logger
import telebot

# Allow imports from backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.telegram_service import TelegramService
from app.services.report_formatter import ReportFormatter
from app.services.bet_tracker import BetTracker
from app.services.analysis_runner import (
    capture_analysis,
    run_orchestrated_analysis,
    run_prop_analysis_pipeline,
)

# Initialize Telebot
if not settings.TELEGRAM_BOT_TOKEN:
    logger.error("No TELEGRAM_BOT_TOKEN found in .env")
    sys.exit(1)

bot = telebot.TeleBot(settings.TELEGRAM_BOT_TOKEN)

# Use our existing service to send formatted chunked HTML since Telebot's built in send_message can fail on large texts
telegram_service = TelegramService()


def check_auth(message):
    """Ensure the user talking to the bot is the authorized admin"""
    if str(message.chat.id) != settings.TELEGRAM_CHAT_ID:
        logger.warning(f"Unauthorized access attempt from chat_id: {message.chat.id}")
        bot.reply_to(message, "Unauthorized user.")
        return False
    return True


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    if not check_auth(message):
        return
    help_text = (
        "🤖 <b>Sports Betting AI Bot</b>\n\n"
        "Commands available:\n"
        "<code>/analyze</code> - Run full analysis and get the complete report\n"
        "<code>/picks</code> - Run analysis and get only the top plays\n"
        "<code>/metrics</code> - Get current Win/Loss record and ROI\n"
        "<code>/ping</code> - Check if bot is alive\n"
    )
    telegram_service.send_message(help_text)


@bot.message_handler(commands=["ping"])
def send_ping(message):
    if not check_auth(message):
        return
    telegram_service.send_message("<b>✅ Pong! Bot is alive and listening.</b>")


@bot.message_handler(commands=["metrics"])
def send_metrics(message):
    if not check_auth(message):
        return

    bot.reply_to(message, "Fetching metrics from database...")

    tracker = BetTracker()
    try:
        metrics = tracker.get_performance_metrics()

        wins = metrics.get("wins", 0)
        losses = metrics.get("losses", 0)
        pushes = metrics.get("pushes", 0)
        units = metrics.get("units", 0.0)
        roi = metrics.get("roi", 0.0)
        win_rate = metrics.get("win_rate", 0.0)

        text = (
            f"📈 <b>PERFORMANCE METRICS</b>\n\n"
            f"Record: <b>{wins}-{losses}-{pushes}</b>\n"
            f"Win Rate: <b>{win_rate:.1%}</b>\n"
            f"Units: <b>{units:+.2f}u</b>\n"
            f"ROI: <b>{roi:.1%}</b>\n"
        )
        telegram_service.send_message(text)
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        telegram_service.send_message(f"❌ Error getting metrics: {e}")


@bot.message_handler(commands=["analyze"])
def send_analyze(message):
    if not check_auth(message):
        return

    msg = bot.reply_to(
        message,
        "⏳ Running full live analysis with orchestrator... This may take a minute.",
    )

    try:
        tracker = BetTracker()
        metrics = tracker.get_performance_metrics()

        # Primary: orchestrated analysis (structured + agent enrichment)
        try:
            data = run_orchestrated_analysis()
            formatted = ReportFormatter.format_live_report(data, metrics=metrics)
            telegram_service.send_message(formatted)
        except Exception as orch_err:
            logger.warning(f"Orchestrator failed, falling back to legacy: {orch_err}")
            raw_output = capture_analysis()
            formatted = ReportFormatter.format_full_report(raw_output, metrics=metrics)
            telegram_service.send_report(formatted, label="ON-DEMAND")

        # Player props (separate message)
        try:
            prop_data = run_prop_analysis_pipeline("nba")
            if prop_data and prop_data.get("best_props"):
                prop_msg = ReportFormatter.format_prop_report(prop_data)
                telegram_service.send_message(prop_msg)
        except Exception as prop_err:
            logger.warning(f"Prop analysis failed (non-fatal): {prop_err}")

        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        telegram_service.send_message(f"❌ Error during analysis: {e}")


@bot.message_handler(commands=["picks"])
def send_picks(message):
    if not check_auth(message):
        return

    logger.info("Received /picks command")
    msg = bot.reply_to(message, "⏳ Running live analysis...")

    try:
        tracker = BetTracker()
        metrics = tracker.get_performance_metrics()

        # Primary: orchestrated analysis with dynamic pick count
        try:
            data = run_orchestrated_analysis()
            formatted = ReportFormatter.format_live_report(data, metrics=metrics)
            logger.info(
                f"Orchestrated picks: {len(data.get('picks', []))} picks "
                f"from {data.get('total_game_count', 0)}-game slate"
            )
            telegram_service.send_message(formatted)
        except Exception as orch_err:
            logger.warning(f"Orchestrator failed, falling back to legacy: {orch_err}")
            raw_output = capture_analysis()
            formatted = ReportFormatter.format_picks_only(raw_output)
            telegram_service.send_message(formatted)

        # Player props (separate message)
        try:
            prop_data = run_prop_analysis_pipeline("nba")
            if prop_data and prop_data.get("best_props"):
                prop_msg = ReportFormatter.format_prop_report(prop_data)
                telegram_service.send_message(prop_msg)
        except Exception as prop_err:
            logger.warning(f"Prop analysis failed (non-fatal): {prop_err}")

        logger.info("Sent formatted message")
        bot.delete_message(message.chat.id, msg.message_id)
        logger.info("Deleted initial status message")
    except Exception as e:
        logger.error(f"Picks error: {e}", exc_info=True)
        telegram_service.send_message(f"❌ Error getting picks: {e}")


def main():
    logger.info("Starting interactive Telegram bot listener...")
    logger.info("Ready for commands: /analyze, /picks, /metrics")

    # Run the bot in polling mode
    bot.infinity_polling(timeout=10, long_polling_timeout=5)


if __name__ == "__main__":
    import sys

    if "--help" in sys.argv:
        print(
            "Run `python3 backend/telegram_interactive.py` to start the interactive bot."
        )
        sys.exit(0)
    main()
