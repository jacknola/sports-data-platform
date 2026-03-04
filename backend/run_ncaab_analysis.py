"""
NCAAB Sharp Money Analysis — Tonight's Slate
Date: Auto-detected from live APIs

Applies the full quantitative sharp betting methodology to tonight's college basketball slate:
1. Devig Pinnacle/sharp book odds to derive true probabilities
2. Detect sharp money signals (RLM, steam, line freeze)
3. Calculate +EV against retail books
4. Apply Bayesian posterior adjustments
5. Run Multivariate Kelly portfolio optimization
6. Output ranked recommendations

Run:
    python backend/run_ncaab_analysis.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


import asyncio
import random
from app.services.sports_api import SportsAPIService, normalize_team_name

import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
import pandas as pd

# Import our services
from app.services.line_movement_analyzer import LineMovementAnalyzer
from app.services.multivariate_kelly import (
    MultivariateKellyOptimizer,
    BettingOpportunity,
    american_to_decimal,
    devig,
)
from app.services.bet_tracker import BetTracker
from app.services.open_line_cache import get_or_set_open_line
from app.services.ncaab_stats_service import NCAABStatsService
from app.services.similarity_search import find_similar_games

# ============================================================================
# TONIGHT'S NCAAB SLATE
# ============================================================================

TONIGHT_GAMES = []

BANKROLL = 100.0


# ============================================================================
# Helpers
# ============================================================================


def american_to_prob(american_odds: int) -> float:
    """Convert American odds to implied probability (no vig removal)."""
    if american_odds > 0:
        return 100.0 / (american_odds + 100.0)
    return abs(american_odds) / (abs(american_odds) + 100.0)


def compute_confidence(edge: float, signal_confidence: float, blended_prob: float) -> str:
    """Composite confidence: edge + signal strength + model certainty."""
    model_certainty = abs(blended_prob - 0.5) * 2  # 0 = coin flip, 1 = certain
    composite = (edge * 0.5) + (signal_confidence * 0.3) + (model_certainty * 0.2)
    if composite >= 0.12:
        return "HIGH"
    if composite >= 0.07:
        return "MEDIUM"
    if composite >= 0.03:
        return "LOW"
    return "SPECULATIVE"


# ============================================================================
# Analysis Engine
# ============================================================================


def estimate_public_splits(spread: float) -> Tuple[float, float]:
    """Estimate public ticket% and money% from spread magnitude.

    Empirical curve: bigger favorites attract more public action.
    Returns (home_ticket_pct, home_money_pct) where home is the team
    the spread belongs to.  If spread is negative (home is favored),
    public leans toward home; if positive, public leans away.

    Money% is set slightly below ticket% because the public tends
    to place many small bets (high ticket count, lower $ share).

    Args:
        spread: Home team spread (negative = home favored)

    Returns:
        Tuple of (home_ticket_pct, home_money_pct) in 0-1 range
    """
    abs_spread = abs(spread)

    # Base public lean toward the favorite (as ticket %)
    if abs_spread <= 1.5:
        fav_ticket_pct = 0.52
    elif abs_spread <= 3.5:
        fav_ticket_pct = 0.58
    elif abs_spread <= 5.5:
        fav_ticket_pct = 0.63
    elif abs_spread <= 7.5:
        fav_ticket_pct = 0.68
    elif abs_spread <= 10.0:
        fav_ticket_pct = 0.74
    elif abs_spread <= 14.0:
        fav_ticket_pct = 0.80
    else:
        fav_ticket_pct = 0.85

    # Add small jitter (±3%) to avoid deterministic outputs
    jitter = random.uniform(-0.03, 0.03)
    fav_ticket_pct = max(0.50, min(0.95, fav_ticket_pct + jitter))

    # Money% slightly lower than ticket% (public bets small on favorites)
    fav_money_pct = fav_ticket_pct - random.uniform(0.02, 0.08)
    fav_money_pct = max(0.35, min(0.92, fav_money_pct))

    # If spread < 0, home is favored → public on home
    # If spread > 0, away is favored → public on away (flip)
    if spread < 0:
        # Home is favorite
        return (fav_ticket_pct, fav_money_pct)
    elif spread > 0:
        # Away is favorite → invert for home perspective
        return (1.0 - fav_ticket_pct, 1.0 - fav_money_pct)
    else:
        # Pick'em
        return (0.50, 0.50)


def calculate_model_prob(home: str, away: str, spread: float, team_stats: Optional[Dict[str, Any]] = None) -> float:
    """Calculate model win probability using real team stats or spread fallback."""
    if not team_stats:
        return estimate_model_prob(spread)

    # Fuzzy lookup helper
    # Fuzzy lookup helper with common abbreviations and fuzzy matching
    def get_stats(team_name: str) -> Optional[Dict[str, Any]]:
        if not team_stats:
            return None
            
        # 1. Exact match
        if team_name in team_stats:
            return team_stats[team_name]
            
        # 2. Common abbreviations mapping
        abbreviations = {
            "UNC": "North Carolina",
            "UConn": "Connecticut",
            "UCONN": "Connecticut",
            "Pitt": "Pittsburgh",
            "Ole Miss": "Mississippi",
            "USC": "Southern California",
            "UCF": "Central Florida",
            "BYU": "Brigham Young",
            "VCU": "Virginia Commonwealth",
            "LSU": "LSU",
            "SMU": "Southern Methodist",
            "UNLV": "UNLV",
            "TCU": "TCU",
            "UMass": "Massachusetts",
            "Penn St": "Penn State",
            "NC State": "North Carolina State",
            "St. John's": "St. Johns",
        }
        
        # Check if team_name starts with or is an abbreviation
        for abbr, full in abbreviations.items():
            if team_name.lower() == abbr.lower() or team_name.lower().startswith(abbr.lower() + " "):
                if full in team_stats:
                    return team_stats[full]
        
        # 3. Substring matching (case-insensitive)
        t_lower = team_name.lower()
        for name, data in team_stats.items():
            n_lower = name.lower()
            if n_lower in t_lower or t_lower in n_lower:
                return data
                
        # 4. Handle "St." vs "State" and "St" vs "Saint"
        normalized_t = t_lower.replace("st.", "state").replace("st ", "state ").replace("saint ", "state ")
        for name, data in team_stats.items():
            normalized_n = name.lower().replace("st.", "state").replace("st ", "state ").replace("saint ", "state ")
            if normalized_n in normalized_t or normalized_t in normalized_n:
                return data
                
        return None

        if team_name in team_stats:
            return team_stats[team_name]
        for name, data in team_stats.items():
            if name.lower() in team_name.lower() or team_name.lower() in name.lower():
                return data
        return None

    h_stats = get_stats(home)
    a_stats = get_stats(away)

    if h_stats and a_stats:
        # League averages from NCAABStatsService
        league_avg = 106.0
        
        # Projected points per 100 possessions
        h_proj_ortg = (h_stats["AdjOE"] * a_stats["AdjDE"]) / league_avg
        a_proj_ortg = (a_stats["AdjOE"] * h_stats["AdjDE"]) / league_avg
        
        # Pythagorean win probability (exponent 11.5 for CBB)
        try:
            h_prob = (h_proj_ortg ** 11.5) / (h_proj_ortg ** 11.5 + a_proj_ortg ** 11.5)
            # Add home court advantage (~3 points or ~3-4% win prob)
            h_prob += 0.03 
            return min(0.95, max(0.05, h_prob))
        except (OverflowError, ZeroDivisionError):
            return estimate_model_prob(spread)
            
    return estimate_model_prob(spread)


def estimate_model_prob(spread: float) -> float:
    """Convert spread to an approximate win probability for the home team.

    Uses a logistic approximation: each point of spread ≈ 3% win probability.
    A -7 spread → ~71% implied home win probability.

    Args:
        spread: Home team spread (negative = home favored)

    Returns:
        Estimated home win probability (0.0 to 1.0)
    """
    # Logistic: P(home) = 1 / (1 + 10^(spread / 10))
    # This maps spread=-7 → ~0.67, spread=-3 → ~0.55, spread=0 → 0.50
    try:
        prob = 1.0 / (1.0 + 10.0 ** (spread / 10.0))
    except (OverflowError, ZeroDivisionError):
        prob = 0.50
    return max(0.05, min(0.95, prob))


# Global data source tag — set by get_live_ncaab_games(), read by run_analysis()
_ncaab_data_source: str = "unknown"


def _match_odds_to_espn_game(
    espn_game: Dict[str, Any],
    odds_data: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Match an ESPN game to its Odds API odds entry by team name.

    Returns the matching odds dict or None.
    """
    espn_home = normalize_team_name(espn_game.get("home_team", "")).lower()
    espn_away = normalize_team_name(espn_game.get("away_team", "")).lower()

    for odds_game in odds_data:
        odds_home = (odds_game.get("home_team") or "").lower()
        odds_away = (odds_game.get("away_team") or "").lower()

        # Check for substring match (ESPN: "Duke Blue Devils", Odds API: "Duke Blue Devils")
        if (espn_home in odds_home or odds_home in espn_home) and (
            espn_away in odds_away or odds_away in espn_away
        ):
            return odds_game

        # Also try partial match on last word (mascot)
        espn_home_parts = espn_home.split()
        odds_home_parts = odds_home.split()
        espn_away_parts = espn_away.split()
        odds_away_parts = odds_away.split()

        if (
            espn_home_parts
            and odds_home_parts
            and espn_away_parts
            and odds_away_parts
            and espn_home_parts[-1] == odds_home_parts[-1]
            and espn_away_parts[-1] == odds_away_parts[-1]
        ):
            return odds_game

    return None


