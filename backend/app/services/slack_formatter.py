"""
Slack Block Kit Formatter — Unified Picks Report

Formats NCAAB, NBA, and Player Prop picks into a single Slack Block Kit
message, sectioned by sport and then by game. Each game section shows:
- Sportsbook lines (spread, ML, total) with odds
- Model projected line & probabilities
- Pick(s) with confidence rating & edge
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════
# Confidence / tier helpers
# ═══════════════════════════════════════════════════════════════════════

_CONFIDENCE_TIERS = [
    (0.70, "🟢 MAX"),
    (0.50, "🟢 HIGH"),
    (0.30, "🟡 MEDIUM"),
    (0.15, "🔵 LOW"),
    (0.00, "⚪ PASS"),
]


def _confidence_label(confidence: float) -> str:
    for threshold, label in _CONFIDENCE_TIERS:
        if confidence >= threshold:
            return label
    return "⚪ PASS"


def _fmt_odds(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def _fmt_spread(point: float) -> str:
    return f"+{point}" if point > 0 else str(point)


# ═══════════════════════════════════════════════════════════════════════
# NCAAB Section
# ═══════════════════════════════════════════════════════════════════════


def _ncaab_game_blocks(
    analysis: Dict[str, Any],
    bets_lookup: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build blocks for a single NCAAB game."""
    blocks: List[Dict[str, Any]] = []
    game = analysis["game"]
    home = game["home"]
    away = game["away"]
    spread = game["spread"]
    total = game.get("total", 0)
    conf = game.get("conference", "NCAAB")

    he = analysis["home_edge"]
    ae = analysis["away_edge"]
    signals = analysis.get("sharp_signals", [])
    sharp_side = analysis.get("sharp_side", "")
    sig_conf = analysis.get("signal_confidence", 0)

    # Determine best side confidence for display
    best_edge = max(he, ae)
    if best_edge >= 0.07:
        conf_label = "🟢 HIGH"
    elif best_edge >= 0.05:
        conf_label = "🟡 MEDIUM"
    elif best_edge >= 0.025:
        conf_label = "🔵 LOW"
    else:
        conf_label = "⚪ PASS"

    # Signal tag
    signal_str = ""
    if signals:
        signal_str = f"  ⚡ {', '.join(signals)}"

    # Game header
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{away}  @  {home}*\n[{conf}]  {conf_label}{signal_str}",
        },
    })

    # Sportsbook lines
    lines: List[str] = []
    lines.append(
        f"*Spread:*  {home} `{_fmt_spread(spread)}`  "
        f"({_fmt_odds(game['retail_home_odds'])})  /  "
        f"{away} `{_fmt_spread(-spread)}`  "
        f"({_fmt_odds(game['retail_away_odds'])})"
    )
    lines.append(
        f"*Pinnacle:*  {home} `{_fmt_odds(game['pinnacle_home_odds'])}`  /  "
        f"{away} `{_fmt_odds(game['pinnacle_away_odds'])}`"
    )
    if total:
        lines.append(f"*Total:*  O/U `{total:.1f}`")

    fd_home = game.get("fanduel_home_odds")
    if fd_home:
        fd_away = game.get("fanduel_away_odds", -110)
        lines.append(f"🎯 *FanDuel:*  {home} `{_fmt_odds(fd_home)}`  /  {away} `{_fmt_odds(fd_away)}`")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "📊 *Sportsbook Lines*\n" + "\n".join(lines)},
    })

    # Model projections
    proj: List[str] = []
    proj.append(
        f"True Prob (devig):  {home} `{analysis['true_home_prob']:.1%}`  /  "
        f"{away} `{analysis['true_away_prob']:.1%}`"
    )
    proj.append(
        f"Model Blend:  {home} `{analysis['blended_home_prob']:.1%}`  /  "
        f"{away} `{analysis['blended_away_prob']:.1%}`"
    )
    proj.append(f"Projected Spread:  {home} `{_fmt_spread(spread)}`")
    proj.append(
        f"Edge:  {home} `{he * 100:+.1f}%`  /  {away} `{ae * 100:+.1f}%`"
    )
    if signals and sharp_side:
        proj.append(f"Sharp Side:  *{sharp_side}*  (confidence: `{sig_conf:.0%}`)")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "🤖 *Model Projections*\n" + "\n".join(proj)},
    })

    # Pick(s)
    home_key = game["game_id"] + "_HOME"
    away_key = game["game_id"] + "_AWAY"
    game_bets = []
    for key in (home_key, away_key):
        if key in bets_lookup:
            game_bets.append(bets_lookup[key])

    if game_bets:
        pick_lines: List[str] = []
        for b in game_bets:
            edge_pct = b.get("edge_pct", 0)
            if edge_pct >= 7:
                emoji = "🟢"
            elif edge_pct >= 5:
                emoji = "🟡"
            else:
                emoji = "🔵"

            pick_lines.append(
                f"{emoji}  *{b['side']}* `{b['decimal_odds']:.3f}`  [SPREAD]\n"
                f"      Edge: `{edge_pct:+.1f}%`  •  Kelly: `{b.get('portfolio_fraction_pct', 0):.2f}%`  •  Bet: `${b.get('bet_size_$', 0):.0f}`"
            )

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "✅ *PICK*\n" + "\n".join(pick_lines)},
        })
    else:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "⚪ _No qualifying edge — PASS_"}],
        })

    blocks.append({"type": "divider"})
    return blocks


