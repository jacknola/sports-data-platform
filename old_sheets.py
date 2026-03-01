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
from itertools import combinations

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

            all_props = prop_data.get("props", [])
            max_rows = int((prop_data or {}).get("export_max_rows", 120) or 120)

            filtered_props: List[Dict[str, Any]] = []
            for p in all_props:
                edge = float(p.get("bayesian_edge", 0) or 0)
                kelly = float(p.get("kelly_fraction", 0) or 0)
                ev_class = (p.get("ev_classification", "") or "").lower()
                if ev_class == "pass" and kelly <= 0:
                    continue
                if edge <= 0 and kelly <= 0:
                    continue
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
                        _fmt_odds(int(odds)),
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
                        _fmt_odds(int(p.get("over_odds", -110))),
                        _fmt_odds(int(p.get("under_odds", -110))),
                    ]
                )

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
                home_prob = p.get("moneyline_prediction", {}).get("home_win_prob", 0.5)
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
                home_edge = ev.get("home_ev", 0)
                away_edge = ev.get("away_ev", 0)
                best_edge = (
                    home_edge
                    if best_bet == "home"
                    else away_edge
                    if best_bet == "away"
                    else 0
                )
                kelly = p.get("kelly_criterion", 0)

                has_positive_reco = bool(best_bet) and best_edge > 0
                best_side = (
                    home if best_bet == "home" else away if best_bet == "away" else ""
                )

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
                        f"{best_side} ({best_bet.upper()})"
                        if has_positive_reco
                        else "",
                        round(best_edge * 100, 2) if has_positive_reco else "",
                        round(kelly * 100, 2)
                        if (has_positive_reco and kelly > 0)
                        else "",
                        round(bet_size, 2) if bet_size else "",
                    ]
                )

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

                # Efficiency stats
                h_eff = game.get("home_eff") or {}
                a_eff = game.get("away_eff") or {}

                # Fallbacks for empty efficiency data: try to expose partial data from the game object
                def _eff_empty(eff):
                    if not isinstance(eff, dict):
                        return True
                    return not any(v not in (None, "", 0) for v in eff.values())

                if _eff_empty(h_eff):
                    h_eff = {
                        "AdjOE": game.get("home_adj_oe", "") or "",
                        "AdjDE": game.get("home_adj_de", "") or "",
                        "BPI": game.get("home_bpi", "") or "",
                    }

                if _eff_empty(a_eff):
                    a_eff = {
                        "AdjOE": game.get("away_adj_oe", "") or "",
                        "AdjDE": game.get("away_adj_de", "") or "",
                        "BPI": game.get("away_bpi", "") or "",
                    }

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

            total_exposure = sum(
                b.get("bet_size_$", 0) for b in (ncaab_data or {}).get("bets", [])
            ) + sum(b.get("bet_size", 0) for b in (nba_bets or []))

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

    def export_parlays(
        self,
        spreadsheet_id: str,
        ncaab_data: Optional[Dict[str, Any]] = None,
        nba_predictions: Optional[List[Dict[str, Any]]] = None,
        prop_data: Optional[Dict[str, Any]] = None,
        tab_name: str = "Parlays",
    ) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Google Sheets not configured"}

        def _am_to_dec(odds: int) -> float:
            if odds > 0:
                return (odds / 100.0) + 1.0
            return (100.0 / abs(odds)) + 1.0

        def _dec_to_am(dec: float) -> int:
            if dec <= 1.0:
                return 0
            if dec >= 2.0:
                return int(round((dec - 1.0) * 100))
            return int(round(-100 / (dec - 1.0)))

        def _fmt_parlay_name(pid: int, legs_count: int) -> str:
            return f"PARLAY-{pid:02d}-{legs_count}LEG"

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = self._get_or_create_worksheet(sheet, tab_name)

            headers = [
                "Date",
                "Parlay ID",
                "Leg #",
                "Source",
                "Selection",
                "Market",
                "Line",
                "Odds",
                "Edge %",
                "Kelly %",
                "Confidence",
                "Parlay Decimal",
                "Parlay Odds",
                "Notes",
            ]

            today = datetime.now().strftime("%Y-%m-%d")
            candidates: List[Dict[str, Any]] = []

            for p in nba_predictions or []:
                if "error" in p:
                    continue
                ev = p.get("expected_value", {})
                best_bet = ev.get("best_bet")
                if best_bet not in ("home", "away"):
                    continue
                home = p.get("home_team", "")
                away = p.get("away_team", "")
                edge = (
                    ev.get("home_ev", 0) if best_bet == "home" else ev.get("away_ev", 0)
                )
                if edge <= 0:
                    continue
                odds = (
                    ev.get("home_odds", 0)
                    if best_bet == "home"
                    else ev.get("away_odds", 0)
                )
                if not odds:
                    continue
                kelly = p.get("kelly_criterion", 0) or 0
                selection = f"{home if best_bet == 'home' else away} ML"
                candidates.append(
                    {
                        "source": "NBA",
                        "selection": selection,
                        "market": "Moneyline",
                        "line": "",
                        "odds": int(odds),
                        "edge": float(edge),
                        "kelly": float(kelly),
                        "confidence": "HIGH"
                        if edge >= 0.07
                        else "MEDIUM"
                        if edge >= 0.04
                        else "LOW",
                        "notes": f"{away} @ {home}",
                    }
                )

            for b in (ncaab_data or {}).get("bets", []):
                edge = float(b.get("edge", 0) or 0)
                if edge <= 0:
                    continue
                odds = int(b.get("odds", 0) or 0)
                if not odds:
                    continue
                candidates.append(
                    {
                        "source": "NCAAB",
                        "selection": b.get("side", ""),
                        "market": b.get("market", "Spread"),
                        "line": b.get("line", ""),
                        "odds": odds,
                        "edge": edge,
                        "kelly": float(
                            (b.get("portfolio_fraction_pct", 0) or 0) / 100.0
                        ),
                        "confidence": "HIGH"
                        if edge >= 0.07
                        else "MEDIUM"
                        if edge >= 0.04
                        else "LOW",
                        "notes": b.get("game_id", ""),
                    }
                )

            prop_pool = (
                (prop_data or {}).get("best_props")
                or (prop_data or {}).get("props")
                or []
            )
            for p in prop_pool:
                edge = float(p.get("bayesian_edge", 0) or 0)
                kelly = float(p.get("kelly_fraction", 0) or 0)
                if edge <= 0 and kelly <= 0:
                    continue
                side = (p.get("best_side", "over") or "over").lower()
                odds = int(
                    p.get("over_odds", -110)
                    if side == "over"
                    else p.get("under_odds", -110)
                )
                candidates.append(
                    {
                        "source": "PROPS",
                        "selection": f"{p.get('player_name', '')} {side.upper()}",
                        "market": p.get("stat_type", ""),
                        "line": p.get("line", ""),
                        "odds": odds,
                        "edge": edge,
                        "kelly": kelly,
                        "confidence": "HIGH"
                        if edge >= 0.07
                        else "MEDIUM"
                        if edge >= 0.04
                        else "LOW",
                        "notes": p.get("team", ""),
                    }
                )

            candidates.sort(
                key=lambda x: (x.get("kelly", 0), x.get("edge", 0)), reverse=True
            )
            candidates = candidates[:12]

            rows: List[List[Any]] = []
            parlay_id = 1

            combos: List[List[Dict[str, Any]]] = []
            for n in (2, 3):
                for combo in combinations(candidates, n):
                    srcs = {c["source"] for c in combo}
                    if len(srcs) < min(n, 2):
                        continue
                    combos.append(list(combo))

            def _combo_score(combo: List[Dict[str, Any]]) -> float:
                dec = 1.0
                for leg in combo:
                    dec *= _am_to_dec(int(leg["odds"]))
                avg_edge = sum(float(l.get("edge", 0)) for l in combo) / len(combo)
                avg_kelly = sum(float(l.get("kelly", 0)) for l in combo) / len(combo)
                return (avg_edge * 0.6) + (avg_kelly * 0.3) + (min(dec, 20.0) * 0.01)

            combos.sort(key=_combo_score, reverse=True)
            combos = combos[:10]

            for combo in combos:
                parlay_dec = 1.0
                for leg in combo:
                    parlay_dec *= _am_to_dec(int(leg["odds"]))
                parlay_am = _dec_to_am(parlay_dec)
                pid = _fmt_parlay_name(parlay_id, len(combo))
                parlay_id += 1

                for idx, leg in enumerate(combo, start=1):
                    rows.append(
                        [
                            today,
                            pid,
                            idx,
                            leg.get("source", ""),
                            leg.get("selection", ""),
                            leg.get("market", ""),
                            leg.get("line", ""),
                            _fmt_odds(int(leg.get("odds", -110))),
                            round(float(leg.get("edge", 0)) * 100, 2),
                            round(float(leg.get("kelly", 0)) * 100, 2),
                            leg.get("confidence", ""),
                            round(parlay_dec, 3),
                            _fmt_odds(parlay_am) if parlay_am else "",
                            leg.get("notes", ""),
                        ]
                    )

            written = self._batch_write(ws, headers, rows)
            logger.info(f"Exported {written} parlay rows to tab '{tab_name}'")
            return {
                "status": "success",
                "tab": tab_name,
                "rows_written": written,
                "candidate_legs": len(candidates),
                "parlays_built": len(combos),
            }
        except Exception as e:
            logger.error(f"Parlay export failed: {e}")
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
            qdrant_used = any(
                ga.get("qdrant_retrieved", False)
                for ga in (ncaab_data.get("game_analyses") or [])
            )
            if qdrant_used:
                logger.info(
                    "Qdrant context present — including historical context in Sheets export"
                )
            results["ncaab"] = self.export_ncaab(spreadsheet_id, ncaab_data)

        if nba_predictions or ncaab_data or prop_data:
            results["parlays"] = self.export_parlays(
                spreadsheet_id,
                ncaab_data=ncaab_data,
                nba_predictions=nba_predictions,
                prop_data=prop_data,
            )

        results["summary"] = self.export_summary(
            spreadsheet_id,
            ncaab_data=ncaab_data,
            nba_predictions=nba_predictions,
            nba_bets=nba_bets,
            prop_data=prop_data,
        )

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
    # ───────────────────────────────────────────────────────────────
    # High-Value Props export
    # ───────────────────────────────────────────────────────────────

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
                odds_val = p.get("over_odds", -110) if best_side == "OVER" else p.get("under_odds", -110)
                
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
                        _fmt_odds(int(odds)),
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
                        _fmt_odds(int(p.get("over_odds", -110))),
                        _fmt_odds(int(p.get("under_odds", -110))),
                    ]
                )

            written = self._batch_write(ws, headers, rows)
            
            # --- Advanced Formatting ---
            try:
                # Format headers
                ws.format("A1:U1", {
                    "backgroundColor": {
                        "red": 0.2,
                        "green": 0.2,
                        "blue": 0.2
                    },
                    "textFormat": {
                        "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                        "bold": True,
                        "fontSize": 11
                    }
                })

                # Conditional formatting rules using raw API via batch_update
                rule_edge_high = {
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{"sheetId": ws.id, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11}],
                            "booleanRule": {
                                "condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "5"}]},
                                "format": {"backgroundColor": {"red": 0.85, "green": 0.93, "blue": 0.83}, "textFormat": {"bold": True, "foregroundColor": {"red": 0.1, "green": 0.4, "blue": 0.1}}}
                            }
                        }, "index": 0
                    }
                }
                
                rule_edge_med = {
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{"sheetId": ws.id, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11}],
                            "booleanRule": {
                                "condition": {"type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "3"}, {"userEnteredValue": "4.99"}]},
                                "format": {"backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}, "textFormat": {"bold": True, "foregroundColor": {"red": 0.5, "green": 0.4, "blue": 0.0}}}
                            }
                        }, "index": 1
                    }
                }

                rule_conf_high = {
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{"sheetId": ws.id, "startRowIndex": 1, "startColumnIndex": 13, "endColumnIndex": 14}],
                            "booleanRule": {
                                "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "HIGH"}]},
                                "format": {"backgroundColor": {"red": 0.85, "green": 0.93, "blue": 0.83}, "textFormat": {"bold": True}}
                            }
                        }, "index": 2
                    }
                }

                sheet.batch_update({"requests": [rule_edge_high, rule_edge_med, rule_conf_high]})
                logger.info("Applied conditional formatting to HighValueProps")
                
            except Exception as fmt_err:
                logger.warning(f"Failed to apply formatting to HighValueProps: {fmt_err}")

            logger.info(f"Exported {written} props to Google Sheets tab '{tab_name}'")
            return {"status": "success", "tab": tab_name, "rows_written": written}

        except Exception as e:
            logger.error(f"High-value props export failed: {e}")
            return {"error": str(e)}