def _parse_bookmaker_spreads(
    odds_game: Dict[str, Any],
    home_team: str,
) -> Dict[str, Any]:
    """Extract spread odds from a single Odds API game object.

    Returns dict with: pinnacle_home/away_odds, retail_home/away_odds,
    spread (canonical), open_spread.
    """
    pinnacle_home = -110
    pinnacle_away = -110
    retail_home = -110
    retail_away = -110
    spread = 0.0
    total = 0.0
    found_pinnacle = False
    found_fanduel = False

    sharp_books = {"pinnacle", "circa", "betonlineag", "lowvig"}
    retail_books = {"fanduel", "draftkings", "betmgm", "caesars", "pointsbet", "bovada"}

    for book in odds_game.get("bookmakers", []):
        book_key = book.get("key", "")
        for market in book.get("markets", []):
            if market.get("key") == "spreads":
                home_odds = -110
                away_odds = -110
                home_point = 0.0
                for out in market.get("outcomes", []):
                    name = out.get("name", "")
                    if name == home_team or name.lower() in home_team.lower():
                        home_odds = round(out.get("price", -110))
                        home_point = float(out.get("point", 0.0))
                    else:
                        away_odds = round(out.get("price", -110))

                if book_key in sharp_books:
                    if book_key == "pinnacle" or not found_pinnacle:
                        pinnacle_home = home_odds
                        pinnacle_away = away_odds
                        if book_key == "pinnacle":
                            found_pinnacle = True
                        spread = home_point  # sharp book spread is canonical
                elif book_key in retail_books:
                    if book_key == "fanduel" or not found_fanduel:
                        retail_home = home_odds
                        retail_away = away_odds
                        if book_key == "fanduel":
                            found_fanduel = True
                        if spread == 0.0:
                            spread = home_point
            elif market.get("key") == "totals":
                # Get the over/under line
                for out in market.get("outcomes", []):
                    if out.get("name") == "Over":
                        current_total = float(out.get("point", 0.0))
                        if total == 0.0 or book_key == "pinnacle" or book_key == "fanduel":
                            total = current_total

    return {
        "pinnacle_home_odds": pinnacle_home,
        "pinnacle_away_odds": pinnacle_away,
        "retail_home_odds": retail_home,
        "retail_away_odds": retail_away,
        "spread": spread,
        "total": total,
        "fanduel_home_odds": retail_home if found_fanduel else None,
        "fanduel_away_odds": retail_away if found_fanduel else None,
    }


