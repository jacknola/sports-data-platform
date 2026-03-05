"""
Report Formatter

Converts raw analysis output (plain text from run_ncaab_analysis.py)
into Telegram-ready HTML with structured sections, emoji indicators,
and proper escaping of reserved characters.

Telegram HTML allowed tags: <b>, <i>, <u>, <code>, <pre>, <a href>
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# Emoji tier indicators
_EMOJI_STRONG = "🟢"  # edge ≥ 5%
_EMOJI_PLAY = "🟡"  # edge 2.5–5%
_EMOJI_PASS = "⚪"  # below threshold
_EMOJI_SIGNAL = "⚡"  # sharp signal detected
_EMOJI_WARN = "⚠️"  # risk warning
_EMOJI_FANDUEL = "🎯"  # best odds on FanDuel (user's primary book)


class ReportFormatter:
    """Formats analysis output for Telegram delivery."""

    # ------------------------------------------------------------------
    # Primary entry points
    # ------------------------------------------------------------------

    @staticmethod
    def format_full_report(raw_output: str, metrics: Optional[dict] = None) -> str:
        """
        Convert full run_ncaab_analysis.py stdout to Telegram HTML.

        Args:
            raw_output: Captured stdout from run_analysis()
            metrics: Optional dict of performance metrics (W/L, ROI)

        Returns:
            HTML-formatted string ready for TelegramService.send_message()
        """
        sections = ReportFormatter._parse_sections(raw_output)
        parts = []

        # Add W/L Record Header if metrics provided
        if metrics and metrics.get("total_bets", 0) > 0:
            w = metrics.get("wins", 0)
            l = metrics.get("losses", 0)
            p = metrics.get("pushes", 0)
            win_rate = metrics.get("win_rate", 0.0) * 100
            units = metrics.get("units", 0.0)
            roi = metrics.get("roi", 0.0) * 100

            push_str = f"-{p}" if p > 0 else ""
            record_str = (
                f"<b>📈 Season Record:</b> {w}-{l}{push_str} ({win_rate:.1f}%)\n"
            )
            record_str += f"<b>💰 Profit:</b> {units:+.2f}U | <b>ROI:</b> {roi:+.1f}%\n"
            record_str += f"<i>Based on {metrics.get('total_bets')} tracked bets</i>"
            parts.append(record_str)

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
        for play in plays[:20]:
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
        out = ["<b>📈 PORTFOLIO SUMMARY</b>"]

        for line in lines:
            if line.startswith("─") or line.startswith("="):
                continue
            # Highlight the total row
            if line.startswith("TOTAL"):
                out.append(f"<b><code>{line}</code></b>")
            elif "PASS" in line or "no bets" in line.lower():
                out.append(f"{_EMOJI_PASS} <i>{line}</i>")
            elif any(c.isdigit() for c in line):
                out.append(f"<code>{ReportFormatter._escape(line)}</code>")
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
                f" {_EMOJI_SIGNAL}"
                if p.get("signals") and "Model only" not in p["signals"]
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

        lines = ["<b>🏀 GAME BREAKDOWN</b>"]

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

    # ------------------------------------------------------------------
    # Orchestrator-powered live report
    # ------------------------------------------------------------------

    @staticmethod
    def format_picks_only_live(data: Dict[str, Any]) -> str:
        """Compact picks-only summary from orchestrator data.

        This is the structured-data equivalent of ``format_picks_only()`` —
        used when ``--picks-only`` is passed and the orchestrator is active.

        Returns:
            HTML string with just the ranked picks (no portfolio or breakdown).
        """
        picks: List[Dict[str, Any]] = data.get("picks", [])

        if not picks:
            return f"{_EMOJI_PASS} <b>No qualifying plays on this slate.</b>"

        lines = [
            f"<b>{_EMOJI_PLAY} TOP PICKS — QUICK VIEW</b>\n"
            f"<i>{datetime.now().strftime('%a %b %d, %I:%M %p')}</i>"
        ]
        for i, pick in enumerate(picks, 1):
            bet_on = pick.get("bet_on", pick.get("team", "Unknown"))
            odds = pick.get("odds", "")
            edge = pick.get("edge", 0)
            edge_val = edge if isinstance(edge, float) and edge < 1 else (edge / 100 if isinstance(edge, (int, float)) and edge != 0 else 0)
            emoji = _EMOJI_STRONG if edge_val >= 0.05 else _EMOJI_PLAY
            edge_pct = edge_val * 100
            sport = (pick.get("sport") or "").upper()
            matchup = pick.get("matchup", "")

            odds_str = f"({odds})" if odds else ""
            sport_tag = f"[{sport}] " if sport else ""
            lines.append(
                f"{emoji} <b>#{i} {ReportFormatter._escape(str(bet_on))} "
                f"<code>{odds_str}</code></b>\n"
                f"   {sport_tag}<i>{ReportFormatter._escape(str(matchup))}</i>\n"
                f"   Edge: <code>{edge_pct:.1f}%</code>"
            )

        return "\n\n".join(lines)

    @staticmethod
    def format_live_report(
        data: Dict[str, Any],
        metrics: Optional[dict] = None,
    ) -> str:
        """Format the orchestrated analysis into a live Telegram report.

        This is the primary formatter when the orchestrator pipeline is active.
        It uses structured pick data (not raw stdout) and dynamically adjusts
        the number of picks displayed based on the slate size.

        Args:
            data: Result dict from ``run_orchestrated_analysis()``.
            metrics: Optional performance metrics dict (W/L, ROI).

        Returns:
            HTML string ready for ``TelegramService.send_message()``.
        """
        parts: List[str] = []

        total_games = data.get("total_game_count", 0)
        max_picks = data.get("max_picks", 0)
        picks: List[Dict[str, Any]] = data.get("picks", [])

        ncaab_count = (data.get("ncaab") or {}).get("game_count", 0)
        nba_count = (data.get("nba") or {}).get("game_count", 0)

        # ── Header ──
        # Phase 4: Data source tag — shows where game data came from
        data_source = data.get("data_source", "")
        source_labels = {
            "espn_live": "LIVE - ESPN + Odds API",
            "oddsapi_live": "LIVE - Odds API",
            "oddsapi_events": "LIVE - Odds API Events",
            "cached": "CACHED",
            "stale_cache": "STALE CACHE",
            "fallback": "FALLBACK - STALE DATA",
        }
        source_label = source_labels.get(data_source, "")

        header_lines = [
            f"<b>🔴 LIVE PICKS — {datetime.now().strftime('%a %b %d, %Y %I:%M %p')}</b>"
        ]
        if source_label:
            header_lines.append(f"<code>[{source_label}]</code>")
        header_lines.append(
            f"Slate: <code>{ncaab_count}</code> NCAAB + <code>{nba_count}</code> NBA "
            f"= <code>{total_games}</code> games"
        )
        parts.append("\n".join(header_lines))

        # ── Season Record ──
        if metrics and metrics.get("total_bets", 0) > 0:
            w = metrics.get("wins", 0)
            l = metrics.get("losses", 0)
            p = metrics.get("pushes", 0)
            win_rate = metrics.get("win_rate", 0.0) * 100
            units = metrics.get("units", 0.0)
            roi = metrics.get("roi", 0.0) * 100
            push_str = f"-{p}" if p else ""
            parts.append(
                f"<b>📈 Record:</b> {w}-{l}{push_str} ({win_rate:.1f}%)\n"
                f"<b>💰 Profit:</b> {units:+.2f}U | <b>ROI:</b> {roi:+.1f}%"
            )

        # ── Picks ──
        if not picks:
            parts.append(f"{_EMOJI_PASS} <b>No qualifying plays on this slate.</b>")
        else:
            pick_lines = [
                f"<b>{_EMOJI_PLAY} TOP {len(picks)} PICKS</b> <i>(of {max_picks} max for {total_games}-game slate)</i>"
            ]
            for i, pick in enumerate(picks, 1):
                pick_lines.append(ReportFormatter._format_single_pick(i, pick))
            parts.append("\n\n".join(pick_lines))

        # ── Orchestrator enrichment summary ──
        enrichment = []
        if data.get("orchestrator_ncaab"):
            agents = data["orchestrator_ncaab"].get("agents_used", [])
            enrichment.append(f"NCAAB: {', '.join(set(agents))}")
        if data.get("orchestrator_nba"):
            agents = data["orchestrator_nba"].get("agents_used", [])
            enrichment.append(f"NBA: {', '.join(set(agents))}")
        if enrichment:
            parts.append(f"<i>🤖 Agent enrichment: {' | '.join(enrichment)}</i>")

        # ── Footer ──
        footer_parts = [
            "Bets are LIVE. Dynamic sizing via Multivariate Kelly.",
            "Track CLV on every bet. Line shop before placing.",
        ]

        # Phase 4: API quota display
        quota_remaining = data.get("api_quota_remaining")
        if quota_remaining is not None:
            footer_parts.append(f"API: {quota_remaining} requests remaining")

        parts.append(f"<i>{'  '.join(footer_parts)}</i>")

        return "\n\n".join(parts)

    @staticmethod
    def _format_single_pick(rank: int, pick: Dict[str, Any]) -> str:
        """Render one pick as a Telegram HTML block."""
        bet_on = pick.get("bet_on", pick.get("team", "Unknown"))
        matchup = pick.get("matchup", "")
        sport = (pick.get("sport") or "").upper()
        odds = pick.get("odds", "")
        edge = pick.get("edge", 0)
        edge_pct = edge * 100 if isinstance(edge, float) and edge < 1 else edge
        score = pick.get("score", 0)
        signals = pick.get("signals", "")
        conference = pick.get("conference", "")

        # Choose emoji tier
        if isinstance(edge, (int, float)):
            edge_val = edge if edge < 1 else edge / 100
        else:
            edge_val = 0
        emoji = _EMOJI_STRONG if edge_val >= 0.05 else _EMOJI_PLAY

        # Signal tag
        signal_tag = ""
        if (
            signals
            and "model only" not in str(signals).lower()
            and "none" not in str(signals).lower()
        ):
            signal_tag = f" {_EMOJI_SIGNAL}"

        # FanDuel tag — highlight when best odds are on user's primary book
        fd_tag = ""
        best_book = pick.get("best_book", pick.get("best_over_book", ""))
        if best_book and "fanduel" in str(best_book).lower():
            fd_tag = f" {_EMOJI_FANDUEL}"

        # Sentiment tag (from orchestrator)
        sentiment_tag = ""
        sentiment = pick.get("sentiment", {})
        if sentiment:
            sent_score = sentiment.get("sentiment_score", sentiment.get("score", 0))
            if isinstance(sent_score, (int, float)) and sent_score != 0:
                direction = "📈" if sent_score > 0 else "📉"
                sentiment_tag = f"  |  Sentiment {direction}"

        # Expert tag
        expert_tag = ""
        expert = pick.get("expert", {})
        if expert and expert.get("should_bet"):
            conf = expert.get("confidence", 0)
            if isinstance(conf, (int, float)) and conf > 0:
                expert_tag = f"\n   🧠 Expert: {conf:.0%} confidence"

        # Build the line
        odds_str = f"<code>({odds})</code>" if odds else ""
        edge_str = f"{float(edge_pct):.1f}%"
        sport_tag = f"[{sport}]" if sport else ""
        
        # Market label
        market = pick.get("market", "").lower()
        if not market and pick.get("stat_type"):
            market = "prop"
            
        market_labels = {
            "spread": "SPREAD",
            "total": "TOTAL",
            "moneyline": "ML",
            "ml": "ML",
            "h2h": "ML",
            "prop": "PROP"
        }
        market_label = market_labels.get(market, market.upper())
        market_tag = f" [{market_label}]" if market_label else ""

        # Efficiency metrics for NCAAB
        efficiency_line = ""
        if sport == "NCAAB":
            # Check if we have raw metrics in the pick (from run_ncaab_analysis)
            h_eff = pick.get("home_eff")
            a_eff = pick.get("away_eff")
            if h_eff and a_eff:
                efficiency_line = (
                    f"\n   🏠 <code>AdjOE:{h_eff.get('AdjOE','')} DE:{h_eff.get('AdjDE','')}</code>"
                    f"\n   ✈️ <code>AdjOE:{a_eff.get('AdjOE','')} DE:{a_eff.get('AdjDE','')}</code>"
                )

        line = (
            f"{emoji} <b>#{rank} {ReportFormatter._escape(str(bet_on))} "
            f"{odds_str}</b>{signal_tag}{fd_tag}\n"
            f"   {sport_tag}{market_tag} <i>{ReportFormatter._escape(str(matchup))}</i>\n"
            f"   Edge: <code>{edge_str}</code>  |  Score: <code>{score:.1f}</code>"
            f"{efficiency_line}"
        )
        if signals and str(signals).strip():
            line += f"\n   Signals: {ReportFormatter._escape(str(signals))}"
        if conference:
            line += f"  |  {ReportFormatter._escape(str(conference))}"
        if sentiment_tag:
            line += sentiment_tag
        if expert_tag:
            line += expert_tag

        return line

    # ------------------------------------------------------------------
    # Player Props Report (separate Telegram message)
    # ------------------------------------------------------------------

    @staticmethod
    def format_prop_report(prop_data: Dict[str, Any]) -> str:
        """Format player prop analysis as a standalone Telegram HTML message.

        Args:
            prop_data: Dict from run_prop_analysis() with keys:
                sport, date, total_props, positive_ev_count,
                props (all), best_props (filtered +EV)

        Returns:
            HTML-formatted string for Telegram
        """
        parts: List[str] = []

        total = prop_data.get("total_props", 0)
        best_props = prop_data.get("best_props", [])
        ev_count = prop_data.get("positive_ev_count", 0)

        # ── Header ──
        parts.append(
            f"<b>🏀 NBA PLAYER PROPS — "
            f"{datetime.now().strftime('%a %b %d, %Y %I:%M %p')}</b>"
        )
        parts.append(
            f"Scanned: <code>{total}</code> props  |  +EV: <code>{ev_count}</code>"
        )

        if not best_props:
            parts.append("\n<i>No +EV props found on this slate.</i>")
            return "\n".join(parts)

        # ── Props ──
        parts.append("")  # blank line
        for i, prop in enumerate(best_props, 1):
            parts.append(ReportFormatter._format_single_prop(i, prop))

        # ── Footer ──
        parts.append("")
        parts.append(
            "<i>Props sized via Quarter-Kelly. Line shop before placing. Track CLV.</i>"
        )

        return "\n".join(parts)

    @staticmethod
    def _format_single_prop(rank: int, prop: Dict[str, Any]) -> str:
        """Render a single player prop pick in Telegram HTML format.

        Args:
            rank: Display rank (1-indexed)
            prop: Dict from _build_prop_analysis() with model, sharp, Bayesian keys

        Returns:
            HTML string for one prop pick
        """
        player = prop.get("player_name", "Unknown")
        stat_type = prop.get("stat_type", "")
        line = prop.get("line", 0)
        best_side = prop.get("best_side", "over")
        bayesian_edge = prop.get("bayesian_edge", 0)
        projected_mean = prop.get("projected_mean", 0)
        kelly = prop.get("kelly_fraction", 0)
        sharp_signals = prop.get("sharp_signals", [])
        ev_class = prop.get("ev_classification", "")
        home_team = prop.get("home_team", "")
        away_team = prop.get("away_team", "")
        books_ct = prop.get("books_offering", 0)
        best_book = (
            prop.get("best_over_book", "")
            if best_side == "over"
            else prop.get("best_under_book", "")
        )
        odds = (
            prop.get("over_odds", -110)
            if best_side == "over"
            else prop.get("under_odds", -110)
        )

        # Stat display names
        stat_display = {
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
        }.get(stat_type, stat_type.upper())

        # Edge tier emoji
        edge_pct = bayesian_edge * 100 if isinstance(bayesian_edge, float) else 0
        if edge_pct >= 8:
            emoji = "🟢"
        elif edge_pct >= 5:
            emoji = "🟡"
        elif edge_pct >= 3:
            emoji = "🔵"
        else:
            emoji = "⚪"

        # Sharp signal tag
        signal_tag = ""
        if sharp_signals:
            types = [
                s.get("signal_type", "") if isinstance(s, dict) else str(s)
                for s in sharp_signals
            ]
            signal_tag = f"  ⚡ {', '.join(types)}"

        # EV classification tag
        ev_tag = ""
        if ev_class and ev_class != "pass":
            ev_tag = f"  [{ev_class.replace('_', ' ').title()}]"

        # Matchup line
        matchup = f"{away_team} @ {home_team}" if home_team and away_team else ""

        # Build output
        side_upper = best_side.upper()
        esc = ReportFormatter._escape

        result = (
            f"{emoji} <b>#{rank} {esc(player)} — {side_upper} "
            f"{line} {stat_display} ({odds})</b>{signal_tag}{ev_tag}\n"
        )
        result += "   [PROP] "
        if matchup:
            result += f"<i>{esc(matchup)}</i>\n"
        result += (
            f"   Proj: <code>{projected_mean:.1f}</code>  |  "
            f"Edge: <code>{edge_pct:.1f}%</code>  |  "
            f"Kelly: <code>{kelly:.2%}</code>"
        )
        if best_book:
            fd_tag = f" {_EMOJI_FANDUEL}" if "fanduel" in best_book.lower() else ""
            result += f"\n   Best line: {esc(best_book)} ({books_ct} books){fd_tag}"

        return result

    # ------------------------------------------------------------------
    # DvP Report (separate Telegram message)
    # ------------------------------------------------------------------

    @staticmethod
    def format_dvp_report(dvp_data: Dict[str, Any]) -> str:
        """Format DvP +EV analysis as a standalone Telegram HTML message.

        Args:
            dvp_data: Dict from DvPAgent.execute() with keys:
                task_type, count, high_value_count, projections

        Returns:
            HTML-formatted string for Telegram
        """
        parts: List[str] = []
        projections = dvp_data.get("projections", [])
        high_value = [p for p in projections if "HIGH VALUE" in p.get("Recommendation", "")]
        leans = [p for p in projections if "LEAN" in p.get("Recommendation", "")]

        parts.append(
            f"<b>🎯 DvP PROP TARGETS — "
            f"{datetime.now().strftime('%a %b %d, %Y %I:%M %p')}</b>"
        )
        parts.append(
            f"Projections: <code>{len(projections)}</code>  |  "
            f"HIGH VALUE: <code>{len(high_value)}</code>  |  "
            f"Leans: <code>{len(leans)}</code>"
        )

        if not high_value and not leans:
            parts.append("\n<i>No DvP edges found on this slate.</i>")
            return "\n".join(parts)

        # HIGH VALUE plays first
        for i, p in enumerate(high_value[:8], 1):
            rec = p.get("Recommendation", "")
            side = "OVER" if "OVER" in rec else "UNDER"
            adv = p.get("DvP_Advantage_%", 0)
            emoji = "🟢" if abs(adv) >= 15 else "🟡"
            parts.append(
                f"\n{emoji} <b>#{i} {ReportFormatter._escape(p.get('Player', ''))} "
                f"{side} {p.get('Stat_Category', '')} {p.get('Sportsbook_Line', '')}</b>\n"
                f"   {p.get('Team', '')} vs {p.get('Opponent', '')} [{p.get('Position', '')}]\n"
                f"   Proj: <code>{p.get('Projected_Line', 0)}</code>  |  "
                f"DvP Edge: <code>{adv:+.1f}%</code>"
            )

        # Then leans (up to 4)
        if leans:
            parts.append("\n<b>📊 Leans:</b>")
            for p in leans[:4]:
                rec = p.get("Recommendation", "")
                side = "O" if "OVER" in rec else "U"
                adv = p.get("DvP_Advantage_%", 0)
                parts.append(
                    f"  {side} {ReportFormatter._escape(p.get('Player', ''))} "
                    f"{p.get('Stat_Category', '')} {p.get('Sportsbook_Line', '')} "
                    f"(<code>{adv:+.1f}%</code>)"
                )

        parts.append("\n<i>DvP = Defense vs Position matchup advantage. Cross-ref with prop lines.</i>")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _escape(text: str) -> str:
        """Escape HTML reserved characters for Telegram HTML parse mode."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
