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
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "threes": "3PM",
    "blocks": "BLK",
    "steals": "STL",
    "pts+reb+ast": "PRA",
    "pts+reb": "P+R",
    "pts+ast": "P+A",
    "reb+ast": "R+A",
    "turnovers": "TO",
    "stl+blk": "S+B",
}


def _coerce_odds(odds: Any, default: int = -110) -> int:
    try:
        if odds is None:
            return default
        if isinstance(odds, bool):
            return default
        return int(float(str(odds).strip()))
    except (TypeError, ValueError):
        return default


def _fmt_odds(odds: Any) -> str:
    odds_int = _coerce_odds(odds)
    return f"+{odds_int}" if odds_int > 0 else str(odds_int)


def _confidence_label(edge: float, ev_class: str) -> str:
    if ev_class == "strong_play" or edge >= 0.07:
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
                "Google Sheets not configured. Set GOOGLE_SERVICE_ACCOUNT_PATH in .env"
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
            logger.error(f"Service account file not found: {credentials_path}")
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

        # Proper A1 notation for more than 26 columns
        def _col_name(n):
            name = ""
            while n > 0:
                n, remainder = divmod(n - 1, 26)
                name = chr(65 + remainder) + name
            return name

        col_end = _col_name(len(headers))
        worksheet.update(
            range_name=f"A1:{col_end}{len(all_data)}",
            values=all_data,
        )
        # Bold + freeze header row
        worksheet.format("1:1", {"textFormat": {"bold": True}})
        worksheet.freeze(rows=1)
        return len(rows)

    # ───────────────────────────────────────────────────────────────
    # Shared formatting helpers
    # ───────────────────────────────────────────────────────────────

    def _hex_to_rgb(self, hex_color: str) -> Dict:
        """Convert '#RRGGBB' to Sheets-compatible RGB dict (0–1 scale)."""
        h = hex_color.lstrip("#")
        return {
            "red": int(h[0:2], 16) / 255,
            "green": int(h[2:4], 16) / 255,
            "blue": int(h[4:6], 16) / 255,
        }

    def _col_letter(self, n: int) -> str:
        """Convert 1-based column number to A1 letter (e.g. 27 → AA)."""
        name = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            name = chr(65 + r) + name
        return name

    def _format_tab_header(
        self,
        ws: gspread.Worksheet,
        hex_color: str,
        col_count: int,
    ) -> None:
        """Apply bold white header with custom background color."""
        try:
            col_letter = self._col_letter(col_count)
            rgb = self._hex_to_rgb(hex_color)
            ws.format(
                f"A1:{col_letter}1",
                {
                    "backgroundColor": rgb,
                    "textFormat": {
                        "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                        "bold": True,
                        "fontSize": 11,
                    },
                    "horizontalAlignment": "CENTER",
                },
            )
        except Exception as e:
            logger.debug(f"Header format skipped: {e}")

    def _apply_ev_row_colors(
        self,
        spreadsheet: gspread.Spreadsheet,
        ws: gspread.Worksheet,
        data_row_count: int,
        ev_col_idx: int,  # 0-based column index of EV Class column
        col_count: int,
    ) -> None:
        """Apply row-level colors based on EV Class via conditional format rules."""
        # (ev_class_text, bg_hex, fg_hex)
        ev_colors = [
            ("Strong Play", "#C6EFCE", "#276221"),
            ("Good Play",   "#E2EFDA", "#375623"),
            ("Lean",        "#FFEB9C", "#9C6500"),
            ("Pass",        "#FFC7CE", "#9C0006"),
        ]
        col_letter = self._col_letter(ev_col_idx + 1)  # 1-based for formula
        requests = []
        for i, (ev_class, bg_hex, fg_hex) in enumerate(ev_colors):
            bg = self._hex_to_rgb(bg_hex)
            fg = self._hex_to_rgb(fg_hex)
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": ws.id,
                            "startRowIndex": 1,
                            "endRowIndex": data_row_count + 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": col_count,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": f'=${col_letter}2="{ev_class}"'}],
                            },
                            "format": {
                                "backgroundColor": bg,
                                "textFormat": {"foregroundColor": fg},
                            },
                        },
                    },
                    "index": i,
                }
            })
        if requests:
            try:
                spreadsheet.batch_update({"requests": requests})
            except Exception as e:
                logger.debug(f"EV row colors skipped: {e}")

    def _apply_column_conditional(
        self,
        spreadsheet: gspread.Spreadsheet,
        ws: gspread.Worksheet,
        col_idx: int,  # 0-based
        rules: List[Dict],  # [{"type": "NUMBER_GREATER_THAN_EQ"|"TEXT_EQ", "value": ..., "bg": "#hex", "fg": "#hex", "bold": bool}]
        data_row_count: int,
        index_offset: int = 0,
    ) -> None:
        """Apply conditional formatting to a single column."""
        requests = []
        for i, rule in enumerate(rules):
            bg = self._hex_to_rgb(rule["bg"])
            fg = self._hex_to_rgb(rule.get("fg", "#000000"))
            cond_type = rule["type"]
            val = rule["value"]
            condition: Dict = {"type": cond_type}
            if cond_type == "NUMBER_BETWEEN":
                condition["values"] = [
                    {"userEnteredValue": str(val[0])},
                    {"userEnteredValue": str(val[1])},
                ]
            else:
                condition["values"] = [{"userEnteredValue": str(val)}]
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": ws.id,
                            "startRowIndex": 1,
                            "endRowIndex": data_row_count + 2,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        }],
                        "booleanRule": {
                            "condition": condition,
                            "format": {
                                "backgroundColor": bg,
                                "textFormat": {
                                    "foregroundColor": fg,
                                    "bold": rule.get("bold", False),
                                },
                            },
                        },
                    },
                    "index": index_offset + i,
                }
            })
        if requests:
            try:
                spreadsheet.batch_update({"requests": requests})
            except Exception as e:
                logger.debug(f"Column conditional skipped: {e}")

    def _set_column_widths(
        self,
        spreadsheet: gspread.Spreadsheet,
        ws: gspread.Worksheet,
        widths: List[int],
    ) -> None:
        """Set column pixel widths via Sheets API batch update."""
        requests = []
        for idx, width in enumerate(widths):
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": idx,
                        "endIndex": idx + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            })
        if requests:
            try:
                spreadsheet.batch_update({"requests": requests})
            except Exception as e:
                logger.debug(f"Column widths skipped: {e}")

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
                "Date",
                "Player",
                "Team",
                "Opponent",
                "Game",
                "Stat",
                "Line",
                "Side",
                "Odds",
                "Projected",
                "Edge %",
                "Bayesian P",
                "EV Class",
                "Confidence",
                "Kelly %",
                "Sharp Signals",
                "Situational Context",
                "Best Book",
                "Books #",
                "Over Odds",
                "Under Odds",
            ]

            # Use ALL analyzed props, sorted by edge descending
            all_props = prop_data.get("props", [])
            all_props.sort(key=lambda x: x.get("bayesian_edge", 0), reverse=True)

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

                # Extract situational RAG context
                situational_context = p.get(
                    "situational_context", "No historical analogs found."
                )

                rows.append(
                    [
                        today,
                        p.get("player_name", ""),
                        p.get("team", ""),
                        p.get("opponent", ""),
                        game,
                        stat_label,
                        p.get("line", 0),
                        best_side,
                        _fmt_odds(odds),
                        round(p.get("projected_mean", 0), 1),
                        round(edge * 100, 2),
                        round(p.get("posterior_p", 0), 4),
                        ev_class.replace("_", " ").title() if ev_class else "",
                        _confidence_label(edge, ev_class),
                        round(p.get("kelly_fraction", 0) * 100, 2),
                        signals,
                        situational_context,
                        best_book,
                        p.get("books_offering", 0),
                        _fmt_odds(p.get("over_odds", -110)),
                        _fmt_odds(p.get("under_odds", -110)),
                    ]
                )

            written = self._batch_write(ws, headers, rows)

            # ── Formatting ──
            try:
                # Slate header
                self._format_tab_header(ws, "#3C4A6A", len(headers))
                # EV class row colors (col 12 = M, 0-based index 12)
                self._apply_ev_row_colors(sheet, ws, written, 12, len(headers))
                # Column widths: Date|Player|Team|Opp|Game|Stat|Line|Side|Odds|Proj|Edge%|BayesP|EVClass|Conf|Kelly%|Signals|Context|Book|Books#|OvOdds|UnOdds
                self._set_column_widths(sheet, ws, [80, 160, 70, 100, 180, 50, 50, 55, 60, 60, 60, 70, 90, 75, 60, 160, 200, 90, 55, 60, 60])
            except Exception as fmt_err:
                logger.debug(f"Props formatting skipped: {fmt_err}")

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
                "Date",
                "Home",
                "Away",
                "Book",
                "Home ML",
                "Away ML",
                "Spread",
                "Spread Odds",
                "Total",
                "Over Odds",
                "Under Odds",
                "Home Win %",
                "Away Win %",
                "Proj Spread",
                "Proj Total",
                "O/U Rec",
                "Best Bet",
                "Edge %",
                "Kelly %",
                "Bet Size",
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
                moneyline_pred = p.get("moneyline_prediction", {})
                home_prob = moneyline_pred.get("home_win_prob", 0.5)
                away_prob = 1 - home_prob

                # Spread data
                spread_data = p.get("spread", {})
                spread_val = spread_data.get("home_point", "") if spread_data else ""
                spread_odds = (
                    _fmt_odds(spread_data.get("home_odds", -110)) if spread_data else ""
                )

                # Total data
                total_data = p.get("total", {})
                total_val = total_data.get("point", "") if total_data else ""
                over_odds = (
                    _fmt_odds(total_data.get("over_odds", -110)) if total_data else ""
                )
                under_odds = (
                    _fmt_odds(total_data.get("under_odds", -110)) if total_data else ""
                )

                # Implied spread from probability
                proj_spread = round((home_prob - 0.5) * -26, 1) if home_prob else ""

                # Best bet
                best_bet = ev.get("best_bet", "")
                best_side = home if best_bet == "home" else away
                home_edge = ev.get("home_ev", 0)
                away_edge = ev.get("away_ev", 0)
                best_edge = home_edge if best_bet == "home" else away_edge
                kelly = p.get("kelly_criterion", 0)

                # Match to bets list
                gid = f"NBA_{home}_{away}_{today.replace('-', '')}".replace(" ", "")
                bet = bet_lookup.get(gid, {})
                bet_size = bet.get("bet_size", 0) if bet else 0

                rows.append(
                    [
                        today,
                        home,
                        away,
                        p.get("book", ""),
                        _fmt_odds(ev.get("home_odds", 0))
                        if ev.get("home_odds")
                        else "",
                        _fmt_odds(ev.get("away_odds", 0))
                        if ev.get("away_odds")
                        else "",
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
                    ]
                )

            written = self._batch_write(ws, headers, rows)

            # ── Formatting ──
            try:
                # Navy header
                self._format_tab_header(ws, "#1A3A6B", len(headers))
                # Highlight rows where Best Bet (col Q = index 16) is not empty
                if written:
                    spreadsheet_obj = self.client.open_by_key(spreadsheet_id)
                    spreadsheet_obj.batch_update({"requests": [{
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{
                                    "sheetId": ws.id,
                                    "startRowIndex": 1,
                                    "endRowIndex": written + 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": len(headers),
                                }],
                                "booleanRule": {
                                    "condition": {
                                        "type": "CUSTOM_FORMULA",
                                        "values": [{"userEnteredValue": '=$Q2<>""'}],
                                    },
                                    "format": {
                                        "backgroundColor": self._hex_to_rgb("#C6EFCE"),
                                        "textFormat": {"foregroundColor": self._hex_to_rgb("#276221")},
                                    },
                                },
                            },
                            "index": 0,
                        }
                    }]})
                # Column widths: Date|Home|Away|Book|HomML|AwML|Spread|SpOdds|Total|OvOdds|UnOdds|H%|A%|ProjSprd|ProjTot|O/U|BestBet|Edge%|Kelly%|BetSize
                self._set_column_widths(self.client.open_by_key(spreadsheet_id), ws,
                    [80, 140, 140, 90, 65, 65, 65, 75, 65, 65, 65, 65, 65, 75, 75, 65, 160, 65, 65, 75])
            except Exception as fmt_err:
                logger.debug(f"NBA formatting skipped: {fmt_err}")

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
                "Date",
                "Home",
                "Away",
                "Conference",
                "Spread",
                "Total",
                "Pinnacle Home",
                "Pinnacle Away",
                "Retail Home",
                "Retail Away",
                "True Home %",
                "True Away %",
                "Blend Home %",
                "Blend Away %",
                "Home Edge %",
                "Away Edge %",
                "Sharp Side",
                "Signals",
                "Signal Conf %",
                "Home AdjOE",
                "Home AdjDE",
                "Away AdjOE",
                "Away AdjDE",
                "BPI Home",
                "BPI Away",
                "Pick",
                "Kelly %",
                "Bet Size",
                "Confidence",
                "Historical Context",
            ]

            today = datetime.now().strftime("%Y-%m-%d")
            analyses = ncaab_data.get("game_analyses", [])
            bets = ncaab_data.get("bets", [])
            bets_lookup: Dict[str, Dict] = {}
            for b in bets:
                bets_lookup[b.get("game_id", "")] = b
            rows: List[List[Any]] = []

            for a in analyses:
                game = a.get("game", {})
                home = game.get("home", "")
                away = game.get("away", "")
                gid = game.get("game_id", "")
                signals = a.get("sharp_signals", [])
                he = a.get("home_edge", 0)
                ae = a.get("away_edge", 0)

                # Efficiency stats
                h_eff = game.get("home_eff") or {}
                a_eff = game.get("away_eff") or {}

                # Find bet for this game
                bet = bets_lookup.get(gid + "_HOME") or bets_lookup.get(
                    gid + "_AWAY", {}
                )

                confidence = a.get("confidence_level", "SPECULATIVE")
                historical = "; ".join(
                    s.get("game", "")[:60] for s in a.get("historical_context", [])[:2]
                )

                rows.append(
                    [
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
                        h_eff.get("AdjOE", ""),
                        h_eff.get("AdjDE", ""),
                        a_eff.get("AdjOE", ""),
                        a_eff.get("AdjDE", ""),
                        h_eff.get("BPI", ""),
                        a_eff.get("BPI", ""),
                        bet.get("side", "") if bet else "",
                        round(bet.get("portfolio_fraction_pct", 0), 2) if bet else "",
                        round(bet.get("bet_size_$", 0), 2) if bet else "",
                        confidence,
                        historical or "No historical data",
                    ]
                )

            written = self._batch_write(ws, headers, rows)

            # ── Formatting ──
            try:
                sheet = self.client.open_by_key(spreadsheet_id)
                # Maroon header
                self._format_tab_header(ws, "#6B1A1A", len(headers))
                # Highlight rows where Pick (col Z = index 25) is not empty
                if written:
                    sheet.batch_update({"requests": [{
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{
                                    "sheetId": ws.id,
                                    "startRowIndex": 1,
                                    "endRowIndex": written + 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": len(headers),
                                }],
                                "booleanRule": {
                                    "condition": {
                                        "type": "CUSTOM_FORMULA",
                                        "values": [{"userEnteredValue": '=$Z2<>""'}],
                                    },
                                    "format": {
                                        "backgroundColor": self._hex_to_rgb("#C6EFCE"),
                                        "textFormat": {"foregroundColor": self._hex_to_rgb("#276221")},
                                    },
                                },
                            },
                            "index": 0,
                        }
                    }]})
                # Confidence column color (col 27 = AB, 0-based 27)
                self._apply_column_conditional(sheet, ws, 27, [
                    {"type": "TEXT_EQ", "value": "HIGH",        "bg": "#C6EFCE", "fg": "#276221", "bold": True},
                    {"type": "TEXT_EQ", "value": "MEDIUM",      "bg": "#FFEB9C", "fg": "#9C6500", "bold": True},
                    {"type": "TEXT_EQ", "value": "LOW",         "bg": "#FFC7CE", "fg": "#9C0006", "bold": False},
                    {"type": "TEXT_EQ", "value": "SPECULATIVE", "bg": "#EEEEEE", "fg": "#555555", "bold": False},
                ], written, index_offset=1)
                # Column widths
                self._set_column_widths(sheet, ws,
                    [80, 130, 130, 90, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 100, 180, 70, 60, 60, 60, 60, 60, 60, 90, 65, 75, 75, 220])
            except Exception as fmt_err:
                logger.debug(f"NCAAB formatting skipped: {fmt_err}")

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
            ws = self._get_or_create_worksheet(sheet, tab_name, rows=40, cols=5)

            now = datetime.now().strftime("%Y-%m-%d %I:%M %p ET")
            ncaab_games = len((ncaab_data or {}).get("game_analyses", []))
            ncaab_bets = len((ncaab_data or {}).get("bets", []))
            nba_games = len([p for p in (nba_predictions or []) if "error" not in p])
            nba_bet_count = len(nba_bets or [])
            prop_total = (prop_data or {}).get("total_props", 0)
            prop_ev = (prop_data or {}).get("positive_ev_count", 0)
            strong_plays = len([p for p in (prop_data or {}).get("props", []) if p.get("ev_classification") == "strong_play"])
            high_value_props = len((prop_data or {}).get("best_props", []))

            total_exposure = sum(
                b.get("bet_size_$", 0) for b in (ncaab_data or {}).get("bets", [])
            ) + sum(b.get("bet_size", 0) for b in (nba_bets or []))

            # CLV avg from bet_tracker if available
            avg_clv = ""
            try:
                from app.services.bet_tracker import BetTracker
                metrics = BetTracker().get_performance_metrics()
                avg_clv_val = metrics.get("avg_clv")
                if avg_clv_val is not None:
                    avg_clv = f"{avg_clv_val:+.2f}%"
            except Exception:
                pass

            summary_data = [
                ["🏀 Daily Picks Summary", now, "", "", ""],
                ["", "", "", "", ""],
                ["📊 GAMES ANALYZED", "", "", "", ""],
                ["  NCAAB Games Analyzed",  ncaab_games, "", "", ""],
                ["  NCAAB Qualifying Bets", ncaab_bets,  "", "", ""],
                ["  NBA Games Analyzed",    nba_games,   "", "", ""],
                ["  NBA Qualifying Bets",   nba_bet_count, "", "", ""],
                ["", "", "", "", ""],
                ["🎯 PROPS", "", "", "", ""],
                ["  Props Scanned",         prop_total,      "", "", ""],
                ["  Props +EV",             prop_ev,         "", "", ""],
                ["  Strong Plays",          strong_plays,    "", "", ""],
                ["  High Value Props",      high_value_props,"", "", ""],
                ["", "", "", "", ""],
                ["💰 EXPOSURE & PERFORMANCE", "", "", "", ""],
                ["  Total Exposure",        f"${total_exposure:.0f}", "", "", ""],
                ["  Avg CLV (settled)",     avg_clv or "N/A", "", "", ""],
                ["", "", "", "", ""],
                ["⚙️ Meta", "", "", "", ""],
                ["  Generated by", "sports-data-platform", "", "", ""],
                ["  Generated at", now, "", "", ""],
            ]

            ws.update(range_name=f"A1:E{len(summary_data)}", values=summary_data)

            # Title row
            ws.format("A1:E1", {
                "backgroundColor": self._hex_to_rgb("#333333"),
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 13,
                },
            })
            # Section header rows (row 3, 9, 15, 19)
            for row_num in [3, 9, 15, 19]:
                ws.format(f"A{row_num}:E{row_num}", {
                    "backgroundColor": self._hex_to_rgb("#E8E8E8"),
                    "textFormat": {"bold": True, "fontSize": 11},
                })
            ws.freeze(rows=1)
            # Column widths
            self._set_column_widths(sheet, ws, [220, 120, 80, 80, 80])

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
        parlay_suggestions: Optional[List[Dict[str, Any]]] = None,
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

        # 1. Legend — always first
        results["legend"] = self.export_legend(spreadsheet_id)

        # 2. Top 10 Plays — always second
        results["top10"] = self.export_top10_plays(
            spreadsheet_id,
            prop_data=prop_data,
            ncaab_data=ncaab_data,
            nba_predictions=nba_predictions,
            nba_bets=nba_bets,
        )

        # 3. Parlays — generated suggestions (or empty-state message if none)
        results["parlays"] = self.export_parlays(
            spreadsheet_id,
            parlay_suggestions=parlay_suggestions,
        )

        if prop_data and prop_data.get("props"):
            results["props"] = self.export_props(spreadsheet_id, prop_data)
            results["high_value_props"] = self.export_high_value_props(
                spreadsheet_id,
                prop_data,
            )

        if nba_predictions:
            results["nba"] = self.export_nba(
                spreadsheet_id, nba_predictions, nba_bets or []
            )

        if ncaab_data and ncaab_data.get("game_analyses"):
            qdrant_used = any(
                ga.get("qdrant_retrieved", False)
                for ga in (ncaab_data.get("game_analyses") or [])
            )
            if qdrant_used:
                logger.info(
                    "Qdrant context present — including historical context in Sheets export"
                )
            results["ncaab"] = self.export_ncaab(spreadsheet_id, ncaab_data)

        results["summary"] = self.export_summary(
            spreadsheet_id,
            ncaab_data=ncaab_data,
            nba_predictions=nba_predictions,
            nba_bets=nba_bets,
            prop_data=prop_data,
        )

        # BetSlip — interactive tracker the user fills in
        results["bet_slip"] = self.export_bet_slip(
            spreadsheet_id,
            prop_data=prop_data,
            ncaab_data=ncaab_data,
            nba_bets=nba_bets,
        )

        # BetTracker — full history with P&L, CLV, status for primary book
        results["bet_tracker"] = self.export_bet_tracker(spreadsheet_id)

        # Log overall result
        tabs_ok = sum(
            1
            for r in results.values()
            if isinstance(r, dict) and r.get("status") == "success"
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

    def export_high_value_props(
        self,
        spreadsheet_id: str,
        prop_data: Dict[str, Any],
        tab_name: str = "HighValueProps",
    ) -> Dict[str, Any]:
        """Export high-value filtered props (Even Odds or Edge < 30%) to Google Sheets."""
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name)

            headers = [
                "Date",
                "Player",
                "Team",
                "Opponent",
                "Game",
                "Stat",
                "Line",
                "Side",
                "Best Odds",      # best across all books
                "FD Odds",        # FanDuel-specific (— if not offered)
                "Best Book",
                "Projected",
                "Edge %",
                "Bayesian P",
                "EV Class",
                "Confidence",
                "Kelly %",
                "Best Line?",     # ✓ = highest-edge line for player+stat
                "Sharp Signals",
                "Situational Context",
                "Books #",
                "Over Odds",
                "Under Odds",
            ]

            all_props = prop_data.get("props", [])
            max_rows = int((prop_data or {}).get("export_max_rows", 120) or 120)

            filtered_props: List[Dict[str, Any]] = []
            for p in all_props:
                edge = float(p.get("bayesian_edge", 0) or 0)
                kelly = float(p.get("kelly_fraction", 0) or 0)
                ev_class = (p.get("ev_classification", "") or "").lower()

                # Exclude purely bad bets first
                if ev_class == "pass" and kelly <= 0:
                    continue
                if edge <= 0 and kelly <= 0:
                    continue

                best_side = p.get("best_side", "over").upper()
                odds_val = (
                    p.get("over_odds", -110)
                    if best_side == "OVER"
                    else p.get("under_odds", -110)
                )

                try:
                    odds_int = int(odds_val)
                except (ValueError, TypeError):
                    odds_int = -110

                # High Value Logic: Edge < 30% OR "Even Odds" (-110 to +110)
                is_low_edge = (edge > 0.0) and (edge < 0.30)
                is_even_odds = -110 <= odds_int <= 110

                if is_low_edge or is_even_odds:
                    filtered_props.append(p)

            filtered_props.sort(
                key=lambda x: (
                    float(x.get("kelly_fraction", 0) or 0),
                    float(x.get("bayesian_edge", 0) or 0),
                ),
                reverse=True,
            )
            filtered_props = filtered_props[:max_rows]

            today = datetime.now().strftime("%Y-%m-%d")
            rows: List[List[Any]] = []

            for p in filtered_props:
                stat_type = p.get("stat_type", "")
                stat_label = _STAT_DISPLAY.get(stat_type, stat_type.upper())
                best_side = p.get("best_side", "over").upper()
                odds = (
                    p.get("over_odds", -110)
                    if best_side == "OVER"
                    else p.get("under_odds", -110)
                )
                # FanDuel-specific odds — show "—" when FD doesn't offer this line
                fd_raw = (
                    p.get("fanduel_over_odds")
                    if best_side == "OVER"
                    else p.get("fanduel_under_odds")
                )
                fd_odds_str = _fmt_odds(int(fd_raw)) if fd_raw is not None else "—"

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
                best_line_mark = "✓" if p.get("best_alt_line") else ""

                situational_context = p.get(
                    "situational_context", "No historical analogs found."
                )

                rows.append(
                    [
                        today,
                        p.get("player_name", ""),
                        p.get("team", ""),
                        p.get("opponent", ""),
                        game,
                        stat_label,
                        p.get("line", 0),
                        best_side,
                        _fmt_odds(odds),          # Best Odds (col I)
                        fd_odds_str,               # FD Odds (col J)
                        best_book,                 # Best Book (col K)
                        round(p.get("projected_mean", 0), 1),
                        round(edge * 100, 2),
                        round(p.get("posterior_p", 0), 4),
                        ev_class.replace("_", " ").title() if ev_class else "",
                        _confidence_label(edge, ev_class),
                        round(p.get("kelly_fraction", 0) * 100, 2),
                        best_line_mark,            # Best Line? (col R)
                        signals,
                        situational_context,
                        p.get("books_offering", 0),
                        _fmt_odds(p.get("over_odds", -110)),
                        _fmt_odds(p.get("under_odds", -110)),
                    ]
                )

            written = self._batch_write(ws, headers, rows)

            # --- Advanced Formatting ---
            try:
                # Dark green header
                self._format_tab_header(ws, "#0D3B1F", len(headers))
                # EV class row colors — EV Class is now col O (index 14)
                self._apply_ev_row_colors(sheet, ws, written, 14, len(headers))
                # Confidence column (P = index 15) color
                self._apply_column_conditional(sheet, ws, 15, [
                    {"type": "TEXT_EQ", "value": "HIGH",   "bg": "#C6EFCE", "fg": "#276221", "bold": True},
                    {"type": "TEXT_EQ", "value": "MEDIUM", "bg": "#FFEB9C", "fg": "#9C6500", "bold": True},
                    {"type": "TEXT_EQ", "value": "LOW",    "bg": "#FFC7CE", "fg": "#9C0006", "bold": False},
                ], written, index_offset=4)
                # Column widths: Date|Player|Team|Opp|Game|Stat|Line|Side|BestOdds|FDOdds|BestBook|Proj|Edge%|BayesP|EVClass|Conf|Kelly%|BestLine?|Signals|Context|Books#|OvOdds|UnOdds
                self._set_column_widths(sheet, ws, [80, 160, 70, 100, 180, 50, 50, 55, 65, 65, 90, 60, 60, 70, 90, 75, 60, 70, 160, 200, 55, 60, 60])
                logger.info("Applied conditional formatting to HighValueProps")

            except Exception as fmt_err:
                logger.warning(
                    f"Failed to apply formatting to HighValueProps: {fmt_err}"
                )

            logger.info(f"Exported {written} props to Google Sheets tab '{tab_name}'")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"High-value props export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # Parlays tab — generated parlay suggestions
    # ───────────────────────────────────────────────────────────────

    def export_parlays(
        self,
        spreadsheet_id: str,
        parlay_suggestions: Optional[List[Dict[str, Any]]] = None,
        tab_name: str = "🎰 Parlays",
    ) -> Dict[str, Any]:
        """Export generated parlay suggestions to a Parlays tab.

        Args:
            spreadsheet_id: Target Google Sheets ID
            parlay_suggestions: List from parlay_engine.generate_suggestions()
        """
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name, rows=200, cols=14)

            headers = [
                "Rank",
                "Type",         # SGP or CROSS
                "Leg 1",
                "Leg 2",
                "Leg 3",
                "Leg 4",
                "Combined Odds",
                "Fair Odds",
                "Edge %",
                "True Prob",
                "EV Class",
                "Score",
                "Notes",
            ]

            suggestions = parlay_suggestions or []
            if not suggestions:
                # Write header + empty state message
                ws.clear()
                ws.update("A1", [headers])
                ws.update("A2", [["No qualifying parlay suggestions today — check back when more +EV props are available.", "", "", "", "", "", "", "", "", "", "", "", ""]])
                self._format_tab_header(ws, "#5B2C8D", len(headers))
                return {"status": "success", "tab": tab_name, "rows_written": 0}

            today = datetime.now().strftime("%Y-%m-%d")
            rows: List[List[Any]] = []

            for i, s in enumerate(suggestions, 1):
                leg_descs = s.get("leg_descriptions", [])
                # Pad to 4 legs
                legs_padded = (leg_descs + ["", "", "", ""])[:4]
                combined_am = s.get("combined_odds_american", 0)
                # Estimate fair combined odds from true_prob
                true_p = float(s.get("combined_true_prob", 0.1))
                if true_p > 0:
                    fair_decimal = 1.0 / true_p
                    fair_am = int((fair_decimal - 1) * 100) if fair_decimal >= 2 else int(-100 / (fair_decimal - 1))
                else:
                    fair_am = combined_am
                ev_class = s.get("ev_class", "")
                edge_pct = float(s.get("edge_pct", 0))
                parlay_type = s.get("type", "CROSS")
                notes = f"{s.get('leg_count', 2)}-leg {parlay_type}"

                rows.append([
                    i,
                    parlay_type,
                    legs_padded[0],
                    legs_padded[1],
                    legs_padded[2],
                    legs_padded[3],
                    _fmt_odds(combined_am),
                    _fmt_odds(fair_am),
                    round(edge_pct, 2),
                    f"{round(true_p * 100, 1)}%",
                    ev_class.replace("_", " ").title() if ev_class else "",
                    round(s.get("composite_score", 0), 4),
                    notes,
                ])

            written = self._batch_write(ws, headers, rows)

            # ── Formatting ──
            try:
                self._format_tab_header(ws, "#5B2C8D", len(headers))  # purple
                self._apply_ev_row_colors(sheet, ws, written, 10, len(headers))  # EV Class col K (index 10)
                self._set_column_widths(sheet, ws, [45, 60, 220, 220, 220, 220, 85, 85, 60, 70, 90, 70, 130])
            except Exception as fmt_err:
                logger.debug(f"Parlays formatting skipped: {fmt_err}")

            logger.info(f"Exported {written} parlay suggestions to '{tab_name}'")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"Parlays export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # Legend tab — color key + column glossary + how-to
    # ───────────────────────────────────────────────────────────────

    def export_legend(
        self,
        spreadsheet_id: str,
        tab_name: str = "📖 Legend",
    ) -> Dict[str, Any]:
        """Write a color-coded legend / guide tab."""
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name, rows=80, cols=4)

            rows: List[List[Any]] = [
                # ── Section 1: Title ──
                ["🏀 Sports Data Platform — Daily Picks Guide", "", "", ""],
                ["Last updated", datetime.now().strftime("%Y-%m-%d %I:%M %p"), "", ""],
                ["", "", "", ""],

                # ── Section 2: Color Key ──
                ["🎨 COLOR CODE", "Meaning", "Action", ""],
                ["🟢 Strong Play",  "Edge ≥ 7% + High confidence",    "BET — Half Kelly recommendation", ""],
                ["🟩 Good Play",    "Edge 5–7% + Medium confidence",  "BET — Half Kelly recommended", ""],
                ["🟡 Lean",         "Edge 3–5% — Lower confidence",   "SMALL BET or pass", ""],
                ["🔴 Pass",         "Edge < 3% or negative",          "SKIP — no value", ""],
                ["", "", "", ""],

                # ── Section 3: Confidence Tiers ──
                ["📊 CONFIDENCE TIER", "Edge Range", "Kelly Fraction", "Min Edge"],
                ["MAX",         "≥ 10%",  "Quarter Kelly",  "10%"],
                ["HIGH",        "7–10%",  "Quarter Kelly",  "7%"],
                ["MEDIUM",      "5–7%",   "Quarter Kelly",  "5%"],
                ["LOW",         "3–5%",   "Quarter Kelly",  "3%"],
                ["SPECULATIVE", "< 3%",   "Skip / $0",      "—"],
                ["", "", "", ""],

                # ── Section 4: Tab Guide ──
                ["📋 TAB GUIDE", "What it shows", "", ""],
                ["🔥 Top 10 Plays",  "Best ranked bets across all sports — start here",             "", ""],
                ["HighValueProps",   "Player props with realistic odds (-110 to +110) or ≤30% edge","", ""],
                ["Props",            "All analyzed player props sorted by Bayesian edge",           "", ""],
                ["NBA",              "NBA game picks: spreads, totals, ML probabilities",           "", ""],
                ["NCAAB",            "College basketball sharp money analysis",                     "", ""],
                ["Summary",          "Daily counts: games analyzed, bets placed, exposure total",  "", ""],
                ["BetSlip",          "Interactive tracker — fill ✓ Placed? with Y for bets taken", "", ""],
                ["Performance",      "W/L record, units, ROI, avg CLV by model/sport",             "", ""],
                ["", "", "", ""],

                # ── Section 5: Column Glossary ──
                ["🔑 COLUMN GLOSSARY", "Definition", "", ""],
                ["Edge %",          "((True Prob × Decimal Odds) - 1) × 100. Positive = +EV",         "", ""],
                ["Bayesian P",      "Posterior probability of covering/hitting from Bayesian model",   "", ""],
                ["Kelly %",         "Fractional Kelly stake as % of bankroll (Quarter Kelly, max 5%)", "", ""],
                ["Kelly $",         "Dollar stake based on $100 bankroll",                            "", ""],
                ["EV Class",        "Strong Play / Good Play / Lean / Pass based on edge tier",        "", ""],
                ["Confidence",      "MAX / HIGH / MEDIUM / LOW / SPECULATIVE",                        "", ""],
                ["Sharp Signals",   "RLM = reverse line movement, STEAM = rapid multi-book move",      "", ""],
                ["CLV",             "Closing Line Value — positive means you beat the closing odds",   "", ""],
                ["Proj Spread",     "Model-implied spread from win probability",                       "", ""],
                ["Signal Conf %",   "How strongly signals agree (0–100%)",                            "", ""],
                ["", "", "", ""],

                # ── Section 6: BetSlip Workflow ──
                ["📝 BETSLIP WORKFLOW", "", "", ""],
                ["Step 1", "Open BetSlip tab",                                           "", ""],
                ["Step 2", "Review picks — check Edge%, EV Class, Confidence",          "", ""],
                ["Step 3", 'Type "Y" in the ✓ Placed? column for bets you are taking', "", ""],
                ["Step 4", "Run: python3 backend/sync_betslip.py  to register bets",    "", ""],
                ["Step 5", "After games finish: python3 backend/sync_betslip.py --settle to record W/L", "", ""],
                ["", "", "", ""],

                # ── Section 7: Kelly Sizing Cheatsheet ──
                ["💰 KELLY SIZING QUICK REF", "Bankroll $1,000", "Bankroll $2,500", "Bankroll $5,000"],
                ["1% Kelly",   "$10",   "$25",   "$50"],
                ["2% Kelly",   "$20",   "$50",   "$100"],
                ["3% Kelly",   "$30",   "$75",   "$150"],
                ["5% Kelly",   "$50",   "$125",  "$250"],
                ["Max (5%)",   "$50",   "$125",  "$250"],
            ]

            ws.update(range_name=f"A1:D{len(rows)}", values=rows)

            # Formatting
            try:
                # Title row
                ws.format("A1:D1", {
                    "backgroundColor": self._hex_to_rgb("#333333"),
                    "textFormat": {
                        "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                        "bold": True,
                        "fontSize": 13,
                    },
                })
                # Section headers (rows 4, 11, 17, 27, 38, 47, 54)
                section_rows = [4, 11, 17, 27, 38, 47, 54]
                for r in section_rows:
                    ws.format(f"A{r}:D{r}", {
                        "backgroundColor": self._hex_to_rgb("#E8E8E8"),
                        "textFormat": {"bold": True, "fontSize": 11},
                    })
                # Color-code the swatch rows
                swatch_map = [
                    (5,  "#C6EFCE"),  # Strong Play
                    (6,  "#E2EFDA"),  # Good Play
                    (7,  "#FFEB9C"),  # Lean
                    (8,  "#FFC7CE"),  # Pass
                ]
                for row_num, bg_hex in swatch_map:
                    ws.format(f"A{row_num}:D{row_num}", {
                        "backgroundColor": self._hex_to_rgb(bg_hex),
                    })
                # Column widths
                self._set_column_widths(sheet, ws, [200, 350, 220, 100])
                ws.freeze(rows=1)

                # ── Navigation links — "Jump to Tab" section ──
                # Append after the last content row with tab hyperlinks
                try:
                    all_ws = sheet.worksheets()
                    tab_id_map = {w.title: w.id for w in all_ws}
                    jump_header_row = len(rows) + 3  # leave a gap
                    ws.update(f"A{jump_header_row}", [["🔗 Quick Navigation"]])
                    ws.format(f"A{jump_header_row}", {
                        "backgroundColor": self._hex_to_rgb("#3C4A6A"),
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}, "fontSize": 11},
                    })
                    nav_tabs = [
                        ("🔥 Top 10 Plays", "Top 10 Plays"),
                        ("🎰 Parlays", "Parlays"),
                        ("📊 HighValueProps", "HighValueProps"),
                        ("📋 Props", "Props"),
                        ("🏀 NBA", "NBA"),
                        ("🏈 NCAAB", "NCAAB"),
                        ("📈 Summary", "Summary"),
                        ("📝 BetSlip", "BetSlip"),
                    ]
                    nav_rows = []
                    for label, tab_title in nav_tabs:
                        # Find sheet by partial match
                        gid = next((v for k, v in tab_id_map.items() if tab_title.lower() in k.lower()), None)
                        if gid is not None:
                            nav_rows.append([f'=HYPERLINK("#gid={gid}","{label}")'])
                        else:
                            nav_rows.append([label])
                    ws.update(f"A{jump_header_row + 1}", nav_rows)
                except Exception as nav_err:
                    logger.debug(f"Legend navigation links skipped: {nav_err}")

            except Exception as fmt_err:
                logger.debug(f"Legend formatting skipped: {fmt_err}")

            logger.info("Exported Legend tab to Google Sheets")
            return {"status": "success", "tab": tab_name, "rows_written": len(rows)}

        except Exception as e:
            logger.error(f"Legend export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # Top 10 Plays — ranked across all data sources
    # ───────────────────────────────────────────────────────────────

    def export_top10_plays(
        self,
        spreadsheet_id: str,
        prop_data: Optional[Dict[str, Any]] = None,
        ncaab_data: Optional[Dict[str, Any]] = None,
        nba_predictions: Optional[List[Dict[str, Any]]] = None,
        nba_bets: Optional[List[Dict[str, Any]]] = None,
        tab_name: str = "🔥 Top 10 Plays",
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """Rank and export the top N plays of the day across all sports/markets.

        Composite score = bayesian_edge × ev_weight × confidence_weight
        ev_weight:    Strong Play=1.0, Good Play=0.75, Lean=0.5, other=0.3
        conf_weight:  MAX=1.3, HIGH=1.0, MEDIUM=0.8, LOW=0.6, SPECULATIVE=0.4
        """
        if not self.client:
            return {"error": "Google Sheets not configured"}

        EV_WEIGHTS = {"strong play": 1.0, "strong_play": 1.0, "good play": 0.75, "good_play": 0.75, "lean": 0.5}
        CONF_WEIGHTS = {"MAX": 1.3, "HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.6, "SPECULATIVE": 0.4}

        candidates: List[Dict[str, Any]] = []
        today = datetime.now().strftime("%Y-%m-%d")

        # ── Props candidates ──
        for p in (prop_data or {}).get("props", []):
            edge = float(p.get("bayesian_edge", 0) or 0)
            if edge <= 0:
                continue
            ev_class = (p.get("ev_classification", "") or "").lower().replace("_", " ")
            conf = _confidence_label(edge, p.get("ev_classification", ""))
            ev_w = EV_WEIGHTS.get(ev_class, 0.3)
            conf_w = CONF_WEIGHTS.get(conf, 0.4)
            score = edge * ev_w * conf_w

            best_side = (p.get("best_side", "over") or "over").upper()
            odds = p.get("over_odds", -110) if best_side == "OVER" else p.get("under_odds", -110)
            book = (p.get("best_over_book", "") if best_side == "OVER" else p.get("best_under_book", "")) or ""
            home = p.get("home_team", "")
            away = p.get("away_team", "")
            game = f"{away} @ {home}" if home and away else ""
            stat_label = _STAT_DISPLAY.get(p.get("stat_type", ""), (p.get("stat_type") or "").upper())

            candidates.append({
                "score": score,
                "type": "Player Prop",
                "source": "HighValueProps" if ev_class in ("strong play", "good play") else "Props",
                "game": game,
                "pick": p.get("player_name", ""),
                "market": f"{stat_label} {best_side}",
                "line": p.get("line", ""),
                "odds": _fmt_odds(odds),
                "edge_pct": round(edge * 100, 2),
                "ev_class": ev_class.title(),
                "confidence": conf,
                "book": book,
                "composite": round(score * 1000, 1),
            })

        # ── NBA candidates ──
        nba_bet_lookup = {b.get("game_id", ""): b for b in (nba_bets or [])}
        for p in (nba_predictions or []):
            if "error" in p:
                continue
            ev = p.get("expected_value", {})
            best_bet = ev.get("best_bet", "")
            if not best_bet:
                continue
            home = p.get("home_team", "")
            away = p.get("away_team", "")
            home_edge = float(ev.get("home_ev", 0) or 0)
            away_edge = float(ev.get("away_ev", 0) or 0)
            edge = home_edge if best_bet == "home" else away_edge
            if edge <= 0:
                continue
            conf = "HIGH" if edge >= 0.07 else ("MEDIUM" if edge >= 0.05 else "LOW")
            ev_class = "strong_play" if edge >= 0.07 else ("good_play" if edge >= 0.05 else "lean")
            score = edge * EV_WEIGHTS.get(ev_class, 0.3) * CONF_WEIGHTS.get(conf, 0.4)
            pick = home if best_bet == "home" else away
            candidates.append({
                "score": score,
                "type": "NBA Game",
                "source": "NBA",
                "game": f"{away} @ {home}",
                "pick": pick,
                "market": "Moneyline",
                "line": "",
                "odds": _fmt_odds(ev.get(f"{best_bet}_odds", 0)) if ev.get(f"{best_bet}_odds") else "",
                "edge_pct": round(edge * 100, 2),
                "ev_class": ev_class.replace("_", " ").title(),
                "confidence": conf,
                "book": "",
                "composite": round(score * 1000, 1),
            })

        # ── NCAAB candidates ──
        for a in (ncaab_data or {}).get("game_analyses", []):
            game_d = a.get("game", {})
            home = game_d.get("home", "")
            away = game_d.get("away", "")
            he = float(a.get("home_edge", 0) or 0)
            ae = float(a.get("away_edge", 0) or 0)
            sharp_side = (a.get("sharp_side") or "").upper()
            edge = he if sharp_side == "HOME" or (not sharp_side and he > ae) else ae
            if edge <= 0:
                continue
            conf = a.get("confidence_level", "LOW")
            ev_class = "strong_play" if edge >= 0.07 else ("good_play" if edge >= 0.05 else "lean")
            score = edge * EV_WEIGHTS.get(ev_class, 0.3) * CONF_WEIGHTS.get(conf, 0.4)
            pick = sharp_side or (home if he > ae else away)
            candidates.append({
                "score": score,
                "type": "NCAAB Game",
                "source": "NCAAB",
                "game": f"{away} @ {home}",
                "pick": pick,
                "market": "Sharp Side",
                "line": game_d.get("spread", ""),
                "odds": "",
                "edge_pct": round(edge * 100, 2),
                "ev_class": ev_class.replace("_", " ").title(),
                "confidence": conf,
                "book": "",
                "composite": round(score * 1000, 1),
            })

        # Sort and take top N
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_plays = candidates[:top_n]

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name, rows=top_n + 5, cols=13)

            headers = [
                "Rank", "Type", "Game", "Pick", "Market", "Line",
                "Odds", "Edge %", "EV Class", "Confidence", "Score", "Book", "Source Tab",
            ]
            rows_out: List[List[Any]] = []
            for i, c in enumerate(top_plays, 1):
                rows_out.append([
                    i,
                    c["type"],
                    c["game"],
                    c["pick"],
                    c["market"],
                    c["line"],
                    c["odds"],
                    c["edge_pct"],
                    c["ev_class"],
                    c["confidence"],
                    c["composite"],
                    c["book"],
                    c["source"],
                ])

            if not rows_out:
                rows_out = [["No picks available today.", "", "", "", "", "", "", "", "", "", "", "", ""]]

            written = self._batch_write(ws, headers, rows_out)

            # Formatting
            try:
                # Orange-red "fire" header
                self._format_tab_header(ws, "#B03A00", len(headers))
                # EV class row colors (col I = index 8)
                self._apply_ev_row_colors(sheet, ws, written, 8, len(headers))
                # Confidence column (J = index 9) color
                self._apply_column_conditional(sheet, ws, 9, [
                    {"type": "TEXT_EQ", "value": "High",   "bg": "#C6EFCE", "fg": "#276221", "bold": True},
                    {"type": "TEXT_EQ", "value": "Medium", "bg": "#FFEB9C", "fg": "#9C6500", "bold": True},
                    {"type": "TEXT_EQ", "value": "Low",    "bg": "#FFC7CE", "fg": "#9C0006", "bold": False},
                ], written, index_offset=4)
                # Column widths: Rank|Type|Game|Pick|Market|Line|Odds|Edge%|EVClass|Conf|Score|Book|Source
                self._set_column_widths(sheet, ws, [45, 90, 200, 160, 110, 55, 60, 65, 90, 85, 65, 90, 100])
                # Bold rank column
                if written:
                    ws.format(f"A2:A{written + 1}", {"textFormat": {"bold": True, "fontSize": 12}})
            except Exception as fmt_err:
                logger.debug(f"Top10 formatting skipped: {fmt_err}")

            logger.info(f"Exported Top {top_n} Plays tab ({written} rows)")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"Top 10 Plays export failed: {e}")
            return {"error": str(e)}

    # ───────────────────────────────────────────────────────────────
    # BetSlip export — interactive tracker the user fills in
    # ───────────────────────────────────────────────────────────────

    def export_bet_slip(
        self,
        spreadsheet_id: str,
        prop_data: Optional[Dict[str, Any]] = None,
        ncaab_data: Optional[Dict[str, Any]] = None,
        nba_bets: Optional[List[Dict[str, Any]]] = None,
        tab_name: str = "BetSlip",
        game_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export today's +EV recommendations as an interactive BetSlip.

        The user fills in the '✓ Placed?' column with 'Y' for bets they took.
        Run sync_betslip.py to register placed bets into the tracker DB.

        Columns:
            Date | Game | Player / Side | Stat | Line | Side | Odds | Book |
            Edge% | Kelly$ | EV Class | ✓ Placed? | Bet ID | Status | P/L | Notes
        """
        if not self.client:
            return {"error": "Google Sheets not configured"}

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name, rows=500, cols=16)

            headers = [
                "Date",
                "Game",
                "Player / Side",
                "Stat / Market",
                "Line",
                "Side",
                "Odds",
                "Book",
                "Edge %",
                "Kelly $",
                "EV Class",
                "✓ Placed?",   # User fills in Y/N here
                "Bet ID",      # Auto-filled by sync_betslip.py
                "Status",      # pending → won/lost/push
                "P/L $",       # Auto-calculated on settlement
                "Notes",
            ]

            today = game_date or datetime.now().strftime("%Y-%m-%d")
            rows: List[List[Any]] = []

            # ── Props (+EV bets from HighValueProps filter) ──
            if prop_data and prop_data.get("best_props"):
                for p in prop_data["best_props"]:
                    edge = float(p.get("bayesian_edge", 0) or 0)
                    kelly_frac = float(p.get("kelly_fraction", 0) or 0)
                    kelly_dollars = round(kelly_frac * 100, 2)  # $100 bankroll
                    best_side = (p.get("best_side", "over") or "over").upper()
                    odds = (
                        p.get("over_odds", -110)
                        if best_side == "OVER"
                        else p.get("under_odds", -110)
                    )
                    best_book = (
                        p.get("best_over_book", "")
                        if best_side == "OVER"
                        else p.get("best_under_book", "")
                    ) or p.get("best_book", "")
                    home = p.get("home_team", "")
                    away = p.get("away_team", "")
                    game = f"{away} @ {home}" if home and away else p.get("opponent", "")
                    stat_label = _STAT_DISPLAY.get(p.get("stat_type", ""), p.get("stat_type", "").upper())
                    ev_class = (p.get("ev_classification", "") or "").replace("_", " ").title()

                    rows.append([
                        today,
                        game,
                        p.get("player_name", ""),
                        f"Player Prop – {stat_label}",
                        p.get("line", 0),
                        best_side,
                        _fmt_odds(odds),
                        best_book,
                        round(edge * 100, 2),
                        kelly_dollars,
                        ev_class,
                        "",   # ✓ Placed? — user fills in Y
                        "",   # Bet ID — filled by sync_betslip.py
                        "pending",
                        "",   # P/L
                        "",   # Notes
                    ])

            # ── NBA game bets ──
            if nba_bets:
                for b in nba_bets:
                    home = b.get("home_team", "")
                    away = b.get("away_team", "")
                    game = f"{away} @ {home}" if home and away else b.get("game_id", "")
                    pick = b.get("pick", b.get("side", ""))
                    market = b.get("market", "spread")
                    odds = b.get("odds", -110)
                    edge = float(b.get("edge", 0) or 0)
                    kelly_dollars = round(float(b.get("bet_size", 0) or 0), 2)

                    rows.append([
                        today,
                        game,
                        pick,
                        f"NBA – {market.title()}",
                        b.get("line", ""),
                        pick,
                        _fmt_odds(odds),
                        "",
                        round(edge * 100, 2),
                        kelly_dollars,
                        "Game Bet",
                        "",
                        "",
                        "pending",
                        "",
                        "",
                    ])

            # ── NCAAB game bets ──
            if ncaab_data and ncaab_data.get("qualifying_bets"):
                for b in ncaab_data["qualifying_bets"]:
                    home = b.get("home_team", b.get("home", ""))
                    away = b.get("away_team", b.get("away", ""))
                    game = f"{away} @ {home}" if home and away else ""
                    pick = b.get("pick", b.get("side", ""))
                    market = b.get("market", "spread")
                    odds = b.get("odds", -110)
                    edge = float(b.get("edge", 0) or 0)
                    kelly_dollars = round(float(b.get("bet_size", 0) or 0), 2)

                    rows.append([
                        today,
                        game,
                        pick,
                        f"NCAAB – {market.title()}",
                        b.get("line", ""),
                        pick,
                        _fmt_odds(odds),
                        "",
                        round(edge * 100, 2),
                        kelly_dollars,
                        "Game Bet",
                        "",
                        "",
                        "pending",
                        "",
                        "",
                    ])

            if not rows:
                logger.info("BetSlip: no qualifying bets to export")
                return {"status": "success", "tab": tab_name, "rows_written": 0}

            written = self._batch_write(ws, headers, rows)

            # ── Formatting ──
            try:
                # Dark green header
                self._format_tab_header(ws, "#0D3B1F", len(headers))
                # "✓ Placed?" column (L = index 11) — yellow bg
                ws.format(f"L2:L{written + 1}", {
                    "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.6},
                    "textFormat": {"bold": True},
                })
                # Status column (N = index 13) conditional coloring
                self._apply_column_conditional(sheet, ws, 13, [
                    {"type": "TEXT_EQ", "value": "won",     "bg": "#C6EFCE", "fg": "#276221", "bold": True},
                    {"type": "TEXT_EQ", "value": "lost",    "bg": "#FFC7CE", "fg": "#9C0006", "bold": True},
                    {"type": "TEXT_EQ", "value": "push",    "bg": "#EEEEEE", "fg": "#555555", "bold": False},
                    {"type": "TEXT_EQ", "value": "pending", "bg": "#FFEB9C", "fg": "#9C6500", "bold": False},
                ], written)
                # Column widths: Date|Game|Player|Stat|Line|Side|Odds|Book|Edge%|Kelly$|EVClass|Placed?|BetID|Status|P/L|Notes
                self._set_column_widths(sheet, ws, [80, 180, 160, 130, 55, 55, 60, 90, 60, 65, 90, 75, 120, 80, 65, 140])

                # ── Data validation: checkboxes + dropdowns ──
                ws_id = ws.id
                dv_requests = []
                if written > 0:
                    data_range = {
                        "sheetId": ws_id,
                        "startRowIndex": 1,   # row 2 (0-indexed)
                        "endRowIndex": written + 1,
                    }
                    # Col L (index 11): checkbox for ✓ Placed?
                    dv_requests.append({
                        "setDataValidation": {
                            "range": {**data_range, "startColumnIndex": 11, "endColumnIndex": 12},
                            "rule": {
                                "condition": {"type": "BOOLEAN"},
                                "showCustomUi": True,
                                "strict": False,
                            },
                        }
                    })
                    # Col F (index 5): Side dropdown
                    dv_requests.append({
                        "setDataValidation": {
                            "range": {**data_range, "startColumnIndex": 5, "endColumnIndex": 6},
                            "rule": {
                                "condition": {
                                    "type": "ONE_OF_LIST",
                                    "values": [
                                        {"userEnteredValue": "OVER"},
                                        {"userEnteredValue": "UNDER"},
                                        {"userEnteredValue": "HOME"},
                                        {"userEnteredValue": "AWAY"},
                                    ],
                                },
                                "showCustomUi": True,
                                "strict": False,
                            },
                        }
                    })
                    # Col N (index 13): Status dropdown
                    dv_requests.append({
                        "setDataValidation": {
                            "range": {**data_range, "startColumnIndex": 13, "endColumnIndex": 14},
                            "rule": {
                                "condition": {
                                    "type": "ONE_OF_LIST",
                                    "values": [
                                        {"userEnteredValue": "pending"},
                                        {"userEnteredValue": "won"},
                                        {"userEnteredValue": "lost"},
                                        {"userEnteredValue": "push"},
                                    ],
                                },
                                "showCustomUi": True,
                                "strict": False,
                            },
                        }
                    })
                if dv_requests:
                    sheet.batch_update({"requests": dv_requests})

            except Exception as fmt_err:
                logger.debug(f"BetSlip formatting skipped: {fmt_err}")

            logger.info(f"Exported {written} bets to BetSlip tab (fill '✓ Placed?' with Y to track)")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"BetSlip export failed: {e}")
            return {"error": str(e)}

    def export_bet_tracker(
        self,
        spreadsheet_id: str,
        book: Optional[str] = None,
        tab_name: str = "BetTracker",
    ) -> Dict[str, Any]:
        """
        Export all tracked bets (pending + settled) from BetTracker to a
        dedicated Google Sheets tab, showing P&L, CLV, and ROI per bet.

        Args:
            spreadsheet_id: Target Google Sheets ID.
            book:           Filter to a specific book (e.g. "fanduel").
                            Defaults to settings.PRIMARY_BOOK.
            tab_name:       Worksheet tab name.

        Columns:
            Date | Sport | Game / Side | Market | Odds | Line | Edge% |
            Kelly$ | Book | Status | CLV | P/L $ | Settled
        """
        if not self.client:
            return {"error": "Google Sheets not configured"}

        from app.services.bet_tracker import BetTracker
        from app.config import settings

        target_book = (book or settings.PRIMARY_BOOK).lower()

        try:
            tracker = BetTracker()
            # Fetch all bets (pending + resolved)
            if tracker.use_supabase:
                try:
                    res = tracker.supabase.client.table("bets").select("*").execute()
                    all_bets = res.data or []
                except Exception as exc:
                    logger.error(f"Supabase bets fetch failed: {exc}")
                    all_bets = []
            else:
                all_bets = tracker._get_resolved_sqlite() + tracker._get_pending_sqlite("nba") + tracker._get_pending_sqlite("ncaab")

            # Filter to primary book
            filtered = [b for b in all_bets if (b.get("book") or "").lower() == target_book]
            if not filtered:
                # If no book tag yet, show all (backward compat with old records)
                filtered = all_bets

            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name, rows=2000, cols=13)

            headers = [
                "Date", "Sport", "Side / Pick", "Market",
                "Odds", "Line", "Edge %", "Kelly $",
                "Book", "Status", "CLV", "P/L $", "Settled At",
            ]

            rows: List[List[Any]] = []
            for b in sorted(filtered, key=lambda x: x.get("date", ""), reverse=True):
                odds = int(b.get("odds") or -110)
                size = float(b.get("bet_size") or 0)
                status = b.get("status", "pending")
                clv = b.get("actual_clv")

                # Calculate P/L
                pl = 0.0
                if status == "won" and size > 0:
                    if odds < 0:
                        pl = round(size * 100.0 / abs(odds), 2)
                    else:
                        pl = round(size * odds / 100.0, 2)
                elif status == "lost":
                    pl = -size

                rows.append([
                    b.get("date", ""),
                    (b.get("sport") or "").upper(),
                    b.get("side", ""),
                    b.get("market", ""),
                    _fmt_odds(odds),
                    b.get("line", ""),
                    round(float(b.get("edge") or 0) * 100, 2),
                    round(size, 2),
                    b.get("book") or target_book,
                    status,
                    round(float(clv), 3) if clv is not None else "",
                    pl,
                    b.get("settled_at", ""),
                ])

            if not rows:
                return {"status": "success", "tab": tab_name, "rows_written": 0}

            written = self._batch_write(ws, headers, rows)

            # Header formatting — dark navy for tracker tab
            try:
                ws.format(
                    "A1:M1",
                    {
                        "backgroundColor": {"red": 0.1, "green": 0.15, "blue": 0.35},
                        "textFormat": {
                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "bold": True,
                            "fontSize": 11,
                        },
                    },
                )
                # Colour-code Status column (I = col 10)
                for i, b in enumerate(filtered, start=2):
                    status = b.get("status", "pending")
                    colour = (
                        {"red": 0.8, "green": 1.0, "blue": 0.8} if status == "won"
                        else {"red": 1.0, "green": 0.8, "blue": 0.8} if status == "lost"
                        else {"red": 1.0, "green": 0.95, "blue": 0.7}  # pending = yellow
                    )
                    ws.format(f"J{i}", {"backgroundColor": colour})
            except Exception as fmt_err:
                logger.debug(f"BetTracker formatting skipped: {fmt_err}")

            logger.info(
                f"Exported {written} bets to BetTracker tab "
                f"(book={target_book})"
            )
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as exc:
            logger.error(f"BetTracker export failed: {exc}")
            return {"error": str(exc)}
