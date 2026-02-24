"""
Google Sheets Export Service — Daily Picks

Exports NCAAB, NBA, and Player Prop analysis to Google Sheets with
separate tabs per sport. Uses gspread + service account auth.

Tabs:
  - Props        — All player props ranked by confidence/edge
  - NBA          — NBA game picks with spreads, totals, ML
  - NCAAB        — NCAAB sharp money picks
  - Summary      — Daily overview (auto-generated)
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger


# ═══════════════════════════════════════════════════════════════════════
# Stat display labels (mirrors slack_formatter)
# ═══════════════════════════════════════════════════════════════════════

_STAT_DISPLAY = {
    "points": "PTS", "rebounds": "REB", "assists": "AST",
    "threes": "3PM", "blocks": "BLK", "steals": "STL",
    "pts+reb+ast": "PRA", "pts+reb": "P+R", "pts+ast": "P+A",
    "reb+ast": "R+A", "turnovers": "TO", "stl+blk": "S+B",
}


def _fmt_odds(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def _confidence_label(edge: float, ev_class: str) -> str:
    if ev_class == "strong_play" or edge >= 0.08:
        return "HIGH"
    elif ev_class == "good_play" or edge >= 0.05:
        return "MEDIUM"
    elif ev_class == "lean" or edge >= 0.03:
        return "LOW"
    return "SPECULATIVE"


class GoogleSheetsService:
    """Service for exporting daily picks to Google Sheets."""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, credentials_path: Optional[str] = None):
        from app.config import settings

        self.client: Optional[gspread.Client] = None
        creds_path = credentials_path or settings.GOOGLE_SERVICE_ACCOUNT_PATH
        if creds_path:
            self._init_client(creds_path)
        else:
            logger.warning(
                "Google Sheets not configured. "
                "Set GOOGLE_SERVICE_ACCOUNT_PATH in .env"
            )

    def _init_client(self, credentials_path: str) -> None:
        """Initialize gspread client from service account JSON."""
        try:
            creds = Credentials.from_service_account_file(
                credentials_path, scopes=self.SCOPES
            )
            self.client = gspread.authorize(creds)
            logger.info("Google Sheets client initialized")
        except FileNotFoundError:
            logger.error(
                f"Service account file not found: {credentials_path}"
            )
        except Exception as e:
            logger.error(f"Failed to init Google Sheets client: {e}")

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    # ───────────────────────────────────────────────────────────────
    # Worksheet helpers
    # ───────────────────────────────────────────────────────────────

    def _get_or_create_worksheet(
        self,
        spreadsheet: gspread.Spreadsheet,
        name: str,
        rows: int = 200,
        cols: int = 20,
    ) -> gspread.Worksheet:
        """Get existing worksheet or create a new one."""
        try:
            ws = spreadsheet.worksheet(name)
            ws.clear()
            return ws
        except gspread.WorksheetNotFound:
            return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)

    def _batch_write(
        self,
        worksheet: gspread.Worksheet,
        headers: List[str],
        rows: List[List[Any]],
    ) -> int:
        """Write headers + data rows in a single batch update."""
        all_data = [headers] + rows
        worksheet.update(
            range_name=f"A1:{chr(64 + len(headers))}{len(all_data)}",
            values=all_data,
        )
        # Bold + freeze header row
        worksheet.format("1:1", {"textFormat": {"bold": True}})
        worksheet.freeze(rows=1)
        return len(rows)

    # ───────────────────────────────────────────────────────────────
    # Props export
    # ───────────────────────────────────────────────────────────────

    def export_props(
        self,
        spreadsheet_id: str,
        prop_data: Dict[str, Any],
        tab_name: str = "Props",
    ) -> Dict[str, Any]:
        """Export all analyzed props to a 'Props' tab, ranked by edge.

        Args:
            spreadsheet_id: Google Sheets ID
            prop_data: Result from run_prop_analysis()
            tab_name: Worksheet name

        Returns:
            Status dict with rows_written count
        """
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name)

            headers = [
                "Date", "Player", "Team", "Opponent", "Game",
                "Stat", "Line", "Side", "Odds", "Projected",
                "Edge %", "Bayesian P", "EV Class", "Confidence",
                "Kelly %", "Sharp Signals", "Best Book",
                "Books #", "Over Odds", "Under Odds",
            ]

            # Use ALL analyzed props, sorted by edge descending
            all_props = prop_data.get("props", [])
            all_props.sort(
                key=lambda x: x.get("bayesian_edge", 0), reverse=True
            )

            today = datetime.now().strftime("%Y-%m-%d")
            rows: List[List[Any]] = []

            for p in all_props:
                stat_type = p.get("stat_type", "")
                stat_label = _STAT_DISPLAY.get(stat_type, stat_type.upper())
                best_side = p.get("best_side", "over").upper()
                odds = (
                    p.get("over_odds", -110)
                    if best_side == "OVER"
                    else p.get("under_odds", -110)
                )
                edge = p.get("bayesian_edge", 0)
                ev_class = p.get("ev_classification", "")
                best_book = (
                    p.get("best_over_book", "")
                    if best_side == "OVER"
                    else p.get("best_under_book", "")
                )
                home = p.get("home_team", "")
                away = p.get("away_team", "")
                game = f"{away} @ {home}" if home and away else ""
                signals = ", ".join(p.get("sharp_signals", []))

                rows.append([
                    today,
                    p.get("player_name", ""),
                    p.get("team", ""),
                    p.get("opponent", ""),
                    game,
                    stat_label,
                    p.get("line", 0),
                    best_side,
                    _fmt_odds(int(odds)),
                    round(p.get("projected_mean", 0), 1),
                    round(edge * 100, 2),
                    round(p.get("posterior_p", 0), 4),
                    ev_class.replace("_", " ").title() if ev_class else "",
                    _confidence_label(edge, ev_class),
                    round(p.get("kelly_fraction", 0) * 100, 2),
                    signals,
                    best_book,
                    p.get("books_offering", 0),
                    _fmt_odds(int(p.get("over_odds", -110))),
                    _fmt_odds(int(p.get("under_odds", -110))),
                ])

            written = self._batch_write(ws, headers, rows)
            logger.info(f"Exported {written} props to Google Sheets tab '{tab_name}'")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"Props export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # NBA export
    # ───────────────────────────────────────────────────────────────

    def export_nba(
        self,
        spreadsheet_id: str,
        predictions: List[Dict[str, Any]],
        bets: List[Dict[str, Any]],
        tab_name: str = "NBA",
    ) -> Dict[str, Any]:
        """Export NBA game predictions + bets to an 'NBA' tab."""
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name)

            headers = [
                "Date", "Home", "Away", "Book",
                "Home ML", "Away ML",
                "Spread", "Spread Odds",
                "Total", "Over Odds", "Under Odds",
                "Home Win %", "Away Win %",
                "Proj Spread", "Proj Total", "O/U Rec",
                "Best Bet", "Edge %", "Kelly %", "Bet Size",
            ]

            today = datetime.now().strftime("%Y-%m-%d")
            bet_lookup = {b.get("game_id", ""): b for b in bets}
            rows: List[List[Any]] = []

            for p in predictions:
                if "error" in p:
                    continue

                ev = p.get("expected_value", {})
                uo = p.get("underover_prediction", {})
                home = p.get("home_team", "")
                away = p.get("away_team", "")
                home_prob = p.get("home_win_probability", 0.5)
                away_prob = 1 - home_prob

                # Spread data
                spread_data = p.get("spread", {})
                spread_val = spread_data.get("home_point", "") if spread_data else ""
                spread_odds = (
                    _fmt_odds(spread_data.get("home_odds", -110))
                    if spread_data
                    else ""
                )

                # Total data
                total_data = p.get("total", {})
                total_val = total_data.get("point", "") if total_data else ""
                over_odds = (
                    _fmt_odds(total_data.get("over_odds", -110))
                    if total_data
                    else ""
                )
                under_odds = (
                    _fmt_odds(total_data.get("under_odds", -110))
                    if total_data
                    else ""
                )

                # Implied spread from probability
                proj_spread = round(
                    (home_prob - 0.5) * -26, 1
                ) if home_prob else ""

                # Best bet
                best_bet = ev.get("best_bet", "")
                best_side = home if best_bet == "home" else away
                home_edge = ev.get("home_ev", 0)
                away_edge = ev.get("away_ev", 0)
                best_edge = home_edge if best_bet == "home" else away_edge
                kelly = p.get("kelly_criterion", 0)

                # Match to bets list
                gid = f"NBA_{home}_{away}_{today.replace('-', '')}".replace(
                    " ", ""
                )
                bet = bet_lookup.get(gid, {})
                bet_size = bet.get("bet_size", 0) if bet else 0

                rows.append([
                    today,
                    home,
                    away,
                    p.get("book", ""),
                    _fmt_odds(ev.get("home_odds", 0)) if ev.get("home_odds") else "",
                    _fmt_odds(ev.get("away_odds", 0)) if ev.get("away_odds") else "",
                    spread_val,
                    spread_odds,
                    total_val,
                    over_odds,
                    under_odds,
                    round(home_prob * 100, 1),
                    round(away_prob * 100, 1),
                    proj_spread,
                    uo.get("total_points", "") if uo else "",
                    uo.get("recommendation", "").upper() if uo else "",
                    f"{best_side} ({best_bet.upper()})" if best_bet else "",
                    round(best_edge * 100, 2) if best_edge else "",
                    round(kelly * 100, 2) if kelly else "",
                    round(bet_size, 2) if bet_size else "",
                ])

            written = self._batch_write(ws, headers, rows)
            logger.info(f"Exported {written} NBA games to tab '{tab_name}'")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"NBA export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # NCAAB export
    # ───────────────────────────────────────────────────────────────

    def export_ncaab(
        self,
        spreadsheet_id: str,
        ncaab_data: Dict[str, Any],
        tab_name: str = "NCAAB",
    ) -> Dict[str, Any]:
        """Export NCAAB sharp money analysis to an 'NCAAB' tab."""
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name)

            headers = [
                "Date", "Home", "Away", "Conference",
                "Spread", "Total",
                "Pinnacle Home", "Pinnacle Away",
                "Retail Home", "Retail Away",
                "True Home %", "True Away %",
                "Blend Home %", "Blend Away %",
                "Home Edge %", "Away Edge %",
                "Sharp Side", "Signals", "Signal Conf %",
                "Pick", "Kelly %", "Bet Size",
            ]

            today = datetime.now().strftime("%Y-%m-%d")
            analyses = ncaab_data.get("game_analyses", [])
            bets = ncaab_data.get("bets", [])
            bets_lookup: Dict[str, Dict] = {}
            for b in bets:
                bets_lookup[b.get("game_id", "") + "_HOME"] = b
                bets_lookup[b.get("game_id", "") + "_AWAY"] = b

            rows: List[List[Any]] = []

            for a in analyses:
                game = a.get("game", {})
                home = game.get("home", "")
                away = game.get("away", "")
                gid = game.get("game_id", "")
                signals = a.get("sharp_signals", [])
                he = a.get("home_edge", 0)
                ae = a.get("away_edge", 0)

                # Find bet for this game
                bet = bets_lookup.get(gid + "_HOME") or bets_lookup.get(
                    gid + "_AWAY", {}
                )

                rows.append([
                    today,
                    home,
                    away,
                    game.get("conference", ""),
                    game.get("spread", 0),
                    game.get("total", ""),
                    _fmt_odds(game.get("pinnacle_home_odds", 0)),
                    _fmt_odds(game.get("pinnacle_away_odds", 0)),
                    _fmt_odds(game.get("retail_home_odds", 0)),
                    _fmt_odds(game.get("retail_away_odds", 0)),
                    round(a.get("true_home_prob", 0) * 100, 1),
                    round(a.get("true_away_prob", 0) * 100, 1),
                    round(a.get("blended_home_prob", 0) * 100, 1),
                    round(a.get("blended_away_prob", 0) * 100, 1),
                    round(he * 100, 2),
                    round(ae * 100, 2),
                    a.get("sharp_side", ""),
                    ", ".join(signals) if signals else "",
                    round(a.get("signal_confidence", 0) * 100, 1),
                    bet.get("side", "") if bet else "",
                    round(bet.get("portfolio_fraction_pct", 0), 2) if bet else "",
                    round(bet.get("bet_size_$", 0), 2) if bet else "",
                ])

            written = self._batch_write(ws, headers, rows)
            logger.info(f"Exported {written} NCAAB games to tab '{tab_name}'")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"NCAAB export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # Summary tab
    # ───────────────────────────────────────────────────────────────

    def export_summary(
        self,
        spreadsheet_id: str,
        ncaab_data: Optional[Dict] = None,
        nba_predictions: Optional[List[Dict]] = None,
        nba_bets: Optional[List[Dict]] = None,
        prop_data: Optional[Dict] = None,
        tab_name: str = "Summary",
    ) -> Dict[str, Any]:
        """Write a summary overview tab."""
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name, rows=30, cols=5)

            now = datetime.now().strftime("%Y-%m-%d %I:%M %p ET")
            ncaab_games = len((ncaab_data or {}).get("game_analyses", []))
            ncaab_bets = len((ncaab_data or {}).get("bets", []))
            nba_games = len([p for p in (nba_predictions or []) if "error" not in p])
            nba_bet_count = len(nba_bets or [])
            prop_total = (prop_data or {}).get("total_props", 0)
            prop_ev = (prop_data or {}).get("positive_ev_count", 0)

            total_exposure = (
                sum(b.get("bet_size_$", 0) for b in (ncaab_data or {}).get("bets", []))
                + sum(b.get("bet_size", 0) for b in (nba_bets or []))
            )

            summary_data = [
                ["Daily Picks Summary", now],
                ["", ""],
                ["Metric", "Value"],
                ["NCAAB Games", ncaab_games],
                ["NCAAB Bets", ncaab_bets],
                ["NBA Games", nba_games],
                ["NBA Bets", nba_bet_count],
                ["Props Scanned", prop_total],
                ["Props +EV", prop_ev],
                ["Total Exposure", f"${total_exposure:.0f}"],
                ["", ""],
                ["Generated by", "sports-data-platform"],
            ]

            ws.update(range_name=f"A1:B{len(summary_data)}", values=summary_data)
            ws.format("1:1", {"textFormat": {"bold": True, "fontSize": 14}})
            ws.format("3:3", {"textFormat": {"bold": True}})
            ws.freeze(rows=0)

            logger.info("Exported summary to Google Sheets")
            return {"status": "success", "tab": tab_name}

        except Exception as e:
            logger.error(f"Summary export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # Full daily export (all tabs)
    # ───────────────────────────────────────────────────────────────

    def export_daily_picks(
        self,
        spreadsheet_id: str,
        ncaab_data: Optional[Dict[str, Any]] = None,
        nba_predictions: Optional[List[Dict[str, Any]]] = None,
        nba_bets: Optional[List[Dict[str, Any]]] = None,
        prop_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export all daily picks to Google Sheets (Props + NBA + NCAAB + Summary).

        Args:
            spreadsheet_id: Target Google Sheets ID
            ncaab_data: Result from run_ncaab_analysis()
            nba_predictions: NBA predictions list
            nba_bets: NBA qualifying bets
            prop_data: Result from run_prop_analysis()

        Returns:
            Dict with per-tab results
        """
        if not self.client:
            return {"error": "Google Sheets not configured"}

        results: Dict[str, Any] = {}

        if prop_data and prop_data.get("props"):
            results["props"] = self.export_props(spreadsheet_id, prop_data)

        if nba_predictions:
            results["nba"] = self.export_nba(
                spreadsheet_id, nba_predictions, nba_bets or []
            )

        if ncaab_data and ncaab_data.get("game_analyses"):
            results["ncaab"] = self.export_ncaab(spreadsheet_id, ncaab_data)

        results["summary"] = self.export_summary(
            spreadsheet_id,
            ncaab_data=ncaab_data,
            nba_predictions=nba_predictions,
            nba_bets=nba_bets,
            prop_data=prop_data,
        )

        # Log overall result
        tabs_ok = sum(
            1 for r in results.values() if isinstance(r, dict) and r.get("status") == "success"
        )
        logger.info(
            f"Google Sheets export complete: {tabs_ok}/{len(results)} tabs written"
        )

        return results

    # ───────────────────────────────────────────────────────────────
    # Info
    # ───────────────────────────────────────────────────────────────

    def get_spreadsheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Get info about a spreadsheet (tabs, title, URL)."""
        if not self.client:
            return {"error": "Google Sheets not configured"}
        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            worksheets = [ws.title for ws in sheet.worksheets()]
            return {
                "title": sheet.title,
                "url": sheet.url,
                "worksheets": worksheets,
                "worksheet_count": len(worksheets),
            }
        except Exception as e:
            logger.error(f"Error getting spreadsheet info: {e}")
            return {"error": str(e)}
