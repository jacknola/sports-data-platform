Scaffold the complete Telegram integration for this platform.

This command builds three things:
1. `backend/app/services/telegram_service.py` — the Telegram bot service
2. `backend/app/services/report_formatter.py` — formats analysis output as Telegram-ready HTML
3. `backend/telegram_cron.py` — standalone cron runner (sends 3x daily reports)

Read the existing codebase first:
- `backend/run_ncaab_analysis.py` — understand report output format
- `backend/app/config.py` — understand Settings structure
- `backend/.env` — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID values

**telegram_service.py requirements:**
- Class `TelegramService` with async `send_message(text, parse_mode='HTML')`
- Auto-chunks messages at 4096 chars (Telegram API limit)
- `send_report(report_text)` — sends report with header/footer
- `send_picks_summary(plays)` — sends just the ranked picks table
- Rate limiting: 1 message/second minimum delay between chunks
- Retry logic: 3 attempts with exponential backoff on HTTP errors
- Load token/chat_id from `settings` (config.py)

**report_formatter.py requirements:**
- `format_ncaab_report(analysis_output: str) -> str` — converts raw text output to HTML
- Bold headers with `<b>`, monospace tables with `<code>`
- Adds emoji indicators: 🟢 STRONG PLAY, 🟡 PLAY, ⚪ PASS
- Adds timestamp and bankroll exposure at top
- `format_picks_only(plays: list) -> str` — compact version (just ranked plays)

**telegram_cron.py requirements:**
- Uses `schedule` library (or APScheduler) for 3x daily sends
- Reads cron times from config: TELEGRAM_CRON_MORNING, _AFTERNOON, _EVENING
- Runs `run_analysis()` from run_ncaab_analysis.py, captures stdout
- Formats and sends via TelegramService
- Logs all sends to `logs/telegram_cron.log`
- Handles graceful shutdown on SIGTERM

**Cron setup instructions to display after scaffolding:**
```bash
# Option A: System cron (simplest)
crontab -e
# Add these 3 lines (adjust times to your timezone):
0 9  * * * cd /home/user/sports-data-platform && python backend/telegram_cron.py --send-now >> logs/cron.log 2>&1
0 14 * * * cd /home/user/sports-data-platform && python backend/telegram_cron.py --send-now >> logs/cron.log 2>&1
0 19 * * * cd /home/user/sports-data-platform && python backend/telegram_cron.py --send-now >> logs/cron.log 2>&1

# Option B: Run as persistent scheduler (stays running, handles its own schedule)
python backend/telegram_cron.py --daemon
```

Add `python-telegram-bot` and `APScheduler` to requirements.txt.
Update `backend/app/services/__init__.py` to export TelegramService.

After creating all files, show a checklist of what was created and next steps.
