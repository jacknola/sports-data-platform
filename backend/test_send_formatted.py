import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.telegram_service import TelegramService
from app.services.report_formatter import ReportFormatter
from telegram_cron import capture_analysis

print("Running analysis...")
raw_output = capture_analysis()
formatted = ReportFormatter.format_picks_only(raw_output)

print("Sending to Telegram...")
ts = TelegramService()
ok = ts.send_message(formatted)
print(f"Sent ok? {ok}")
