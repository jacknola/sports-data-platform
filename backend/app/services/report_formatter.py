"""
Report Formatter

Converts raw analysis output (plain text from run_ncaab_analysis.py)
into Telegram-ready HTML with structured sections, emoji indicators,
and proper escaping of reserved characters.

Telegram HTML allowed tags: <b>, <i>, <u>, <code>, <pre>, <a href>
"""

import re
from datetime import datetime
from typing import Optional


# Emoji tier indicators
_EMOJI_STRONG = "🟢"   # edge ≥ 5%
_EMOJI_PLAY = "🟡"     # edge 2.5–5%
_EMOJI_PASS = "⚪"     # below threshold
_EMOJI_SIGNAL = "⚡"   # sharp signal detected
_EMOJI_WARN = "⚠️"    # risk warning


class ReportFormatter:
    """Formats analysis output for Telegram delivery."""

    # ------------------------------------------------------------------
    # Primary entry points
    # ------------------------------------------------------------------

    @staticmethod
    def format_full_report(raw_output: str, bankroll: float = 10_000.0) -> str:
        """
        Convert full run_ncaab_analysis.py stdout to Telegram HTML.

        Args:
            raw_output: Captured stdout from run_analysis()
            bankroll: Current bankroll for context display

        Returns:
            HTML-formatted string ready for TelegramService.send_message()
        """
        sections = ReportFormatter._parse_sections(raw_output)
        parts = []

        # Portfolio summary block (most important — goes first after header)
        if sections.get("portfolio"):
            parts.append(ReportFormatter._format_portfolio(sections["portfolio"]))

        # Top plays block
        if sections.get("top_plays"):
            parts.append(ReportFormatter._format_top_plays(sections["top_plays"]))

        # Game-by-game breakdown (detailed, goes last since it's long)
        if sections.get("games"):
            parts.append(ReportFormatter._format_games(sections["games"]))

        # Fallback: send raw output wrapped in <pre> if parsing failed
        if not parts:
            return f"<pre>{ReportFormatter._escape(raw_output[:3800])}</pre>"

        return "\n\n".join(parts)

    @staticmethod
    def format_picks_only(raw_output: str) -> str:
        """
        Extract and format only the top ranked plays — compact version
        suitable for a quick-glance summary message.

        Args:
            raw_output: Captured stdout from run_analysis()

        Returns:
            Compact HTML picks list
        """
        sections = ReportFormatter._parse_sections(raw_output)
        plays = sections.get("top_plays", [])

        if not plays:
            return "<b>No qualifying plays identified.</b>"

        lines = [f"<b>{_EMOJI_PLAY} TOP PLAYS — QUICK VIEW</b>\n"]
        for play in plays[:6]:
            signals = play.get("signals", "Model only")
            edge = play.get("edge_raw", 0.0)
            emoji = _EMOJI_STRONG if edge >= 0.05 else _EMOJI_PLAY
            lines.append(
                f"{emoji} <b>{play['bet_on']} {play['odds']}</b>\n"
                f"   <i>{play['matchup']}</i>\n"
                f"   Edge <code>{play['edge']}</code> | {signals}"
            )

        return "\n\n".join(lines)

    # ------------------------------------------------------------------
    # Section parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_sections(raw: str) -> dict:
        """
        Parse raw stdout into named sections.

        Returns dict with keys: portfolio, top_plays, games, metadata
        """
        result = {"portfolio": "", "top_plays": [], "games": [], "metadata": {}}

        lines = raw.split("\n")

        # Extract metadata from first few lines
        for line in lines[:5]:
            if "Bankroll" in line or "BANKROLL" in line:
                result["metadata"]["bankroll_line"] = line.strip()
            if "Games analyzed" in line:
                m = re.search(r"Games analyzed:\s*(\d+)", line)
                if m:
                    result["metadata"]["games_analyzed"] = int(m.group(1))
                m2 = re.search(r"Opportunities.*?:\s*(\d+)", line)
                if m2:
                    result["metadata"]["opportunities"] = int(m2.group(1))

        # Split by major section headers
        current_section = None
        portfolio_lines = []
        top_plays_lines = []
        game_lines = []

        for line in lines:
            if "PORTFOLIO SUMMARY" in line:
                current_section = "portfolio"
                continue
            if "TOP PLAYS" in line and "RANKED" in line:
                current_section = "top_plays"
                continue
            if "GAME-BY-GAME" in line:
                current_section = "games"
                continue
            if "RISK FRAMEWORK" in line:
                current_section = None
                continue

            if current_section == "portfolio":
                portfolio_lines.append(line)
            elif current_section == "top_plays":
                top_plays_lines.append(line)
            elif current_section == "games":
                game_lines.append(line)

        result["portfolio"] = "\n".join(portfolio_lines)
        result["top_plays"] = ReportFormatter._parse_top_plays(top_plays_lines)
        result["games"] = ReportFormatter._parse_games(game_lines)

        return result

    @staticmethod
    def _parse_top_plays(lines: list) -> list:
        """Parse the TOP PLAYS section into structured dicts."""
        plays = []
        current = {}

        for line in lines:
            line = line.strip()
            if not line or line.startswith("=") or line.startswith("─"):
                if current:
                    plays.append(current)
                    current = {}
                continue

            # Line like: #1  Alabama Crimson Tide (-108)
            m = re.match(r"#(\d+)\s+(.+?)\s+\(([+-]\d+)\)", line)
            if m:
                current = {
                    "rank": int(m.group(1)),
                    "bet_on": m.group(2).strip(),
                    "odds": m.group(3),
                    "matchup": "",
                    "edge": "",
                    "edge_raw": 0.0,
                    "signals": "",
                }
                continue

            if current:
                if "Matchup:" in line:
                    current["matchup"] = line.replace("Matchup:", "").strip()
                elif "Edge:" in line:
                    current["edge"] = re.search(r"Edge:\s*([+\-\d.]+%)", line)
                    if current["edge"]:
                        raw_edge = current["edge"].group(1).replace("%", "")
                        try:
                            current["edge_raw"] = float(raw_edge) / 100
                        except ValueError:
                            current["edge_raw"] = 0.0
                        current["edge"] = current["edge"].group(1)
                    signal_m = re.search(r"Signal:\s*([^|]+)", line)
                    if signal_m:
                        current["signals"] = signal_m.group(1).strip()

        if current:
            plays.append(current)

        return plays

    @staticmethod
    def _parse_games(lines: list) -> list:
        """Parse game-by-game lines into structured dicts."""
        games = []
        current = {}

        for line in lines:
            line = line.strip()
            if not line:
                if current.get("matchup"):
                    games.append(current)
                    current = {}
                continue

            if " @ " in line and not line.startswith("[") and not line.startswith("*"):
                current = {"matchup": line, "details": []}
                continue

            if current:
                if line.startswith("★ BET:"):
                    current.setdefault("bets", []).append(
                        line.replace("★ BET:", "").strip()
                    )
                elif line.startswith("→ PASS"):
                    current["pass"] = True
                elif line.startswith("Note:"):
                    current["note"] = line.replace("Note:", "").strip()
                elif "Sharp Signals:" in line:
                    current["sharp"] = line.replace("Sharp Signals:", "").strip()
                else:
                    current["details"].append(line)

        if current.get("matchup"):
            games.append(current)

        return games

    # ------------------------------------------------------------------
    # HTML formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _format_portfolio(raw: str) -> str:
        """Format the portfolio summary section."""
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        out = [f"<b>📈 PORTFOLIO SUMMARY</b>"]

        for line in lines:
            if line.startswith("─") or line.startswith("="):
                continue
            # Highlight the total row
            if line.startswith("TOTAL"):
                out.append(f"<b><code>{line}</code></b>")
            elif "PASS" in line or "no bets" in line.lower():
                out.append(f"{_EMOJI_PASS} <i>{line}</i>")
            elif any(c.isdigit() for c in line):
                out.append(f"<code>{line}</code>")
            else:
                out.append(line)

        return "\n".join(out)

    @staticmethod
    def _format_top_plays(plays: list) -> str:
        """Format the ranked top plays into Telegram HTML."""
        if not plays:
            return f"{_EMOJI_PASS} <i>No qualifying plays today.</i>"

        lines = [f"<b>{_EMOJI_PLAY} TOP PLAYS</b>"]

        for p in plays[:8]:
            edge_raw = p.get("edge_raw", 0.0)
            emoji = _EMOJI_STRONG if edge_raw >= 0.05 else _EMOJI_PLAY
            signal_tag = (
                f" {_EMOJI_SIGNAL}" if p.get("signals") and "Model only" not in p["signals"]
                else ""
            )
            lines.append(
                f"\n{emoji} <b>#{p['rank']} — {p['bet_on']} "
                f"<code>{p['odds']}</code></b>{signal_tag}\n"
                f"   <i>{p['matchup']}</i>\n"
                f"   Edge: <code>{p['edge']}</code>  |  {p['signals'] or 'Model only'}"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_games(games: list) -> str:
        """Format game-by-game breakdown (abbreviated for Telegram)."""
        if not games:
            return ""

        lines = [f"<b>🏀 GAME BREAKDOWN</b>"]

        for g in games:
            matchup = ReportFormatter._escape(g.get("matchup", ""))
            lines.append(f"\n<b>{matchup}</b>")

            # Sharp signals
            if g.get("sharp") and "None" not in g["sharp"]:
                lines.append(f"  {_EMOJI_SIGNAL} <i>{g['sharp']}</i>")

            # Key stats (first 3 detail lines that have numbers)
            detail_count = 0
            for d in g.get("details", []):
                if any(c.isdigit() for c in d) and detail_count < 3:
                    lines.append(f"  <code>{d}</code>")
                    detail_count += 1

            # Bets
            for bet in g.get("bets", []):
                lines.append(f"  {_EMOJI_STRONG} <b>BET: {bet}</b>")

            if g.get("pass"):
                lines.append(f"  {_EMOJI_PASS} PASS")

            if g.get("note"):
                note = ReportFormatter._escape(g["note"][:120])
                lines.append(f"  <i>{note}</i>")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _escape(text: str) -> str:
        """Escape HTML reserved characters for Telegram HTML parse mode."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