def _format_ncaab_section(
    game_analyses: List[Dict[str, Any]],
    bets: List[Dict[str, Any]],
    data_source: str = "",
) -> List[Dict[str, Any]]:
    """Build all NCAAB Slack blocks."""
    if not game_analyses:
        return []

    blocks: List[Dict[str, Any]] = []

    source_tag = f"  •  _{data_source}_" if data_source else ""
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "🏀 NCAAB PICKS", "emoji": True},
    })
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"*{len(game_analyses)} games*  •  Devig + RLM + Bayesian + Half-Kelly{source_tag}",
        }],
    })
    blocks.append({"type": "divider"})

    # Build bet lookup by game_id
    bets_lookup: Dict[str, Dict[str, Any]] = {}
    for b in bets:
        bets_lookup[b.get("game_id", "")] = b

    for analysis in game_analyses:
        blocks.extend(_ncaab_game_blocks(analysis, bets_lookup))

    # Section footer
    total_wagered = sum(b.get("bet_size_$", 0) for b in bets)
    active = len([b for b in bets if b.get("bet_size_$", 0) > 0])
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"*{active} NCAAB bets*  •  Exposure: `${total_wagered:.0f}`",
        }],
    })

    return blocks


# ═══════════════════════════════════════════════════════════════════════
# NBA Section
# ═══════════════════════════════════════════════════════════════════════


def _implied_spread(home_win_prob: float) -> float:
    """ML probability → implied spread (~3% per point)."""
    return -((home_win_prob - 0.5) / 0.03)


