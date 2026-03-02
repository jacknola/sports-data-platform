"""
sync_betslip.py — Register placed bets from Google Sheets BetSlip tab.

Usage:
    python3 backend/sync_betslip.py               # sync today's BetSlip
    python3 backend/sync_betslip.py --date 2026-03-03
    python3 backend/sync_betslip.py --settle       # settle won/lost from results

Workflow:
    1. Open the BetSlip tab in Google Sheets
    2. Find rows where '✓ Placed?' == 'Y' (or 'y') and 'Bet ID' is empty
    3. Call BetTracker.save_bet() for each → returns a Bet ID
    4. Write the Bet ID back to the sheet (column M)
    5. Log a summary

When you want to settle bets:
    - Update the 'Status' column (col N) in the sheet: won / lost / push
    - Run with --settle flag
    - The script reads those rows and calls BetTracker.update_bet_result()
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.services.bet_tracker import BetTracker
from app.services.google_sheets import GoogleSheetsService
from app.config import settings

# ── Column positions in BetSlip (0-indexed) ──
COL_DATE     = 0
COL_GAME     = 1
COL_PLAYER   = 2
COL_MARKET   = 3
COL_LINE     = 4
COL_SIDE     = 5
COL_ODDS     = 6
COL_BOOK     = 7
COL_EDGE     = 8
COL_KELLY    = 9
COL_EV_CLASS = 10
COL_PLACED   = 11   # ✓ Placed? — user fills Y here
COL_BET_ID   = 12   # Bet ID — written back by this script
COL_STATUS   = 13   # Status — won/lost/push (user or script fills)
COL_PL       = 14   # P/L — calculated on settlement
COL_NOTES    = 15


def _parse_odds(odds_str: Any) -> int:
    """Convert '+150' or '-110' string back to int."""
    try:
        s = str(odds_str).strip().replace("+", "")
        return int(float(s))
    except (ValueError, TypeError):
        return -110


def _row_to_address(row_idx: int, col_idx: int) -> str:
    """Convert 0-based row/col to A1 notation (row_idx is 0-based data row, +2 for header)."""
    col_letter = chr(65 + col_idx)
    return f"{col_letter}{row_idx + 2}"  # +2: 1-based + header row


def sync_placed_bets(spreadsheet_id: str, tab_name: str = "BetSlip") -> int:
    """
    Read BetSlip tab, register rows where '✓ Placed?' = 'Y' and Bet ID is empty.
    Writes generated Bet IDs back to column M.
    Returns count of newly registered bets.
    """
    sheets_svc = GoogleSheetsService()
    tracker = BetTracker()

    if not sheets_svc.client:
        logger.error("Google Sheets not configured — check service account credentials")
        return 0

    try:
        spreadsheet = sheets_svc.client.open_by_key(spreadsheet_id)
        try:
            ws = spreadsheet.worksheet(tab_name)
        except Exception:
            logger.warning(f"Tab '{tab_name}' not found in spreadsheet")
            return 0

        all_rows = ws.get_all_values()
        if len(all_rows) < 2:
            logger.info("BetSlip is empty")
            return 0

        header = all_rows[0]
        data_rows = all_rows[1:]

        registered = 0
        updates: List[Dict[str, Any]] = []

        for i, row in enumerate(data_rows):
            # Pad short rows
            while len(row) < 16:
                row.append("")

            placed = row[COL_PLACED].strip().upper()
            existing_bet_id = row[COL_BET_ID].strip()

            if placed != "Y":
                continue
            if existing_bet_id:
                logger.debug(f"Row {i+2}: already registered as {existing_bet_id}")
                continue

            # Build bet_data for BetTracker.save_bet()
            game_raw = row[COL_GAME] or ""
            player_side = row[COL_PLAYER] or ""
            market = row[COL_MARKET] or ""
            line_raw = row[COL_LINE]
            side = row[COL_SIDE] or ""
            odds = _parse_odds(row[COL_ODDS])
            book = row[COL_BOOK] or ""
            edge_raw = row[COL_EDGE]
            kelly_raw = row[COL_KELLY]
            date_str = row[COL_DATE] or datetime.now().strftime("%Y-%m-%d")

            try:
                line = float(str(line_raw).replace(",", "."))
            except (ValueError, TypeError):
                line = 0.0

            try:
                edge = float(str(edge_raw)) / 100.0  # sheet stores as pct
            except (ValueError, TypeError):
                edge = 0.0

            try:
                bet_size = float(str(kelly_raw).replace(",", "."))
            except (ValueError, TypeError):
                bet_size = 0.0

            # Derive sport from market label
            sport = "nba"
            if "NCAAB" in market.upper():
                sport = "ncaab"

            # game_id: stable key for this wager
            safe_game = game_raw.replace(" ", "_").replace("@", "vs")
            safe_player = player_side.replace(" ", "_")
            game_id = f"{sport}_{safe_game}_{safe_player}_{side}_{date_str}".lower()

            bet_data = {
                "date": date_str,
                "game_id": game_id,
                "sport": sport,
                "side": f"{player_side} {side}".strip(),
                "market": market,
                "odds": odds,
                "line": line,
                "edge": edge,
                "bet_size": bet_size,
                "book": book,
            }

            try:
                bet_id = tracker.save_bet(bet_data)
                updates.append({
                    "row_idx": i,
                    "bet_id": bet_id,
                    "cell": _row_to_address(i, COL_BET_ID),
                    "status_cell": _row_to_address(i, COL_STATUS),
                })
                registered += 1
                logger.info(f"Registered: {player_side} {side} @ {odds} → Bet ID {bet_id}")
            except Exception as e:
                logger.error(f"Failed to register bet row {i+2}: {e}")

        # Write Bet IDs back to sheet
        if updates:
            batch_data = []
            for u in updates:
                batch_data.append({"range": u["cell"], "values": [[u["bet_id"]]]})
                batch_data.append({"range": u["status_cell"], "values": [["pending"]]})
            ws.batch_update(batch_data)
            logger.info(f"Wrote {len(updates)} Bet IDs back to BetSlip tab")

        logger.info(f"sync_betslip: {registered} new bets registered")
        return registered

    except Exception as e:
        logger.error(f"sync_betslip failed: {e}")
        return 0


def settle_bets(spreadsheet_id: str, tab_name: str = "BetSlip") -> int:
    """
    Read BetSlip rows where Status = won/lost/push and Bet ID is set.
    Call BetTracker.update_bet_result() and write P/L back to sheet.
    Returns count of settled bets.
    """
    sheets_svc = GoogleSheetsService()
    tracker = BetTracker()

    if not sheets_svc.client:
        logger.error("Google Sheets not configured")
        return 0

    try:
        spreadsheet = sheets_svc.client.open_by_key(spreadsheet_id)
        ws = spreadsheet.worksheet(tab_name)
        all_rows = ws.get_all_values()
        if len(all_rows) < 2:
            return 0

        data_rows = all_rows[1:]
        settled = 0
        updates: List[Dict[str, Any]] = []

        for i, row in enumerate(data_rows):
            while len(row) < 16:
                row.append("")

            bet_id = row[COL_BET_ID].strip()
            status = row[COL_STATUS].strip().lower()
            placed = row[COL_PLACED].strip().upper()

            if not bet_id or placed != "Y":
                continue
            if status not in ("won", "lost", "push", "win", "loss", "w", "l"):
                continue
            # Normalize
            norm = {"win": "won", "w": "won", "loss": "lost", "l": "lost"}.get(status, status)

            # Compute P/L
            odds = _parse_odds(row[COL_ODDS])
            try:
                bet_size = float(str(row[COL_KELLY]).replace(",", "."))
            except (ValueError, TypeError):
                bet_size = 0.0

            if norm == "won":
                if odds > 0:
                    pl = round(bet_size * (odds / 100.0), 2)
                else:
                    pl = round(bet_size * (100.0 / abs(odds)), 2)
            elif norm == "push":
                pl = 0.0
            else:
                pl = -bet_size

            try:
                tracker.update_bet_result(bet_id, norm)
                updates.append({
                    "pl_cell": _row_to_address(i, COL_PL),
                    "status_cell": _row_to_address(i, COL_STATUS),
                    "pl": pl,
                    "status": norm,
                })
                settled += 1
                logger.info(f"Settled {bet_id}: {norm}  P/L ${pl:+.2f}")
            except Exception as e:
                logger.error(f"Failed to settle {bet_id}: {e}")

        if updates:
            batch_data = []
            for u in updates:
                batch_data.append({"range": u["pl_cell"], "values": [[u["pl"]]]})
                batch_data.append({"range": u["status_cell"], "values": [[u["status"]]]})
            ws.batch_update(batch_data)

        logger.info(f"Settled {settled} bets")
        return settled

    except Exception as e:
        logger.error(f"settle_bets failed: {e}")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync BetSlip from Google Sheets")
    parser.add_argument("--settle", action="store_true", help="Settle won/lost bets from sheet")
    parser.add_argument("--tab", default="BetSlip", help="Sheet tab name")
    parser.add_argument(
        "--sheet-id",
        default=getattr(settings, "GOOGLE_SPREADSHEET_ID", None),
        help="Google Sheets ID (defaults to settings.GOOGLE_SPREADSHEET_ID)",
    )
    args = parser.parse_args()

    sheet_id = args.sheet_id
    if not sheet_id:
        # fallback to GOOGLE_SPREADSHEET_ID
        sheet_id = getattr(settings, "GOOGLE_SPREADSHEET_ID", None)
    if not sheet_id:
        logger.error("No spreadsheet ID — set GOOGLE_SHEETS_ID in .env or pass --sheet-id")
        sys.exit(1)

    if args.settle:
        n = settle_bets(sheet_id, args.tab)
        print(f"Settled {n} bets")
    else:
        n = sync_placed_bets(sheet_id, args.tab)
        print(f"Registered {n} new bets from BetSlip")
