"""
Telegram Bot Service

Sends betting reports and alerts to a Telegram chat/channel.

Features:
- Auto-chunks messages at 4096 chars (Telegram API limit)
- HTML parse mode (handles +/- betting symbols cleanly)
- Rate limiting: 1 second between chunks to same chat
- Retry logic: 3 attempts with exponential backoff
- Structured report and picks-only send methods
"""

import time
import asyncio
from typing import Optional
import httpx
from loguru import logger

from app.config import settings


# Telegram API hard limit per message
_TELEGRAM_MAX_LENGTH = 4096
# Minimum seconds between messages to same chat (avoid rate limit)
_RATE_LIMIT_DELAY = 1.0
# Retry attempts on HTTP failure
_MAX_RETRIES = 3


class TelegramService:
    """Sends messages and reports via the Telegram Bot API."""

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID

        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")
        if not self.chat_id:
            raise ValueError(
                "TELEGRAM_CHAT_ID is not set in .env — "
                "message @userinfobot on Telegram to get your ID"
            )

        self._base_url = f"https://api.telegram.org/bot{self.token}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a text message, auto-chunking if over 4096 chars.

        Args:
            text: Message content (HTML tags supported)
            parse_mode: 'HTML' or 'Markdown' (HTML recommended)

        Returns:
            True if all chunks sent successfully
        """
        chunks = self._chunk(text)
        success = True

        for i, chunk in enumerate(chunks):
            ok = self._send_chunk(chunk, parse_mode)
            if not ok:
                success = False
                logger.error(f"Failed to send chunk {i+1}/{len(chunks)}")
            if i < len(chunks) - 1:
                time.sleep(_RATE_LIMIT_DELAY)

        return success

    def send_report(self, report_text: str, label: str = "REPORT") -> bool:
        """
        Send a full betting report with header and footer.

        Args:
            report_text: Raw report content (plain text or pre-formatted HTML)
            label: Report type label shown in header (e.g. 'MORNING', 'EVENING')

        Returns:
            True if sent successfully
        """
        from datetime import datetime
        import pytz

        tz = pytz.timezone(settings.TELEGRAM_TIMEZONE)
        now = datetime.now(tz).strftime("%a %b %-d, %Y · %-I:%M %p %Z")

        header = (
            f"<b>📊 SPORTS BETTING REPORT — {label}</b>\n"
            f"<i>{now}</i>\n"
            f"{'─' * 32}\n\n"
        )
        footer = (
            f"\n{'─' * 32}\n"
            f"<i>Track CLV on every bet. Positive CLV = confirmed edge.</i>"
        )

        full_message = header + report_text + footer
        return self.send_message(full_message)

    def send_picks_summary(self, plays: list) -> bool:
        """
        Send a compact ranked picks table.

        Args:
            plays: List of dicts with keys: rank, bet_on, odds, edge, matchup, signals

        Returns:
            True if sent successfully
        """
        if not plays:
            return self.send_message("<b>No qualifying plays today.</b>")

        lines = ["<b>🎯 TOP PLAYS</b>\n"]
        for p in plays:
            signals = ", ".join(p.get("signals", [])) or "Model only"
            edge = p.get("edge", 0)
            emoji = "🟢" if edge >= 0.05 else "🟡"
            lines.append(
                f"{emoji} <b>#{p['rank']} {p['bet_on']} ({p['odds']:+d})</b>\n"
                f"   {p['matchup']}\n"
                f"   Edge: <code>{edge*100:+.2f}%</code> | {signals}\n"
            )

        return self.send_message("\n".join(lines))

    def send_alert(self, title: str, body: str) -> bool:
        """Send an urgent sharp-money or steam alert."""
        text = f"<b>⚡ ALERT: {title}</b>\n\n{body}"
        return self.send_message(text)

    def test_connection(self) -> bool:
        """Send a test ping to verify bot token and chat ID are correct."""
        ok = self.send_message(
            "<b>✅ Telegram bot connected.</b>\n"
            "Reports will arrive 3× daily. Use /send-report for on-demand delivery."
        )
        if ok:
            logger.info("Telegram connection test passed")
        else:
            logger.error("Telegram connection test failed")
        return ok

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_chunk(self, text: str, parse_mode: str) -> bool:
        """POST a single chunk to the Telegram sendMessage endpoint with retries."""
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(url, json=payload)

                if resp.status_code == 200:
                    return True

                # Telegram returns 400 for bad parse_mode — retry as plain text
                if resp.status_code == 400:
                    logger.warning(
                        f"Telegram 400 on attempt {attempt}: {resp.text[:200]}"
                    )
                    if parse_mode != "":
                        payload["parse_mode"] = ""
                        continue

                logger.warning(
                    f"Telegram HTTP {resp.status_code} on attempt {attempt}: "
                    f"{resp.text[:200]}"
                )

            except httpx.RequestError as e:
                logger.warning(f"Telegram request error attempt {attempt}: {e}")

            if attempt < _MAX_RETRIES:
                backoff = 2 ** attempt
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)

        return False

    @staticmethod
    def _chunk(text: str) -> list[str]:
        """Split text into chunks of at most _TELEGRAM_MAX_LENGTH characters."""
        if len(text) <= _TELEGRAM_MAX_LENGTH:
            return [text]

        chunks = []
        while text:
            if len(text) <= _TELEGRAM_MAX_LENGTH:
                chunks.append(text)
                break
            # Try to split on a newline boundary near the limit
            split_at = text.rfind("\n", 0, _TELEGRAM_MAX_LENGTH)
            if split_at == -1:
                split_at = _TELEGRAM_MAX_LENGTH
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")

        return chunks