def _format_nba_section(
    predictions: List[Dict[str, Any]],
    bets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build all NBA Slack blocks."""
    valid_preds = [p for p in predictions if "error" not in p]
    if not valid_preds:
        return []

    blocks: List[Dict[str, Any]] = []

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "🏀 NBA PICKS", "emoji": True},
    })
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"*{len(valid_preds)} games*  •  XGBoost ML + Kelly Optimization",
        }],
    })
    blocks.append({"type": "divider"})

    # Bet lookup by game_id
    bet_lookup: Dict[str, List[Dict[str, Any]]] = {}
    for b in bets:
        bet_lookup.setdefault(b.get("game_id", ""), []).append(b)

    for pred in valid_preds:
        home = pred["home_team"]
        away = pred["away_team"]
        ml = pred.get("moneyline_prediction", {})
        uo = pred.get("underover_prediction", {})
        ev = pred.get("expected_value", {})
        spread = pred.get("spread", {})
        total = pred.get("total", {})
        book = pred.get("book", "").title()
        confidence = pred.get("confidence", 0)

        home_prob = ml.get("home_win_prob", 0.5)
        away_prob = ml.get("away_win_prob", 0.5)
        conf_label = _confidence_label(confidence)

        # Game header
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{away}  @  {home}*\n{conf_label} Confidence"},
        })

        # Sportsbook lines
        book_label = f"_{book}_" if book else ""
        lines: List[str] = []

        home_ml = ev.get("home_odds", -110)
        away_ml = ev.get("away_odds", -110)
        lines.append(f"*ML:*  {away} `{_fmt_odds(away_ml)}`  /  {home} `{_fmt_odds(home_ml)}`")

        if spread:
            hp = spread.get("home_point", 0)
            ho = spread.get("home_odds", -110)
            ap = spread.get("away_point", 0)
            ao = spread.get("away_odds", -110)
            lines.append(
                f"*Spread:*  {away} `{_fmt_spread(ap)}` ({_fmt_odds(ao)})  /  "
                f"{home} `{_fmt_spread(hp)}` ({_fmt_odds(ho)})"
            )

        if total:
            tp = total.get("point", 0)
            to_over = total.get("over_odds", -110)
            to_under = total.get("under_odds", -110)
            lines.append(f"*Total:*  O/U `{tp}`  —  Over ({_fmt_odds(to_over)})  /  Under ({_fmt_odds(to_under)})")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"📊 *Sportsbook Lines* {book_label}\n" + "\n".join(lines)},
        })

        # Model projections
        proj: List[str] = []
        proj.append(f"ML Prob:  {home} `{home_prob:.1%}`  /  {away} `{away_prob:.1%}`")
        proj.append(f"Projected Spread:  {home} `{_implied_spread(home_prob):+.1f}`")

        if uo:
            proj_total = uo.get("total_points", 0)
            over_p = uo.get("over_prob", 0.5)
            rec = uo.get("recommendation", "over").upper()
            proj.append(f"Projected Total:  `{proj_total}`  ({rec} {over_p:.0%})")

        home_edge = ev.get("home_ev", 0)
        away_edge = ev.get("away_ev", 0)
        proj.append(f"Edge:  {home} `{home_edge * 100:+.1f}%`  /  {away} `{away_edge * 100:+.1f}%`")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "🤖 *Model Projections*\n" + "\n".join(proj)},
        })

        # Picks
        gid = f"NBA_{home}_{away}_{datetime.now().strftime('%Y%m%d')}".replace(" ", "")
        gid_total = f"NBA_TOTAL_{home}_{away}_{datetime.now().strftime('%Y%m%d')}".replace(" ", "")
        game_bets = bet_lookup.get(gid, []) + bet_lookup.get(gid_total, [])

        if game_bets:
            pick_lines: List[str] = []
            for b in game_bets:
                edge_pct = b.get("edge", 0) * 100
                emoji = "🟢" if edge_pct >= 7 else ("🟡" if edge_pct >= 5 else "🔵")
                pick_lines.append(
                    f"{emoji}  *{b['side']}* `{_fmt_odds(b['odds'])}`  [{b.get('market', 'ML').upper()}]\n"
                    f"      Edge: `{edge_pct:+.1f}%`  •  Bet: `${b.get('bet_size', 0):.0f}`"
                )
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "✅ *PICK*\n" + "\n".join(pick_lines)},
            })
        else:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "⚪ _No qualifying edge — PASS_"}],
            })

        blocks.append({"type": "divider"})

    # Section footer
    total_wagered = sum(b.get("bet_size", 0) for b in bets)
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"*{len(bets)} NBA bets*  •  Exposure: `${total_wagered:.0f}`",
        }],
    })

    return blocks


# ═══════════════════════════════════════════════════════════════════════
# Player Props Section
# ═══════════════════════════════════════════════════════════════════════

_STAT_DISPLAY = {
    "points": "PTS", "rebounds": "REB", "assists": "AST",
    "threes": "3PM", "blocks": "BLK", "steals": "STL",
    "pts+reb+ast": "PRA", "pts+reb": "P+R", "pts+ast": "P+A",
    "reb+ast": "R+A", "turnovers": "TO", "stl+blk": "S+B",
}

_PROP_TIER_MAP = {
    "strong_play": ("🟢 STRONG", 4),
    "good_play": ("🟡 GOOD", 3),
    "lean": ("🔵 LEAN", 2),
    "": ("⚪ MODEL", 1),
}


def _prop_tier(prop: Dict[str, Any]) -> tuple:
    ev_class = prop.get("ev_classification", "")
    label, rank = _PROP_TIER_MAP.get(ev_class, ("⚪ MODEL", 1))

    bayesian_edge = prop.get("bayesian_edge", 0)
    if bayesian_edge >= 0.08:
        label, rank = "🟢 HIGH", max(rank, 4)
    elif bayesian_edge >= 0.05:
        label, rank = "🟡 MEDIUM", max(rank, 3)
    elif bayesian_edge >= 0.03:
        label, rank = "🔵 LOW", max(rank, 2)

    return label, rank


def _filter_props(props: List[Dict[str, Any]], min_tier: str = "medium") -> List[Dict[str, Any]]:
    thresholds = {"low": 2, "medium": 3, "high": 4}
    min_rank = thresholds.get(min_tier, 3)
    filtered = [p for p in props if _prop_tier(p)[1] >= min_rank]
    filtered.sort(key=lambda x: x.get("bayesian_edge", 0), reverse=True)
    return filtered


def _format_props_section(
    best_props: List[Dict[str, Any]],
    min_tier: str = "medium",
) -> List[Dict[str, Any]]:
    """Build player prop Slack blocks, grouped by game."""
    filtered = _filter_props(best_props, min_tier)

    if not filtered:
        return [{
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "⚪ _No medium+ confidence player props on this slate._"}],
        }]

    blocks: List[Dict[str, Any]] = []

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "🎯 PLAYER PROPS", "emoji": True},
    })
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"*{len(filtered)} picks*  •  Medium–High confidence  •  Bayesian + Sharp Signals + EV Model",
        }],
    })
    blocks.append({"type": "divider"})

    # Group by game
    game_groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in filtered:
        home = p.get("home_team", "")
        away = p.get("away_team", "")
        key = f"{away} @ {home}" if home and away else "Unknown"
        game_groups.setdefault(key, []).append(p)

    for game_label, game_props in game_groups.items():
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{game_label}*"},
        })

        for p in game_props:
            player = p.get("player_name", "Unknown")
            stat_label = _STAT_DISPLAY.get(p.get("stat_type", ""), p.get("stat_type", "").upper())
            line = p.get("line", 0)
            best_side = p.get("best_side", "over").upper()
            proj_mean = p.get("projected_mean", 0)
            bayesian_edge = p.get("bayesian_edge", 0)
            kelly = p.get("kelly_fraction", 0)
            over_odds = p.get("over_odds", -110)
            under_odds = p.get("under_odds", -110)
            sharp_signals = p.get("sharp_signals", [])
            ev_class = p.get("ev_classification", "")
            best_book = p.get("best_over_book", "") if best_side == "OVER" else p.get("best_under_book", "")
            odds = over_odds if best_side == "OVER" else under_odds

            conf_label, _ = _prop_tier(p)
            signal_str = f"  ⚡ {', '.join(sharp_signals)}" if sharp_signals else ""
            ev_tag = f"  [{ev_class.replace('_', ' ').title()}]" if ev_class and ev_class != "pass" else ""
            book_str = ""
            if best_book:
                fd = "  🎯" if "fanduel" in best_book.lower() else ""
                book_str = f"\n      Best: _{best_book}_{fd}"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{conf_label}  *{player}* — {best_side} {line} {stat_label} "
                        f"`{_fmt_odds(int(odds))}`{signal_str}{ev_tag}\n"
                        f"      Proj: `{proj_mean:.1f}`  •  Edge: `{bayesian_edge * 100:+.1f}%`  •  "
                        f"Kelly: `{kelly:.2%}`{book_str}"
                    ),
                },
            })

        blocks.append({"type": "divider"})

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "Quarter-Kelly sizing  •  Line shop before placing  •  Track CLV"}],
    })

    return blocks


# ═══════════════════════════════════════════════════════════════════════
# Unified Report
# ═══════════════════════════════════════════════════════════════════════


def format_unified_slack_report(
    ncaab_data: Optional[Dict[str, Any]] = None,
    nba_predictions: Optional[List[Dict[str, Any]]] = None,
    nba_bets: Optional[List[Dict[str, Any]]] = None,
    prop_data: Optional[Dict[str, Any]] = None,
    min_prop_tier: str = "medium",
) -> List[Dict[str, Any]]:
    """Build a single unified Slack Block Kit message with all picks.

    Sections:
        1. Header with timestamp and slate summary
        2. NCAAB games (if any)
        3. NBA games (if any)
        4. Player props — medium+ confidence (if any)
        5. Footer
    """
    blocks: List[Dict[str, Any]] = []

    now_str = datetime.now().strftime("%a %b %d, %Y  •  %I:%M %p ET")

    ncaab_count = len((ncaab_data or {}).get("game_analyses", []))
    nba_count = len([p for p in (nba_predictions or []) if "error" not in p])
    prop_count = len((prop_data or {}).get("best_props", []))

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"📊 DAILY PICKS — {now_str}", "emoji": True},
    })

    slate_parts = []
    if ncaab_count:
        slate_parts.append(f"{ncaab_count} NCAAB")
    if nba_count:
        slate_parts.append(f"{nba_count} NBA")
    if prop_count:
        slate_parts.append(f"{prop_count} props scanned")

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"Slate: *{' + '.join(slate_parts or ['No games'])}*  •  All picks in one place",
        }],
    })
    blocks.append({"type": "divider"})

    # ── NCAAB ──
    if ncaab_data and ncaab_data.get("game_analyses"):
        blocks.extend(_format_ncaab_section(
            ncaab_data["game_analyses"],
            ncaab_data.get("bets", []),
            ncaab_data.get("data_source_label", ""),
        ))
        blocks.append({"type": "divider"})

    # ── NBA ──
    if nba_predictions:
        blocks.extend(_format_nba_section(nba_predictions, nba_bets or []))
        blocks.append({"type": "divider"})

    # ── Player Props ──
    if prop_data and prop_data.get("best_props"):
        blocks.extend(_format_props_section(prop_data["best_props"], min_prop_tier))

    # ── Global footer ──
    total_ncaab = sum(b.get("bet_size_$", 0) for b in (ncaab_data or {}).get("bets", []))
    total_nba = sum(b.get("bet_size", 0) for b in (nba_bets or []))
    total = total_ncaab + total_nba
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": (
                f"Total exposure: `${total:.0f}`  •  "
                f"Bets are LIVE  •  Dynamic sizing via Multivariate Kelly  •  "
                f"Track CLV on every bet. Line shop before placing."
            ),
        }],
    })

    return blocks
