"""
SheetsService — push 2D array data to a Google Sheet tab.

Authentication
──────────────
  Uses a Google service account JSON key file.
  Path configured via GOOGLE_SERVICE_ACCOUNT_PATH environment variable.
  The service account email must be shared on the target spreadsheet
  with at least Editor permissions.

Usage
─────
  service = SheetsService()

  # Single call — clear + write
  header  = [["Date", "Bankroll", "PnL", "Bets", "Wins"]]
  service.push(header + data_rows, sheet_name="Backtest Equity Curve")

  # Append to existing data (clear=False)
  service.push(new_rows, sheet_name="Daily Bets", clear=False)

If credentials are not configured the service logs a warning and returns
False rather than raising, consistent with the platform's graceful fallback.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from app.config import settings

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


class SheetsService:
    """Write 2D array data to Google Sheets using a service account."""

    def __init__(
        self,
        service_account_path: str | None = None,
        spreadsheet_id: str | None = None,
    ) -> None:
        self._sa_path = Path(
            service_account_path or settings.GOOGLE_SERVICE_ACCOUNT_PATH or ""
        )
        self._spreadsheet_id = spreadsheet_id or settings.GOOGLE_SPREADSHEET_ID
        self._client: gspread.Client | None = None

    # ── Public interface ──────────────────────────────────────────────────────

    def push(
        self,
        payload: list[list[Any]],
        sheet_name: str = "Sheet1",
        clear: bool = True,
    ) -> bool:
        """
        Write a 2D array to the named sheet tab.

        Parameters
        ----------
        payload :    List of rows; first row is typically the header.
        sheet_name : Tab name within the spreadsheet.
        clear :      If True (default), clears all existing content first.

        Returns
        -------
        True on success, False on any failure (error is logged).
        """
        if not self._spreadsheet_id:
            logger.warning(
                "SheetsService: GOOGLE_SPREADSHEET_ID not set — skipping push."
            )
            return False

        if not self._sa_path.exists():
            logger.warning(
                f"SheetsService: service account file not found at '{self._sa_path}'. "
                "Set GOOGLE_SERVICE_ACCOUNT_PATH in .env."
            )
            return False

        try:
            client     = self._get_client()
            workbook   = client.open_by_key(self._spreadsheet_id)

            try:
                sheet = workbook.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                sheet = workbook.add_worksheet(
                    title=sheet_name, rows=10_000, cols=50
                )
                logger.info(f"Created new sheet tab: '{sheet_name}'")

            if clear:
                sheet.clear()

            # Batch write starting from A1
            sheet.update("A1", payload)
            logger.info(f"Pushed {len(payload):,} rows → '{sheet_name}'")
            return True

        except gspread.exceptions.APIError as exc:
            logger.error(f"Google Sheets API error: {exc}")
            return False
        except Exception as exc:
            logger.error(f"SheetsService.push failed: {exc}")
            return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            creds = Credentials.from_service_account_file(
                str(self._sa_path), scopes=_SCOPES
            )
            self._client = gspread.authorize(creds)
        return self._client
