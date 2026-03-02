"""
Parlay Suggestion Engine

Generates 2-4 leg parlay combinations from today's +EV picks.

Types generated:
  - SGP  (Same-Game Parlay): 2-3 legs from the same event_id
  - CROSS (Cross-Game):      2-4 highest-edge legs from different games

Scoring:
  composite = edge × combined_prob × leg_count_penalty
  (more legs → higher payout but lower probability → heavier penalty)
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional

from loguru import logger


# Correlation penalty for same-game parlays (legs within the same event are correlated)
_SGP_CORRELATION_PENALTY = 0.85  # reduce combined prob by 15% to account for correlation

# Leg count penalties — bigger parlays have much lower expected hit rate
_LEG_PENALTY = {2: 1.0, 3: 0.90, 4: 0.75}

_MIN_COMBINED_ODDS = 150   # American — parlay must pay at least +150
_MIN_EDGE = -0.01          # Allow near-break-even parlays to surface in output
_MAX_PARLAYS = 15          # Max suggestions returned


def _american_to_decimal(american: int) -> float:
    if american >= 100:
        return (american / 100) + 1
    return (100 / abs(american)) + 1


def _decimal_to_american(decimal: float) -> int:
    if decimal >= 2.0:
        return int((decimal - 1) * 100)
    return int(-100 / (decimal - 1))


def _combine_decimal_odds(odds_list: List[float]) -> float:
    result = 1.0
    for o in odds_list:
        result *= o
    return result


def _combine_probs(probs: List[float], sgp: bool = False) -> float:
    result = 1.0
    for p in probs:
        result *= p
    if sgp:
        result *= _SGP_CORRELATION_PENALTY
    return result


def _parlay_edge(combined_decimal: float, combined_true_prob: float) -> float:
    """EV = (true_prob × decimal_odds) - 1"""
    return (combined_true_prob * combined_decimal) - 1


def _build_leg(pick: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
    """Normalise a pick (prop / nba bet / ncaab bet) into a standard parlay leg dict."""
    edge = float(pick.get("bayesian_edge", pick.get("edge", 0)) or 0)
    true_prob = float(pick.get("posterior_p", pick.get("true_over_prob", 0.5)) or 0.5)

    best_side = (pick.get("best_side") or pick.get("side") or "over").upper()
    if best_side == "OVER":
        am_odds = int(pick.get("over_odds", -110) or -110)
        true_p = float(pick.get("true_over_prob", true_prob) or true_prob)
        fd_odds = pick.get("fanduel_over_odds")
    else:
        am_odds = int(pick.get("under_odds", -110) or -110)
        true_p = float(pick.get("true_under_prob", 1 - true_prob) or (1 - true_prob))
        fd_odds = pick.get("fanduel_under_odds")

    decimal = _american_to_decimal(am_odds)

    # Player prop
    player = pick.get("player_name") or pick.get("pick") or ""
    stat = pick.get("stat_type", "")
    line = pick.get("line", "")
    game = pick.get("game", "")
    if not game:
        h = pick.get("home_team", "")
        a = pick.get("away_team", "")
        game = f"{a} @ {h}" if h and a else ""

    return {
        "event_id": pick.get("event_id", pick.get("game_id", "")),
        "game": game,
        "player": player,
        "stat": stat,
        "line": line,
        "side": best_side,
        "odds_american": am_odds,
        "fanduel_odds": fd_odds,
        "decimal_odds": decimal,
        "true_prob": true_p,
        "edge": edge,
        "ev_class": pick.get("ev_classification", ""),
        "source": source,
    }


def generate_suggestions(
    props: List[Dict[str, Any]],
    ncaab_analyses: Optional[List[Dict[str, Any]]] = None,
    nba_predictions: Optional[List[Dict[str, Any]]] = None,
    nba_bets: Optional[List[Dict[str, Any]]] = None,
    top_n: int = _MAX_PARLAYS,
) -> List[Dict[str, Any]]:
    """Generate parlay suggestions from today's +EV picks.

    Args:
        props:           Full analyzed props list from run_prop_analysis()
        ncaab_analyses:  game_analyses from run_ncaab_analysis()
        nba_predictions: NBA predictions list
        nba_bets:        NBA qualifying bets

    Returns:
        List of parlay dicts sorted by composite score descending.
    """
    # ── Build leg pool ──
    legs: List[Dict[str, Any]] = []

    # Props: top +EV candidates
    prop_pool = [
        p for p in (props or [])
        if float(p.get("bayesian_edge", 0) or 0) > 0.02
        and p.get("ev_classification", "") not in ("pass", "")
    ]
    prop_pool.sort(key=lambda x: x.get("bayesian_edge", 0), reverse=True)
    for p in prop_pool[:40]:
        leg = _build_leg(p, "Props")
        if leg:
            legs.append(leg)

    # NCAAB: qualifying game bets
    for a in (ncaab_analyses or []):
        game_d = a.get("game", {})
        he = float(a.get("home_edge", 0) or 0)
        ae = float(a.get("away_edge", 0) or 0)
        sharp_side = a.get("sharp_side", "")
        edge = he if sharp_side.upper() == "HOME" or (not sharp_side and he > ae) else ae
        if edge < 0.03:
            continue
        home = game_d.get("home", "")
        away = game_d.get("away", "")
        pick_team = sharp_side or (home if he > ae else away)
        true_p = a.get("blended_home_prob", 0.5) if pick_team == home else (1 - a.get("blended_home_prob", 0.5))
        bet_odds = game_d.get("pinnacle_home_odds" if pick_team == home else "pinnacle_away_odds", -110) or -110
        legs.append({
            "event_id": game_d.get("game_id", f"ncaab_{home}_{away}"),
            "game": f"{away} @ {home}",
            "player": "",
            "stat": "Moneyline",
            "line": "",
            "side": "HOME" if pick_team == home else "AWAY",
            "odds_american": int(bet_odds),
            "fanduel_odds": None,
            "decimal_odds": _american_to_decimal(int(bet_odds)),
            "true_prob": float(true_p),
            "edge": edge,
            "ev_class": "strong_play" if edge >= 0.07 else ("good_play" if edge >= 0.05 else "lean"),
            "source": "NCAAB",
        })

    # NBA: qualifying bets
    for b in (nba_bets or []):
        edge = float(b.get("edge", 0) or 0)
        if edge < 0.03:
            continue
        am_odds = int(b.get("odds", -110) or -110)
        home = b.get("home_team", "")
        away = b.get("away_team", "")
        legs.append({
            "event_id": b.get("game_id", f"nba_{home}_{away}"),
            "game": f"{away} @ {home}",
            "player": "",
            "stat": b.get("market", "Moneyline").title(),
            "line": b.get("line", ""),
            "side": b.get("side", "").upper(),
            "odds_american": am_odds,
            "fanduel_odds": None,
            "decimal_odds": _american_to_decimal(am_odds),
            "true_prob": float(b.get("true_prob", 0.52)),
            "edge": edge,
            "ev_class": "strong_play" if edge >= 0.07 else ("good_play" if edge >= 0.05 else "lean"),
            "source": "NBA",
        })

    if len(legs) < 2:
        logger.info("Parlay engine: not enough qualifying legs to build suggestions")
        return []

    # ── Generate combinations ──
    suggestions: List[Dict[str, Any]] = []

    # Same-Game Parlays (SGP): 2-3 legs with same event_id
    event_map: Dict[str, List[Dict]] = {}
    for leg in legs:
        eid = leg["event_id"]
        if eid:
            event_map.setdefault(eid, []).append(leg)

    for eid, event_legs in event_map.items():
        if len(event_legs) < 2:
            continue
        # Try 2-leg and 3-leg SGPs
        for size in (2, 3):
            if len(event_legs) < size:
                continue
            for combo in itertools.combinations(event_legs[:6], size):
                sugg = _score_combo(list(combo), sgp=True, parlay_type="SGP")
                if sugg:
                    suggestions.append(sugg)

    # Cross-Game Parlays: 2-4 legs from different events
    # Use top 20 legs by edge, ensure different event_ids per combo
    top_legs = sorted(legs, key=lambda x: x["edge"], reverse=True)[:20]
    for size in (2, 3, 4):
        for combo in itertools.combinations(top_legs, size):
            # Ensure all from different events (or event_id is empty = different matches)
            event_ids = [l["event_id"] for l in combo if l["event_id"]]
            if len(event_ids) != len(set(event_ids)):
                continue  # duplicate event_id = same game
            sugg = _score_combo(list(combo), sgp=False, parlay_type="CROSS")
            if sugg:
                suggestions.append(sugg)
        if len(suggestions) > 200:  # avoid combinatorial explosion
            break

    # Sort by composite score and deduplicate by leg fingerprint
    suggestions.sort(key=lambda x: x["composite_score"], reverse=True)
    seen_fingerprints: set = set()
    unique_suggestions: List[Dict[str, Any]] = []
    for s in suggestions:
        fp = s["fingerprint"]
        if fp not in seen_fingerprints:
            seen_fingerprints.add(fp)
            unique_suggestions.append(s)
        if len(unique_suggestions) >= top_n:
            break

    logger.info(f"Parlay engine: generated {len(unique_suggestions)} suggestions from {len(legs)} legs")
    return unique_suggestions


def _score_combo(
    combo: List[Dict[str, Any]],
    sgp: bool,
    parlay_type: str,
) -> Optional[Dict[str, Any]]:
    """Score a leg combination and return a parlay suggestion dict, or None if below threshold."""
    n = len(combo)
    decimal_odds_list = [l["decimal_odds"] for l in combo]
    true_probs = [l["true_prob"] for l in combo]

    combined_decimal = _combine_decimal_odds(decimal_odds_list)
    combined_prob = _combine_probs(true_probs, sgp=sgp)
    combined_prob *= _LEG_PENALTY.get(n, 0.6)

    combined_am = _decimal_to_american(combined_decimal)
    edge = _parlay_edge(combined_decimal, combined_prob)

    # Filter: must pay at least +MIN_COMBINED_ODDS and meet edge threshold
    if combined_am < _MIN_COMBINED_ODDS or edge < _MIN_EDGE:
        return None

    # Composite score: edge × combined_prob × (1 + 0.1 per extra leg)
    composite = edge * combined_prob * (1 + 0.05 * (n - 2))

    ev_class = "strong_play" if edge >= 0.10 else ("good_play" if edge >= 0.05 else "lean")

    leg_descs = []
    for l in combo:
        desc = l["player"] if l["player"] else l["game"].split(" @ ")[0] if " @ " in l["game"] else l["game"]
        stat_part = f" {l['stat']}" if l["stat"] and l["stat"] != "Moneyline" else ""
        line_part = f" {l['line']}" if l["line"] != "" else ""
        side_part = f" {l['side']}"
        odds_part = f" ({l['odds_american']:+d})"
        leg_descs.append(f"{desc}{stat_part}{line_part}{side_part}{odds_part}")

    fingerprint = "|".join(sorted(
        f"{l['event_id']}:{l['player']}:{l['stat']}:{l['side']}:{l['line']}" for l in combo
    ))

    return {
        "type": parlay_type,
        "legs": combo,
        "leg_descriptions": leg_descs,
        "leg_count": n,
        "combined_odds_american": combined_am,
        "combined_odds_decimal": round(combined_decimal, 3),
        "combined_true_prob": round(combined_prob, 4),
        "edge_pct": round(edge * 100, 2),
        "ev_class": ev_class,
        "composite_score": round(composite, 5),
        "fingerprint": fingerprint,
    }
