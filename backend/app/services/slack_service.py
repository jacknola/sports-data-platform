"""
Slack Webhook Service

Sends betting reports and picks to a Slack channel via Incoming Webhook.

Features:
- Rich Block Kit formatting for game-by-game sections
- Auto-chunks messages exceeding Slack's 50-block limit
- Retry logic with exponential backoff
"""

import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.config import settings


_MAX_BLOCKS_PER_MESSAGE = 50
_MAX_RETRIES = 3


class SlackService:
    """Sends messages to Slack via Incoming Webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL
        if not self.webhook_url:
            raise ValueError(
                "SLACK_WEBHOOK_URL is not set in .env — "
                "create one at https://api.slack.com/messaging/webhooks"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_blocks(self, blocks: List[Dict[str, Any]], text: str = "") -> bool:
        """Send a Block Kit message, auto-chunking if over 50 blocks.

        Args:
            blocks: List of Slack Block Kit block dicts
            text: Fallback plain-text (shown in notifications)

        Returns:
            True if all chunks sent successfully
        """
        if not blocks:
            return True

        chunks = self._chunk_blocks(blocks)
        success = True

        for i, chunk in enumerate(chunks):
            payload: Dict[str, Any] = {"blocks": chunk}
            if i == 0 and text:
                payload["text"] = text

            ok = self._post(payload)
            if not ok:
                success = False
                logger.error(f"Failed to send Slack chunk {i + 1}/{len(chunks)}")
            if i < len(chunks) - 1:
                time.sleep(1.0)

        return success

    def send_text(self, text: str) -> bool:
        """Send a simple plain-text message."""
        return self._post({"text": text})

    def test_connection(self) -> bool:
        """Send a test ping to verify webhook works."""
        ok = self.send_text("✅ Slack bot connected. NBA picks will arrive here.")
        if ok:
            logger.info("Slack connection test passed")
        else:
            logger.error("Slack connection test FAILED")
        return ok

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, payload: Dict[str, Any]) -> bool:
        """POST a payload to the Slack webhook with retries."""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(self.webhook_url, json=payload)

                if resp.status_code == 200:
                    return True

                logger.warning(
                    f"Slack HTTP {resp.status_code} on attempt {attempt}: "
                    f"{resp.text[:200]}"
                )
            except httpx.RequestError as e:
                logger.warning(f"Slack request error attempt {attempt}: {e}")

            if attempt < _MAX_RETRIES:
                backoff = 2 ** attempt
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)

        return False

    @staticmethod
    def _chunk_blocks(blocks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split blocks into chunks of at most _MAX_BLOCKS_PER_MESSAGE."""
        if len(blocks) <= _MAX_BLOCKS_PER_MESSAGE:
            return [blocks]

        chunks: List[List[Dict[str, Any]]] = []
        for i in range(0, len(blocks), _MAX_BLOCKS_PER_MESSAGE):
            chunks.append(blocks[i : i + _MAX_BLOCKS_PER_MESSAGE])
        return chunks