async def get_live_ncaab_games(team_stats: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch today's NCAAB games using a multi-source waterfall.

    Waterfall:
        1. ESPN Scoreboard → game discovery (free, no API key)
        2. Odds API /events → secondary game discovery
        3. Odds API /odds  → odds enrichment for discovered games
        4. Cache fallback   → serve stale data with warning
        5. TONIGHT_GAMES   → absolute last resort with error log

    Returns:
        Tuple of (games_list, data_source_tag)
        data_source_tag is one of: "espn_live", "oddsapi_live", "cached",
        "stale_cache", "fallback"
    """
    global _ncaab_data_source
    api = SportsAPIService()

    # ── Step 1: Discover games (ESPN → Odds API /events) ──
    discovery = await api.discover_games("basketball_ncaab")
    espn_games = discovery.data
    source = discovery.source

    logger.info(f"Game discovery: {len(espn_games)} games via {source}")

    # ── Step 2: Fetch odds for enrichment ──
    odds_data = await api.get_odds("basketball_ncaab")

    if odds_data:
        logger.info(f"Odds enrichment: {len(odds_data)} games with odds data")

    # ── Step 3: Build game list ──
    live_games: List[Dict[str, Any]] = []

    if espn_games and source in ("espn_live", "cached", "stale_cache"):
        # ESPN-based path: match each ESPN game to Odds API data
        for espn_game in espn_games:
            home = espn_game.get("home_team", "")
            away = espn_game.get("away_team", "")

            if not home or not away:
                continue

            # Try to match with odds data
            matched_odds = (
                _match_odds_to_espn_game(espn_game, odds_data) if odds_data else None
            )

            if matched_odds:
                # We have odds → extract spread data
                spreads = _parse_bookmaker_spreads(
                    matched_odds, matched_odds.get("home_team", home)
                )
                spread_val = spreads["spread"]

                if spread_val == 0.0:
                    logger.debug(f"No spread market for {away} @ {home} — using moneyline-implied prob")
                    # Derive spread-equivalent from moneylines (pinnacle odds on spread market)
                    ml_home = spreads.get("pinnacle_home_odds")
                    ml_away = spreads.get("pinnacle_away_odds")
                    if ml_home and ml_away:
                        p_home = american_to_prob(ml_home)
                        p_away = american_to_prob(ml_away)
                        total_p = p_home + p_away
                        spread_val = round((0.5 - p_home / total_p) * 15.0, 1)  # ML-implied spread estimate
                    else:
                        spread_val = 0.0  # Still unknown but don't skip — fall through with 50/50

                game_id = f"NCAAB_{matched_odds.get('id', espn_game.get('espn_id', ''))}"
                # TODO: Wire up SportsGameOdds API when implemented
                public_data = None

                if public_data:
                    ticket_pct = public_data.get("home_ticket_pct", 0.50)
                    money_pct = public_data.get("home_money_pct", 0.50)
                    logger.info(f"Using REAL public splits for {game_id}: {ticket_pct:.0%}/{money_pct:.0%}")
                else:
                    ticket_pct, money_pct = estimate_public_splits(spread_val)
                    logger.debug(f"Using estimated public splits for {game_id}")

                # Extract efficiency stats for display
                h_stats = None
                a_stats = None
                if team_stats:
                    def get_stats(team_name):
                        if team_name in team_stats: return team_stats[team_name]
                        def _normalize(s):
                            t = (s or "").strip().lower()
                            t = t.replace(".", "").replace("st.", "state").replace(" saint ", " state ").replace(" st ", " state ").replace("  ", " ")
                            return t
                        abbreviations = {"UNC": "North Carolina", "UConn": "Connecticut", "UCONN": "Connecticut", "Pitt": "Pittsburgh", "Ole Miss": "Mississippi", "USC": "Southern California", "UCF": "Central Florida", "BYU": "Brigham Young", "VCU": "Virginia Commonwealth", "LSU": "LSU", "SMU": "Southern Methodist", "UNLV": "UNLV", "TCU": "TCU", "UMass": "Massachusetts", "Penn St": "Penn State", "NC State": "North Carolina State", "St. John's": "St. Johns"}
                        t_lower = _normalize(team_name)
                        for abbr, full in abbreviations.items():
                            abbr_l, full_l = abbr.lower(), full.lower()
                            if t_lower == abbr_l or t_lower == full_l or abbr_l in t_lower or full_l in t_lower:
                                if full in team_stats: return team_stats[full]
                                for name, data in team_stats.items():
                                    if _normalize(name) == full_l: return data
                        for name, data in team_stats.items():
                            if _normalize(name) in t_lower or t_lower in _normalize(name): return data
                        for name, data in team_stats.items():
                            if _normalize(name) in _normalize(team_name) or _normalize(team_name) in _normalize(name): return data
                        return None
                    h_stats = get_stats(matched_odds.get("home_team", home))
                    a_stats = get_stats(matched_odds.get("away_team", away))

                model_prob = calculate_model_prob(
                    matched_odds.get("home_team", home),
                    matched_odds.get("away_team", away),
                    spread_val,
                    team_stats
                )

                cached = get_or_set_open_line(
                    game_id, "spread", spread_val,
                    current_odds=spreads["pinnacle_home_odds"],
                    current_odds_away=spreads["pinnacle_away_odds"],
                )
                live_games.append(
                    {
                        "game_id": game_id,
                        "home": matched_odds.get("home_team", home),
                        "away": matched_odds.get("away_team", away),
                        "conference": espn_game.get("conference", "NCAAB"),
                        **spreads,
                        "open_spread": cached["open_line"],
                        "home_ticket_pct": round(ticket_pct, 3),
                        "home_money_pct": round(money_pct, 3),
                        "model_home_prob": round(model_prob, 3),
                        "total": spreads.get("total", 0.0),
                        "home_eff": h_stats,
                        "away_eff": a_stats,
                        "notes": f"Live ESPN + Odds API. Spread-implied public splits. Model prob from logistic.",
                    }
                )
            else:
                # ESPN game with no odds match — log but skip (no spread = no analysis)
                logger.debug(f"No odds match for ESPN game: {away} @ {home}")

    elif odds_data:
        # No ESPN data — fall back to Odds API only (same as before but better)
        source = "oddsapi_live"
        for g in odds_data:
            home = g.get("home_team", "")
            away = g.get("away_team", "")
            game_id = f"NCAAB_{g.get('id', '')}"

            spreads = _parse_bookmaker_spreads(g, home)
            spread_val = spreads["spread"]

            if spread_val == 0.0:
                logger.debug(f"No spread market for {away} @ {home} — using moneyline-implied prob")
                ml_home = spreads.get("pinnacle_home_odds")
                ml_away = spreads.get("pinnacle_away_odds")
                if ml_home and ml_away:
                    p_home = american_to_prob(ml_home)
                    p_away = american_to_prob(ml_away)
                    total_p = p_home + p_away
                    spread_val = round((0.5 - p_home / total_p) * 15.0, 1)  # ML-implied spread estimate
                else:
                    spread_val = 0.0  # Still unknown but don't skip — fall through with 50/50

            # TODO: Wire up SportsGameOdds API when implemented
            public_data = None

            if public_data:
                ticket_pct = public_data.get("home_ticket_pct", 0.50)
                money_pct = public_data.get("home_money_pct", 0.50)
                logger.info(f"Using REAL public splits for {game_id}: {ticket_pct:.0%}/{money_pct:.0%}")
            else:
                ticket_pct, money_pct = estimate_public_splits(spread_val)
                logger.debug(f"Using estimated public splits for {game_id}")

            # Extract efficiency stats for display
            h_stats = None
            a_stats = None
            if team_stats:
                def get_stats(team_name):
                    if team_name in team_stats: return team_stats[team_name]
                    def _normalize(s):
                        t = (s or "").strip().lower()
                        t = t.replace(".", "").replace("st.", "state").replace(" saint ", " state ").replace(" st ", " state ").replace("  ", " ")
                        return t
                    abbreviations = {"UNC": "North Carolina", "UConn": "Connecticut", "UCONN": "Connecticut", "Pitt": "Pittsburgh", "Ole Miss": "Mississippi", "USC": "Southern California", "UCF": "Central Florida", "BYU": "Brigham Young", "VCU": "Virginia Commonwealth", "LSU": "LSU", "SMU": "Southern Methodist", "UNLV": "UNLV", "TCU": "TCU", "UMass": "Massachusetts", "Penn St": "Penn State", "NC State": "North Carolina State", "St. John's": "St. Johns"}
                    t_lower = _normalize(team_name)
                    for abbr, full in abbreviations.items():
                        abbr_l, full_l = abbr.lower(), full.lower()
                        if t_lower == abbr_l or t_lower == full_l or abbr_l in t_lower or full_l in t_lower:
                            if full in team_stats: return team_stats[full]
                            for name, data in team_stats.items():
                                if _normalize(name) == full_l: return data
                    for name, data in team_stats.items():
                        if _normalize(name) in t_lower or t_lower in _normalize(name): return data
                    for name, data in team_stats.items():
                        if _normalize(name) in _normalize(team_name) or _normalize(team_name) in _normalize(name): return data
                    return None
                h_stats = get_stats(home)
                a_stats = get_stats(away)

            model_prob = calculate_model_prob(home, away, spread_val, team_stats)

            cached = get_or_set_open_line(
                game_id, "spread", spread_val,
                current_odds=spreads["pinnacle_home_odds"],
                current_odds_away=spreads["pinnacle_away_odds"],
            )
            live_games.append(
                {
                    "game_id": game_id,
                    "home": home,
                    "away": away,
                    "conference": "NCAAB",
                    **spreads,
                    "open_spread": cached["open_line"],
                    "home_ticket_pct": round(ticket_pct, 3),
                    "home_money_pct": round(money_pct, 3),
                    "model_home_prob": round(model_prob, 3),
                    "total": spreads.get("total", 0.0),
                    "home_eff": h_stats,
                    "away_eff": a_stats,
                    "notes": "Live Odds API only (ESPN unavailable). Spread-implied public splits.",
                }
            )

    # ── Step 4: Evaluate result ──
    if live_games:
        _ncaab_data_source = source
        logger.info(
            f"NCAAB pipeline: {len(live_games)} games ready for analysis [{source}]"
        )
        return (live_games, source)

    # ── Step 5: Last resort — return empty if no live data available
    # DO NOT return stale hardcoded data — it causes users to bet on old games
    today = datetime.now().strftime("%Y%m%d")
    hardcoded_date = "20260221"  # Date embedded in TONIGHT_GAMES game_ids

    logger.error(
        f"ALL LIVE SOURCES FAILED — no games available for {today}. "
        f"Hardcoded TONIGHT_GAMES (dated {hardcoded_date}) will NOT be used "
        f"as they are stale. Check API keys and network connectivity."
    )
    return ([], "no_games")


def run_analysis() -> Dict[str, Any]:
    """Run NCAAB sharp money analysis.

    Prints a full human-readable breakdown to stdout AND returns a structured
    result dict so the orchestrator / report formatter can consume it directly.

    Returns:
        {
            "sport": "ncaab",
            "game_count": int,
            "games": List[dict],           # raw game dicts from slate
            "scored_plays": List[dict],    # all qualifying plays, sorted by score
            "bets": List[dict],            # bets from portfolio optimizer
            "game_analyses": List[dict],   # per-game analysis data
        }
    """
    # Fetch real team stats
    stats_service = NCAABStatsService()
    team_stats = asyncio.run(stats_service.fetch_all_team_stats())

    games_to_analyze, data_source = asyncio.run(get_live_ncaab_games(team_stats))

    # Initialized here; populated after portfolio optimization
    bets: List[Dict[str, Any]] = []
    scored_plays: List[Dict[str, Any]] = []
    game_analyses: List[Dict[str, Any]] = []

    detector = LineMovementAnalyzer()
    optimizer = MultivariateKellyOptimizer(
        kelly_scale=0.5,  # Half-Kelly
        max_single_fraction=0.05,  # Max 5% per bet
        max_total_exposure=0.25,  # Max 25% total exposure
        min_edge=0.05,  # 5% minimum edge (raised from 2.5% to reduce noise)
    )

    # Phase 4: Data source tag in output
    source_labels = {
        "espn_live": "[LIVE - ESPN + Odds API]",
        "oddsapi_live": "[LIVE - Odds API]",
        "oddsapi_events": "[LIVE - Odds API Events]",
        "cached": "[CACHED]",
        "stale_cache": "[STALE CACHE]",
        "fallback": "[FALLBACK - STALE DATA]",
    }
    source_label = source_labels.get(data_source, f"[{data_source.upper()}]")

    print("\n" + "=" * 76)
    print(f"  NCAAB SHARP MONEY ANALYSIS — {datetime.now().strftime('%A, %B %d, %Y')}")
    print(f"  Data: {source_label} | {len(games_to_analyze)} games on slate")
    print(f"  Methodology: RLM + Devig + Bayesian + Multivariate Kelly (Half-Kelly)")
    print("=" * 76)

    opportunities = []

    for game in games_to_analyze:
        # --- Devig Pinnacle for true probabilities ---
        true_home_prob, true_away_prob = devig(
            game["pinnacle_home_odds"], game["pinnacle_away_odds"]
        )

        # --- Blend with model probability (80% market / 20% KenPom model) ---
        # Pinnacle is the sharpest book in the world — it dominates the signal.
        # Model adds marginal value only when it meaningfully diverges from the market.
        # Cap model at [0.30, 0.70] to prevent Pythagorean extremes from dominating.
        capped_model_prob = min(0.70, max(0.30, game["model_home_prob"]))
        blended_home_prob = 0.80 * true_home_prob + 0.20 * capped_model_prob
        blended_away_prob = 1.0 - blended_home_prob

        # --- Line Movement & Market Consensus Analysis ---
        sharp_analysis = LineMovementAnalyzer.analyze_game(
            game_id=game["game_id"],
            market="spread",
            home_team=game["home"],
            away_team=game["away"],
            open_line=game["open_spread"],
            current_line=game["spread"],
            pinnacle_home_odds=game["pinnacle_home_odds"],
            retail_home_odds=game["retail_home_odds"],
        )

        sharp_side = sharp_analysis["sharp_side"]
        signals = sharp_analysis["sharp_signals"]
        signal_confidence = sharp_analysis["signal_confidence"]

        # Line-movement and consensus signals raise confidence
        sharp_boost = 0.0
        if "LINE_MOVE" in signals:
            sharp_boost = signal_confidence * 0.5
        elif "CONSENSUS" in signals:
            sharp_boost = signal_confidence * 0.4

        # --- EV Calculation for both sides against retail ---
        retail_home_dec = american_to_decimal(game["retail_home_odds"])
        retail_away_dec = american_to_decimal(game["retail_away_odds"])

        retail_home_implied = 1.0 / retail_home_dec
        retail_away_implied = 1.0 / retail_away_dec

        home_edge = blended_home_prob - retail_home_implied
        away_edge = blended_away_prob - retail_away_implied

        # --- Build BettingOpportunity objects ---
        home_opp = BettingOpportunity(
            game_id=game["game_id"] + "_HOME",
            side=game["home"],
            market="spread",
            true_prob=blended_home_prob,
            decimal_odds=retail_home_dec,
            edge=home_edge,
            sport="ncaab",
            conference=game["conference"],
            home_team=game["home"],
            away_team=game["away"],
            sharp_signal_boost=sharp_boost if sharp_side == game["home"] else 0.0,
        )
        setattr(home_opp, "line", game["spread"])  # For settlement tracking

        away_opp = BettingOpportunity(
            game_id=game["game_id"] + "_AWAY",
            side=game["away"],
            market="spread",
            true_prob=blended_away_prob,
            decimal_odds=retail_away_dec,
            edge=away_edge,
            sport="ncaab",
            conference=game["conference"],
            home_team=game["home"],
            away_team=game["away"],
            sharp_signal_boost=sharp_boost if sharp_side == game["away"] else 0.0,
        )
        setattr(away_opp, "line", -game["spread"])  # For settlement tracking

        # Only add the better edge side (or both if both are positive)
        if home_edge > 0.05:
            opportunities.append(home_opp)
        if away_edge > 0.05:
            opportunities.append(away_opp)

        # Qdrant: find similar historical games for context
        best_edge = max(home_edge, away_edge)
        best_prob = blended_home_prob if home_edge >= away_edge else blended_away_prob
        confidence_level = compute_confidence(best_edge, signal_confidence, best_prob)
        try:
            similar = find_similar_games(game_data=game, limit=3)
            historical_context = [
                {"game": s.get("description", ""), "outcome": s.get("home_score", ""), "date": s.get("date", "")}
                for s in similar
            ]
            qdrant_retrieved = True
        except Exception as e:
            logger.debug(f"Qdrant similarity search failed for {game['game_id']}: {e}")
            historical_context = []
            qdrant_retrieved = False

        game_analyses.append(
            {
                "game": game,
                "true_home_prob": true_home_prob,
                "true_away_prob": true_away_prob,
                "blended_home_prob": blended_home_prob,
                "blended_away_prob": blended_away_prob,
                "home_edge": home_edge,
                "away_edge": away_edge,
                "sharp_signals": signals,
                "sharp_side": sharp_side,
                "signal_confidence": signal_confidence,
                "home_opp": home_opp,
                "away_opp": away_opp,
                "confidence_level": confidence_level,
                "historical_context": historical_context,
                "qdrant_retrieved": qdrant_retrieved,
            }
        )

    # --- Run Multivariate Kelly Portfolio Optimization ---
    portfolio = optimizer.optimize(opportunities, bankroll=BANKROLL)
    portfolio_summary = portfolio.summary()

    # Build lookup for fractions
    fraction_lookup = {}
    for opp, frac in zip(portfolio.opportunities, portfolio.optimal_fractions):
        fraction_lookup[opp.game_id] = (opp, frac)

    # ============================================================
    # OUTPUT
    # ============================================================

    print(
        f"\n  BANKROLL: ${BANKROLL:,.0f}  |  Kelly Scale: Half (50%)  |  Max Single: 5%"
    )
    print(
        f"  Games analyzed: {len(games_to_analyze)}  |  Opportunities meeting ≥2.5% edge: {len(opportunities)}"
    )
    print()

    # --- Game-by-game breakdown ---
    print("─" * 76)
    print("  GAME-BY-GAME BREAKDOWN")
    print("─" * 76)

    for analysis in game_analyses:
        game = analysis["game"]
        h = game["home"]
        a = game["away"]
        spread = game["spread"]
        fav = h if spread < 0 else a
        dog = a if spread < 0 else h
        spread_str = f"{fav} {spread:+.1f}" if spread < 0 else f"{fav} +{spread:.1f}"
        total_str = f"{game.get('total', 0.0):.1f}"

        print(f"\n  {a} @ {h} [SPREAD]")
        print(f"  [{game['conference']}] Spread: {spread_str} | O/U: {total_str}")
        print(
            f"  Open: {game['open_spread']:+.1f} → Current: {game['spread']:+.1f} "
            f"(move: {game['spread'] - game['open_spread']:+.1f})"
        )
        print(
            f"  Public: {game['home_ticket_pct']:.0%} tickets / "
            f"{game['home_money_pct']:.0%} money on {h}"
        )
        print(
            f"  Pinnacle: {h} {game['pinnacle_home_odds']:+d} / {a} {game['pinnacle_away_odds']:+d}"
        )
        fd_tag = "  🎯 FanDuel" if game.get("fanduel_home_odds") else ""
        print(
            f"  Retail:   {h} {game['retail_home_odds']:+d} / {a} {game['retail_away_odds']:+d}{fd_tag}"
        )
        print(
            f"  True prob (devig): {h} {analysis['true_home_prob']:.1%} / "
            f"{a} {analysis['true_away_prob']:.1%}"
        )
        print(
            f"  Model blend:       {h} {analysis['blended_home_prob']:.1%} / "
            f"{a} {analysis['blended_away_prob']:.1%}"
        )

        # Edge display
        he = analysis["home_edge"]
        ae = analysis["away_edge"]
        he_str = f"{he * 100:+.2f}%"
        ae_str = f"{ae * 100:+.2f}%"
        he_tag = " ← +EV" if he > 0.025 else (" ← EV" if he > 0 else "")
        ae_tag = " ← +EV" if ae > 0.025 else (" ← EV" if ae > 0 else "")
        print(f"  Edge vs retail:    {h} {he_str}{he_tag} / {a} {ae_str}{ae_tag}")

        # Sharp signals
        if analysis["sharp_signals"]:
            signal_str = ", ".join(analysis["sharp_signals"])
            sharp_side_display = analysis["sharp_side"] or "N/A"
            conf = analysis["signal_confidence"]
            print(
                f"  Sharp Signals: [{signal_str}] → Sharp $ on {sharp_side_display} "
                f"(confidence: {conf:.0%})"
            )
        else:
            print("  Sharp Signals: None detected")

        # Portfolio allocation
        home_key = game["game_id"] + "_HOME"
        away_key = game["game_id"] + "_AWAY"

        bets_found = []
        fd_home = game.get("fanduel_home_odds")
        fd_away = game.get("fanduel_away_odds")
        if home_key in fraction_lookup:
            opp, frac = fraction_lookup[home_key]
            if frac >= 0.001:
                size = frac * BANKROLL
                fd_note = f"  🎯 FanDuel ({fd_home:+d})" if fd_home else ""
                bets_found.append(
                    f"  ★ BET: {h} {game['retail_home_odds']:+d} "
                    f"→ ${size:.0f} ({frac * 100:.2f}% of bankroll){fd_note}"
                )
        if away_key in fraction_lookup:
            opp, frac = fraction_lookup[away_key]
            if frac >= 0.001:
                size = frac * BANKROLL
                fd_note = f"  🎯 FanDuel ({fd_away:+d})" if fd_away else ""
                bets_found.append(
                    f"  ★ BET: {a} {game['retail_away_odds']:+d} "
                    f"→ ${size:.0f} ({frac * 100:.2f}% of bankroll){fd_note}"
                )

        if bets_found:
            for b in bets_found:
                print(b)
        else:
            print("  → PASS (no qualifying edge after portfolio optimization)")

        print(f"  Note: {game['notes']}")

    # --- Portfolio Summary ---
    print("\n" + "=" * 76)
    print("  PORTFOLIO SUMMARY — MULTIVARIATE KELLY (HALF-KELLY)")
    print("=" * 76)

    bets = [b for b in portfolio_summary["bets"] if b["bet_size_$"] >= 0.01]

    if bets:
        # Sort by edge descending
        bets.sort(key=lambda x: x["edge_pct"], reverse=True)

        print(f"\n  {'Side':<35} {'Odds':>6} {'Edge':>7} {'Kelly%':>8} {'Bet $':>8}")
        print("  " + "-" * 68)

        for b in bets:
            side_label = b["side"][:34]
            print(
                f"  {side_label:<35} "
                f"{b['decimal_odds']:>6.3f} "
                f"{b['edge_pct']:>+6.2f}% "
                f"{b['portfolio_fraction_pct']:>7.2f}% "
                f"${b['bet_size_$']:>7.0f}"
            )

        total_exposure = portfolio_summary["total_bankroll_exposure_pct"]
        total_bet = sum(b["bet_size_$"] for b in bets)
        print("  " + "-" * 68)
        print(
            f"  {'TOTAL':<35} {'':>6} {'':>7} {total_exposure:>7.2f}% ${total_bet:>7.0f}"
        )

        print(
            f"\n  Expected log-growth rate: {portfolio_summary['expected_growth_rate']:+.5f}"
        )
        print(
            f"  Portfolio variance:       {portfolio_summary['portfolio_variance']:.6f}"
        )
        print(
            f"  Active bets: {len(bets)}  |  Total exposure: {total_exposure:.2f}% of bankroll"
        )
    else:
        print("\n  No bets meet all criteria after portfolio optimization.")
        print("  Consider lowering minimum edge threshold or adding more games.")

    # --- Save bets to tracker ---
    if bets:
        # First save games to PostgreSQL so bets can reference them
        try:
            from app.database import SessionLocal
            from app.models.game import Game
            from sqlalchemy import select
            
            db = SessionLocal()
            for game_analysis in game_analyses:
                game_data = game_analysis["game"]
                ext_id = game_data["game_id"]
                
                # Check if exists
                stmt = select(Game).where(Game.external_game_id == ext_id)
                existing = db.execute(stmt).scalars().first()
                
                if not existing:
                    new_game = Game(
                        external_game_id=ext_id,
                        sport="ncaab",
                        home_team=game_data["home"],
                        away_team=game_data["away"],
                        game_date=datetime.now(timezone.utc).replace(tzinfo=None) # Approximation
                    )
                    db.add(new_game)
            db.commit()
            db.close()
            logger.info("Games synced to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to sync games to PostgreSQL: {e}")

        tracker = BetTracker()
        for b in bets:
            # Find the original opportunity to get true_prob
            opp_id = b["game_id"]
            orig_opp = next((o for o in opportunities if o.game_id == opp_id), None)
            
            # We only track bets that actually have a bet size
            if float(b["bet_size_$"]) > 0:
                tracker.save_bet(
                    {
                        "game_id": b["game_id"].replace("_HOME", "").replace("_AWAY", ""),
                        "sport": "ncaab",
                        "side": b["side"],
                        "market": b["market"],
                        "odds": int(b["decimal_odds"] * 100)
                        if b["decimal_odds"] > 2.0
                        else int(
                            -100 / (b["decimal_odds"] - 1)
                        ),  # rough approximation just for tracking
                        "line": float(b.get("line", 0.0)),
                        "edge": float(b["edge_pct"]) / 100,
                        "bet_size": float(b["bet_size_$"]),
                        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "true_prob": orig_opp.true_prob if orig_opp else None
                    }
                )
        print(f"\n  Saved {len(bets)} pending bets to tracker.")

    # --- Top Plays Ranked ---
    print("\n" + "=" * 76)
    print("  TOP PLAYS — RANKED BY COMBINED SCORE (Edge × Signal Confidence)")
    print("=" * 76)

    for analysis in game_analyses:
        game = analysis["game"]
        for side, edge, opp_team in [
            (game["home"], analysis["home_edge"], game["away"]),
            (game["away"], analysis["away_edge"], game["home"]),
        ]:
            if edge < 0.025:
                continue

            is_sharp_side = analysis["sharp_side"] == side
            signal_conf = analysis["signal_confidence"] if is_sharp_side else 0.0
            score = edge * 100 + signal_conf * 5  # weighted composite

            side_idx = 0 if side == game["home"] else 1
            odds = (
                game["retail_home_odds"]
                if side == game["home"]
                else game["retail_away_odds"]
            )

            scored_plays.append(
                {
                    "rank": 0,
                    "matchup": f"{game['away']} @ {game['home']}",
                    "bet_on": side,
                    "market": "spread",
                    "odds": odds,
                    "edge": edge,
                    "signal_conf": signal_conf,
                    "signals": analysis["sharp_signals"],
                    "score": score,
                    "conference": game["conference"],
                }
            )

    scored_plays.sort(key=lambda x: x["score"], reverse=True)

    print()
    for i, play in enumerate(scored_plays[:8], 1):
        signals_str = (", ".join(play["signals"])) if play["signals"] else "Model only"
        print(f"  #{i}  {play['bet_on']} ({play['odds']:+d})")
        print(f"       Matchup: {play['matchup']}")
        print(
            f"       Edge: {play['edge'] * 100:+.2f}%  |  Signal: {signals_str}  |  "
            f"Composite score: {play['score']:.2f}"
        )
        print()

    # --- Risk Warnings ---
    print("─" * 76)
    print("  RISK FRAMEWORK")
    print("─" * 76)
    print("""
  • All edges are derived from Half-Kelly (50%). Adjust down to Quarter-Kelly
    in losing streaks or periods of high model uncertainty.

  • Track Closing Line Value (CLV) on every bet. Sustained positive CLV
    confirms model alpha. Negative CLV means revisit calibration.

  • Do NOT chase losses by increasing bet size. The Kelly system sizes for
    geometric bankroll growth; over-betting destroys long-run EV.

  • Retail sportsbook limits: If a book restricts you after consistent wins,
    migrate volume to Sporttrade, Prophet Exchange, or similar exchange.

  • Monte Carlo EMDD warning: At current exposure levels, a 10-15% bankroll
    drawdown is statistically normal even with +EV plays. Stay the course.

  • Sharp signals (RLM/FREEZE) confirm but do not replace model probability.
    Always require ≥2.5% edge before acting regardless of signal strength.
    """)

    print("=" * 76)
    print(f"  Analysis complete. {len(scored_plays)} qualifying plays identified.")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 76 + "\n")

    # Save detailed analysis with advanced metrics to a local CSV file', '    if game_analyses:', '        try:', '            df = pd.DataFrame(game_analyses)', '            # Flatten nested dicts for better CSV readability', '            for col in ["game", "home_eff", "away_eff", "home_opp", "away_opp"]:', '                if col in df.columns:', '                    df = pd.concat([df.drop([col], axis=1), df[col].apply(pd.Series).add_prefix(f"{col}_")], axis=1)', '            df.to_csv("sheets/ncaab_predictions.csv", index=False)', '            logger.info("NCAAB analysis with advanced metrics saved to sheets/ncaab_predictions.csv")', '        except Exception as e:', '            logger.error(f"Failed to save NCAAB analysis to CSV: {e}")', '
    return {
        "sport": "ncaab",
        "game_count": len(games_to_analyze),
        "games": games_to_analyze,
        "scored_plays": scored_plays,
        "bets": bets,
        "game_analyses": game_analyses,
        "data_source": data_source,
        "data_source_label": source_label,
    }


if __name__ == "__main__":
    run_analysis()
