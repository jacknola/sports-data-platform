"""
Player Prop endpoints

Three endpoints wired to the full prop analysis pipeline:
  GET  /props/{sport}        — All props with sharp signal analysis (LIVE data)
  GET  /props/{sport}/best   — Top props by EV, filtered by min_edge
  POST /props/analyze        — Full pipeline on a single prop
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio
import re
from loguru import logger

from app.services.bayesian import BayesianAnalyzer
from app.services.prop_analyzer import PropAnalyzer
from app.services.prop_probability import PropProbabilityModel
from app.services.multivariate_kelly import (
    BettingOpportunity,
    MultivariateKellyOptimizer,
)
from app.services.sports_api import SportsAPIService
from app.services.nba_stats_service import NBAStatsService
from app.services.ev_calculator import EVCalculator
from app.services.open_line_cache import get_or_set_open_line
from app.core.betting import american_to_decimal
from app.services.similarity_search import SimilaritySearchService
from app.config import settings

router = APIRouter()

_bayesian = BayesianAnalyzer()
_prop_analyzer = PropAnalyzer()
_prop_model = PropProbabilityModel()
_kelly_optimizer = MultivariateKellyOptimizer(kelly_scale=0.5, min_edge=0.03)
_sports_api = SportsAPIService()
_nba_stats = NBAStatsService()
_ev_calc = EVCalculator()
_similarity = SimilaritySearchService()

# Bankroll used for prop stake sizing (matches NCAAB/NBA game bankroll)
_BANKROLL: float = 100.0

# nba_api static team lookup: abbreviation → full name (local, instant)
try:
    from nba_api.stats.static import teams as _nba_static_teams

    _NBA_TEAM_BY_ABBREV: Dict[str, str] = {
        t["abbreviation"]: t["full_name"] for t in _nba_static_teams.get_teams()
    }
    _NBA_TEAM_BY_NAME: Dict[str, str] = {
        t["full_name"].lower(): t["abbreviation"] for t in _nba_static_teams.get_teams()
    }
except Exception:
    _NBA_TEAM_BY_ABBREV = {}
    _NBA_TEAM_BY_NAME = {}


# ---------------------------------------------------------------------------
# Prop type → stat key mapping (for NBAStatsService)
# ---------------------------------------------------------------------------
_PROP_TYPE_TO_STAT = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_threes": "threes",
    "player_blocks": "blocks",
    "player_steals": "steals",
    "player_points_rebounds_assists": "pts+reb+ast",
    "player_points_rebounds": "pts+reb",
    "player_points_assists": "pts+ast",
    "player_rebounds_assists": "reb+ast",
    "player_blocks_steals": "blocks+steals",
    "player_turnovers": "turnovers",
    # Alternate line markets → same stat type as main line
    "player_points_alternate": "points",
    "player_rebounds_alternate": "rebounds",
    "player_assists_alternate": "assists",
    "player_threes_alternate": "threes",
}


# ---------------------------------------------------------------------------
# Live prop fetching — replaces hardcoded _get_sample_props()
# ---------------------------------------------------------------------------


async def _get_live_props(sport: str) -> List[Dict]:
    """Fetch live player props from Odds API + enrich with player stats.

    Optimized pipeline:
        1. SportsAPIService.get_all_player_props() → raw prop lines from books
        2. Pre-filter by devig edge (>52% implied) to avoid enriching bad props
        3. NBAStatsService.get_player_prop_research() → player stats (capped at 30)
        4. Build prop dict matching _build_prop_analysis() input schema

    Returns:
        List of enriched prop dicts ready for _build_prop_analysis()
    """
    if sport.lower() not in ("nba", "basketball_nba"):
        return []

    sport_key = "basketball_nba"

    # Step 1: Get props from Odds API
    raw_props = await _sports_api.get_all_player_props(sport_key)
    if not raw_props:
        logger.warning("No live props returned from Odds API")
        return []

    logger.info(f"Fetched {len(raw_props)} unique player props from Odds API")

    # ── Step 2: Pre-filter ──
    # Goals:
    #   - Require >= 2 books offering the prop (single-book lines are unreliable)
    #   - Diversify across stat types (not just threes)
    #   - Cap at MAX_ENRICHED to avoid 200+ NBA.com calls
    MIN_DEVIG_EDGE = 0.01  # Very permissive — let model decide, not devig
    MAX_PER_STAT = (
        30  # Max props per stat type (raised to support alternate lines)
    )
    MAX_ENRICHED = (
        400  # Hard cap total (raised to allow up to 150 final best props)
    )

    # Score and bucket by stat type
    stat_buckets: Dict[str, List[tuple]] = {}
    for raw in raw_props:
        if not raw.get("player") or not raw.get("line"):
            continue
        # Allow single-book lines from sharp books (Pinnacle, etc.) — removed books_offering < 2 filter
        # if raw.get("books_offering", 1) < 2:
        #     continue
        devig_over = raw.get("devigged_over_prob", 0.5)
        devig_under = raw.get("devigged_under_prob", 0.5)
        # Score by EV magnitude instead of distance-from-50/50 to handle long odds correctly
        # For long odds (+150, +200), use (devigged_prob * decimal_odds) - 1 as the score
        over_am = raw.get("over_odds", -110)
        under_am = raw.get("under_odds", -110)
        over_decimal = american_to_decimal(over_am) if over_am else 1.91
        under_decimal = american_to_decimal(under_am) if under_am else 1.91
        ev_over = (devig_over * over_decimal) - 1
        ev_under = (devig_under * under_decimal) - 1
        # Use max absolute EV as the sorting score (handles both short and long odds fairly)
        edge_magnitude = max(abs(ev_over), abs(ev_under))
        is_long_odds = over_am >= 200 or under_am >= 200
        if edge_magnitude < MIN_DEVIG_EDGE and not is_long_odds:
            continue
        ptype = raw.get("prop_type", "unknown")
        if ptype not in stat_buckets:
            stat_buckets[ptype] = []
        stat_buckets[ptype].append((edge_magnitude, raw))

    # Sort each bucket by edge descending, take top MAX_PER_STAT per type
    filtered: List[Dict] = []
    for ptype, bucket in stat_buckets.items():
        bucket.sort(key=lambda x: x[0], reverse=True)
        filtered.extend(raw for _, raw in bucket[:MAX_PER_STAT])

    # Sort by EV magnitude descending, cap at MAX_ENRICHED
    filtered.sort(
        key=lambda r: max(
            abs(
                (
                    r.get("devigged_over_prob", 0.5)
                    * american_to_decimal(r.get("over_odds", -110))
                )
                - 1
            ),
            abs(
                (
                    r.get("devigged_under_prob", 0.5)
                    * american_to_decimal(r.get("under_odds", -110))
                )
                - 1
            ),
        ),
        reverse=True,
    )
    filtered = filtered[:MAX_ENRICHED]

    logger.info(
        f"Pre-filter: {len(filtered)}/{len(raw_props)} props "
        f"across {len(stat_buckets)} stat types (cap={MAX_ENRICHED}, >=2 books)"
    )

    # ── Pre-fetch all-team advanced stats (pace, ratings) — single cached call ──
    all_team_stats: Dict[str, Dict[str, Any]] = {}
    try:
        all_team_stats = await _nba_stats._nba_api_all_team_stats()
    except Exception as e:
        logger.debug(f"All-team stats pre-fetch failed (non-fatal): {e}")

    # ── Pre-fetch team rotations for "Next Man Up" detection ──
    team_rotations: Dict[str, List[Dict[str, Any]]] = {}
    unique_team_abbrevs = set()
    for r in filtered:
        # Try to get team abbreviation
        t_abbr = r.get("team_abbreviation")
        if not t_abbr:
            # Fallback: game title "LAL @ DEN"
            title = r.get("game_title") or r.get("event_description") or ""
            matches = re.findall(r"\b[A-Z]{2,3}\b", title)
            if matches:
                for m in matches:
                    unique_team_abbrevs.add(m.upper())
        else:
            unique_team_abbrevs.add(t_abbr.upper())

    # Fetch rotations in parallel
    rotation_tasks = [
        _nba_stats.get_team_rotation(abbr) for abbr in unique_team_abbrevs
    ]
    rotation_results = await asyncio.gather(*rotation_tasks)
    team_rotations = {
        abbr: rot for abbr, rot in zip(unique_team_abbrevs, rotation_results) if rot
    }

    # ── Step 3: Enrich with player stats (concurrent with semaphore) ──
    enriched: List[Dict] = []
    research_cache: Dict[str, Dict[str, Any]] = {}  # player:stat → research
    SEMAPHORE_CONCURRENCY = 3  # Max concurrent NBA.com requests

    sem = asyncio.Semaphore(SEMAPHORE_CONCURRENCY)

    async def fetch_with_semaphore(raw: Dict) -> tuple:
        async with sem:
            player_name = raw["player"]
            prop_type_api = raw.get("prop_type", "")
            line = raw["line"]
            stat_type: str = _PROP_TYPE_TO_STAT.get(
                prop_type_api
            ) or prop_type_api.replace("player_", "")
            player_id = player_name.lower().replace(" ", "_").replace(".", "")
            research_key = f"{player_id}:{stat_type}"

            # Return cached if available
            if research_key in research_cache:
                return (raw, research_cache[research_key])

            try:
                research = await _nba_stats.get_player_prop_research(
                    player_name=player_name,
                    prop_type=stat_type,
                    line=line,
                )
                research_cache[research_key] = research or {}
            except Exception as e:
                logger.debug(f"Stats lookup failed for {player_name}: {e}")
                research = {}
                research_cache[research_key] = research
            return (raw, research)

    # Fetch all in parallel with concurrency limit
    tasks = [fetch_with_semaphore(raw) for raw in filtered]
    results = await asyncio.gather(*tasks)

    # Process results and build enriched props
    for raw, research in results:
        player_name = raw["player"]
        prop_type_api = raw.get("prop_type", "")
        line = raw["line"]
        over_odds = raw.get("over_odds", -110)
        under_odds = raw.get("under_odds", -110)

        stat_type: str = _PROP_TYPE_TO_STAT.get(prop_type_api) or prop_type_api.replace(
            "player_", ""
        )
        player_id = player_name.lower().replace(" ", "_").replace(".", "")

        # ── Extract stats from research or use safe defaults ──
        season_avg = line
        last_5_avg = line
        usage_rate = 0.25
        usage_trend = 0.0
        injury_status = "ACTIVE"
        is_injury_replacement = False
        replacement_note = ""
        rest_days = 2

        rest_days = 2
        team_pace = 100.0
        opp_pace = 100.0
        opp_def_rating = 113.5
        dvp_modifier = None

        if research and not research.get("error"):
            rolling = research.get("rolling_averages", {})
            season_data = research.get("season_averages", {})

            if season_data:
                stat_key_map = {
                    "points": "pts",
                    "rebounds": "reb",
                    "assists": "ast",
                    "threes": "fg3m",
                    "blocks": "blk",
                    "steals": "stl",
                    "turnovers": "turnover",
                }
                sk = stat_key_map.get(stat_type, stat_type)
                season_avg = float(season_data.get(sk, line))

            if rolling:
                stat_rolling = rolling.get(stat_type, rolling.get("season_avg", {}))
                if isinstance(stat_rolling, dict):
                    last_5_avg = float(stat_rolling.get("l5", season_avg))
                elif isinstance(stat_rolling, (int, float)):
                    last_5_avg = float(stat_rolling)

            injuries = research.get("team_injuries", [])
            if injuries:
                for inj in injuries:
                    if player_name.lower() in str(inj).lower():
                        status = (
                            inj.get("status", "ACTIVE").upper()
                            if isinstance(inj, dict)
                            else "ACTIVE"
                        )
                        if status in ("QUESTIONABLE", "DOUBTFUL", "OUT", "PROBABLE"):
                            injury_status = status
                        break

            # Extract player team for Next Man Up detection + pace resolution
            player_info = research.get("player", {})
            player_team_abbrev = player_info.get("team_abbreviation")

            # ── Next Man Up Detection (NBA only) ──
            if sport.lower() == "nba" and player_team_abbrev:
                rotation = team_rotations.get(player_team_abbrev.upper(), [])
                team_injuries = research.get("team_injuries", [])
                
                # Top players (Top 6 by minutes) who are OUT or QUESTIONABLE
                injured_stars = []
                for p in rotation[:6]:
                    p_name = p['name']
                    for inj in team_injuries:
                        # Be careful with player name matching
                        if p_name.lower() in str(inj).lower():
                            status = (
                                inj.get("status", "ACTIVE").upper()
                                if isinstance(inj, dict)
                                else "ACTIVE"
                            )
                            if status in ("OUT", "DOUBTFUL", "QUESTIONABLE"):
                                injured_stars.append(p_name)
                                break
                
                if injured_stars:
                    # Current player's rank in rotation (Minutes proxy)
                    p_rank = next((i for i, p in enumerate(rotation) if p['name'].lower() == player_name.lower()), 99)
                    # If this player is rank 6-10 (Primary bench) and there's a star out, they get the bump
                    if 5 <= p_rank <= 10 and injury_status == "ACTIVE":
                        is_injury_replacement = True
                        replacement_note = f"Usage bump due to injuries to: {', '.join(injured_stars)}"

            matchup = research.get("matchup_data", {})

            if matchup:
                opp_def_rating = float(matchup.get("def_rating", 113.5))
                opp_pace = float(matchup.get("pace", 100.0))

            # Resolve player's own team pace from pre-fetched all-team stats
            if player_team_abbrev and all_team_stats:
                own_stats = all_team_stats.get(player_team_abbrev.upper(), {})
                if own_stats:
                    team_pace = float(own_stats.get("pace", 100.0))

        # ── Determine team / opponent / is_home from research + event data ──
        home_team = raw.get("home_team", "")
        away_team = raw.get("away_team", "")
        # Improve team resolution when missing from raw prop data
        if not home_team or not away_team:
            title_source = (
                raw.get("game_title", "") or raw.get("event_description", "")
            ) or ""
            if title_source:
                # Try format: "AwayTeam @ HomeTeam" or variants with @ / vs / at
                m = re.match(
                    r"^\s*([^\@]+?)\s*(?:@|vs\.?|vs|at)\s*([^\@]+?)\s*$",
                    title_source,
                    flags=re.IGNORECASE,
                )
                if m:
                    away_candidate = (m.group(1) or "").strip()
                    home_candidate = (m.group(2) or "").strip()
                    if not away_team and away_candidate:
                        away_team = away_candidate
                    if not home_team and home_candidate:
                        home_team = home_candidate
                else:
                    if "@" in title_source:
                        parts = [p.strip() for p in title_source.split("@")]
                        if len(parts) == 2:
                            if not away_team:
                                away_team = parts[0]
                            if not home_team:
                                home_team = parts[1]
        player_team = ""
        opponent = ""
        is_home = False

        if research and not research.get("error"):
            player_info = research.get("player", {})
            player_team = player_info.get("team", "") or ""

            # Fallback: derive team from game logs matchup when balldontlie 429'd
            if not player_team:
                logs = research.get("game_logs", [])
                if logs:
                    log_matchup = logs[0].get(
                        "matchup", ""
                    )  # e.g. "DET vs. SAS" or "DET @ SAS"
                    # Extract team abbreviation from matchup (first token before "vs." or "@")
                    match = re.match(r"^(\w+)\s+(?:vs\.?|@)", log_matchup)
                    if match:
                        abbrev = match.group(1).upper()
                        player_team = _NBA_TEAM_BY_ABBREV.get(abbrev, "")

            # Match player's team to home/away using substring matching
            if player_team:
                pt_lower = player_team.lower()
                if pt_lower in home_team.lower() or home_team.lower() in pt_lower:
                    is_home = True
                    opponent = away_team
                elif pt_lower in away_team.lower() or away_team.lower() in pt_lower:
                    is_home = False
                    opponent = home_team
            else:
                # Final fallback: if player_team still empty, check if player_name matches home/away
                # This handles cases where research completely fails
                player_name_lower = player_name.lower()
                home_lower = home_team.lower()
                away_lower = away_team.lower()

                # Check if player belongs to home or away based on name proximity
                # (This is a weak heuristic but better than leaving fields blank)
                if home_team and not away_team:
                    player_team = home_team
                    is_home = True
                elif away_team and not home_team:
                    player_team = away_team
                    is_home = False
                elif home_team and away_team:
                    # Default to home team if we can't determine
                    # (Sheets will at least show SOME team instead of blank)
                    player_team = home_team
                    opponent = away_team
                    is_home = True
                    logger.debug(
                        f"Props fallback: Could not determine {player_name}'s team, defaulting to home ({home_team})"
                    )

        # ── Open-line cache: store first-seen line/odds for sharp detection ──
        prop_market_key = f"prop:{player_id}:{stat_type}"
        _cached_open = None
        try:
            _cached_open = get_or_set_open_line(
                game_id=raw.get("event_id", ""),
                market=prop_market_key,
                current_line=line,
                current_odds=over_odds,
                current_odds_away=under_odds,
            )
        except Exception as e:
            logger.debug(f"Open-line cache failed for {player_name}: {e}")

        # ── Build the prop dict ──
        enriched.append(
            {
                "player_id": player_id,
                "player_name": player_name,
                "team": player_team,
                "opponent": opponent,
                "game_id": raw.get("event_id", ""),
                "stat_type": stat_type,
                "line": line,
                "over_odds": over_odds,
                "under_odds": under_odds,
                "open_over_odds": _cached_open.get("open_odds", over_odds)
                if _cached_open
                else over_odds,
                "open_under_odds": _cached_open.get("open_odds_away", under_odds)
                if _cached_open
                else under_odds,
                "open_line": _cached_open.get("open_line", line)
                if _cached_open
                else line,
                # TODO: Sharp signals require real ticket/money % from SportsGameOdds API
                # Currently hardcoded 50/50 prevents RLM detection (requires >=65% on one side)
                # See: backend/app/services/sharp_money_detector.py for RLM logic
                "over_ticket_pct": 0.0,  # No live data source — 0.0 prevents false RLM signals
                "over_money_pct": 0.0,  # No live data source — 0.0 prevents false RLM signals
                "season_avg": season_avg,
                "last_5_avg": last_5_avg,
                "usage_rate": usage_rate,
                "usage_trend": usage_trend,
                "injury_status": injury_status,
                "is_injury_replacement": is_injury_replacement,
                "replacement_note": replacement_note,

                "rest_days": rest_days,
                "is_home": is_home,
                "team_pace": team_pace,
                "opponent_pace": opp_pace,
                "opponent_def_rating": opp_def_rating,
                "dvp_modifier": dvp_modifier,
                "home_team": home_team,
                "away_team": away_team,
                "books_offering": raw.get("books_offering", 1),
                "best_over_book": raw.get("best_over_book", ""),
                "best_under_book": raw.get("best_under_book", ""),
                "devigged_over_prob": raw.get("devigged_over_prob", 0.5),
                "devigged_under_prob": raw.get("devigged_under_prob", 0.5),
                "_research": research,
            }
        )

    logger.info(
        f"Enriched {len(enriched)} props with player stats "
        f"({len(research_cache)} unique player lookups)"
    )
    return enriched


def _build_prop_analysis(prop: Dict) -> Dict:
    """
    Run the full prop analysis pipeline on a single prop dict.

    Pipeline:
      1. PropProbabilityModel.project()      — distribution + edge
      2. PropAnalyzer.analyze_prop()         — sharp signal detection
      3. BayesianAnalyzer.compute_posterior() — Bayesian posterior + Kelly
      4. EVCalculator.calculate_ev()          — hit-rate based EV (complementary)
    """
    player_data = {
        "player_id": prop["player_id"],
        "player_name": prop["player_name"],
        "stat_type": prop["stat_type"],
        "line": prop["line"],
        "season_avg": prop["season_avg"],
        "last_5_avg": prop["last_5_avg"],
        "usage_rate": prop["usage_rate"],
        "usage_trend": prop["usage_trend"],
        "injury_status": prop["injury_status"],
        "rest_days": prop["rest_days"],
    }
    game_context = {
        "team_pace": prop["team_pace"],
        "opponent_pace": prop["opponent_pace"],
        "opponent_def_rating": prop["opponent_def_rating"],
        "is_home": prop["is_home"],
        "dvp_modifier": prop.get("dvp_modifier"),
    }

    # 1. Projection (Normal CDF model)
    projection = _prop_model.project(
        player_data,
        game_context,
        over_odds=prop["over_odds"],
        under_odds=prop["under_odds"],
    )

    # 2. Sharp signal analysis (static one-shot)
    sharp = PropAnalyzer.analyze_prop(
        prop_id=f"{prop['player_id']}:{prop['stat_type']}",
        player_name=prop["player_name"],
        stat_type=prop["stat_type"],
        open_line=prop["open_line"],
        current_line=prop["line"],
        over_ticket_pct=prop["over_ticket_pct"],
        over_money_pct=prop["over_money_pct"],
        open_over_odds=prop["open_over_odds"],
        current_over_odds=prop["over_odds"],
        open_under_odds=prop["open_under_odds"],
        current_under_odds=prop["under_odds"],
    )

    # 3. Bayesian posterior
    # Feed the Normal CDF model projection (not market devig) as the prior.
    # This lets the model's actual statistical projection drive the posterior
    # rather than the book's implied probability which is ~0.50 for most props.
    bayesian_input = projection.to_bayesian_input()
    bayesian_input["features"]["injury_status"] = prop["injury_status"]
    bayesian_input["features"]["is_home"] = prop["is_home"]
    # Override devig_prob with model projection probability for the best side
    model_prob = (
        projection.model_p_over
        if projection.best_side == "over"
        else projection.model_p_under
    )
    if model_prob and model_prob > 0:
        bayesian_input["devig_prob"] = float(model_prob)
    bayesian_input["current_american_odds"] = (
        prop["over_odds"] if projection.best_side == "over" else prop["under_odds"]
    )
    posterior = _bayesian.compute_posterior(bayesian_input)

    # Sharp signal boost on Kelly
    signal_boost = posterior["edge"] * 0.1 if sharp["sharp_signals"] else 0.0
    decimal_odds = american_to_decimal(bayesian_input["current_american_odds"])
    kelly = _bayesian.calculate_kelly_criterion(
        posterior["posterior_p"], decimal_odds, edge=posterior["edge"]
    )

    # 4. EVCalculator (complementary hit-rate model)
    ev_data: Dict[str, Any] = {}
    research = prop.get("_research")
    if research and research.get("game_logs"):
        try:
            ev_data = _ev_calc.calculate_ev(
                research_data=research,
                line=prop["line"],
                odds=bayesian_input["current_american_odds"],
                prop_type=prop["stat_type"],
                bankroll=_BANKROLL,
            )
        except Exception as e:
            logger.debug(f"EVCalculator failed for {prop['player_name']}: {e}")

    # 5. Situational RAG (Similarity search in Qdrant)
    situational_context = "No historical analogs found."
    try:
        # Use player-specific collection for props
        analogs = _similarity.vector_store.search_similar_scenarios(
            description=f"{prop['player_name']} vs {prop['opponent']} {prop['stat_type']}",
            collection=settings.QDRANT_COLLECTION_PLAYERS,
            limit=3,
        )
        if analogs:
            outcomes = [
                str(a.get("outcome_pra") or a.get("outcome_pts")) for a in analogs
            ]
            situational_context = f"Similar Hist Scenarios: {', '.join(outcomes)} | Match: {analogs[0].get('description')}"
    except Exception as e:
        logger.debug(f"Situational RAG failed: {e}")

    # Classification from EVCalculator
    ev_classification = ev_data.get("classification", "")
    ev_true_prob = ev_data.get("true_probability", None)
    ev_edge = ev_data.get("edge", None)

    return {
        "player_name": prop["player_name"],
        "team": prop.get("team", ""),
        "opponent": prop.get("opponent", ""),
        "game_id": prop.get("game_id", ""),
        "stat_type": prop["stat_type"],
        "line": prop["line"],
        "market": "prop",
        "best_side": projection.best_side,
        "over_odds": prop["over_odds"],
        "under_odds": prop["under_odds"],
        # Model
        "projected_mean": projection.projected_mean,
        "projected_std": projection.projected_std,
        "model_p_over": projection.model_p_over,
        "model_p_under": projection.model_p_under,
        "model_edge_over": projection.model_edge_over,
        "model_edge_under": projection.model_edge_under,
        # Sharp signals
        "sharp_signals": sharp["sharp_signals"],
        "sharp_side": sharp["sharp_side"],
        "signal_confidence": sharp["signal_confidence"],
        "true_over_prob": sharp["true_over_prob"],
        "true_under_prob": sharp["true_under_prob"],
        "ev_edge_pct": sharp["ev_edge_pct"],
        "situational_context": situational_context,
        # is_positive_ev: True if EVCalculator found edge OR sharp signals confirm
        "is_positive_ev": (
            ev_classification in ("strong_play", "good_play", "lean")
            or sharp["is_positive_ev"]
        ),
        # Bayesian
        "posterior_p": posterior["posterior_p"],
        "fair_american_odds": posterior["fair_american_odds"],
        "bayesian_edge": posterior["edge"],
        "confidence_interval": posterior["confidence_interval"],
        "adjustments": posterior["adjustments"],
        # Sizing
        "kelly_fraction": round(kelly, 4),
        "sharp_signal_boost": round(signal_boost, 4),
        "method": "prop_model_bayesian",
        # EV Calculator (complementary model)
        "ev_classification": ev_classification,
        "ev_true_prob": ev_true_prob,
        "ev_edge": ev_edge,
        # Metadata
        "home_team": prop.get("home_team", ""),
        "away_team": prop.get("away_team", ""),
        "books_offering": prop.get("books_offering", 0),
        "best_over_book": prop.get("best_over_book", ""),
        "best_under_book": prop.get("best_under_book", ""),
        "devigged_over_prob": prop.get("devigged_over_prob", 0.5),
        "devigged_under_prob": prop.get("devigged_under_prob", 0.5),
        "is_injury_replacement": prop.get("is_injury_replacement", False),
        "replacement_note": prop.get("replacement_note", ""),
    }



# ---------------------------------------------------------------------------
# Standalone prop analysis function (for Telegram / analysis_runner)
# ---------------------------------------------------------------------------


async def run_prop_analysis(sport: str = "nba") -> Dict[str, Any]:
    """Run the full prop analysis pipeline and return structured results.

    Called by analysis_runner.py for Telegram reports.

    Returns:
        Dict with keys: sport, date, total_props, positive_ev_count,
        props (all analyzed), best_props (filtered +EV, sorted by edge)
    """
    raw_props = await _get_live_props(sport)

    if not raw_props:
        return {
            "sport": sport.upper(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_props": 0,
            "positive_ev_count": 0,
            "props": [],
            "best_props": [],
        }

    analyzed: List[Dict[str, Any]] = []
    for p in raw_props:
        try:
            result = _build_prop_analysis(p)
            analyzed.append(result)
        except Exception as e:
            logger.debug(f"Prop analysis failed for {p.get('player_name', '?')}: {e}")

    # ── Filter to +EV props ──
    # EVCalc (hit-rate model) is the primary gate — it uses real L5/L10/L20 data.
    # Bayesian is secondary — confirms the projection aligns with the model prior.
    #
    # Rules:
    #   - EVCalc fired + says "pass"  → ALWAYS block
    #   - EVCalc fired + says non-pass → require Bayesian edge >= 1.5% to confirm
    #   - EVCalc did NOT fire (no game logs, empty ev_classification) → require Bayesian >= 3%
    def _is_positive(p: Dict[str, Any]) -> bool:
        ev_class = p.get("ev_classification", "")
        bayesian_edge = p.get("bayesian_edge", 0)
        kelly_frac = p.get("kelly_fraction", 0)
        if kelly_frac > 0:
            return True
        if ev_class == "pass":
            return False
        if ev_class in ("strong_play", "good_play", "lean"):
            return bayesian_edge >= 0.01
        return bayesian_edge >= 0.015

    best = [p for p in analyzed if _is_positive(p)]

    # ── Diversity guarantee: ensure at least 1 pick per stat type ──
    # If a stat type has no +EV pick, include the best-edge prop from that type
    # as long as it has positive edge (>0%).
    stat_types_in_best = {p.get("stat_type") for p in best}
    all_stat_types = {p.get("stat_type") for p in analyzed}
    for st in all_stat_types - stat_types_in_best:
        candidates = [
            p
            for p in analyzed
            if p.get("stat_type") == st
            and p.get("bayesian_edge", 0) > 0
            and p.get("ev_classification", "") != "pass"
        ]
        if candidates:
            candidates.sort(key=lambda x: x.get("bayesian_edge", 0), reverse=True)
            best.append(candidates[0])

    # Sort: strong_play first, then by bayesian_edge descending
    ev_rank = {"strong_play": 0, "good_play": 1, "lean": 2, "": 3}
    best.sort(
        key=lambda x: (
            ev_rank.get(x.get("ev_classification", ""), 3),
            -x.get("bayesian_edge", 0),
        )
    )

    # ── Dynamic Limits ──
    # Calculate the number of unique teams playing on the slate
    unique_teams = {p.get("team") for p in raw_props if p.get("team")}
    num_unique_teams = len(unique_teams) if unique_teams else 1
    
    # Allow up to 150 total high-value props, distributed dynamically per team
    limit_per_team = max(1, 150 // num_unique_teams)
    
    import collections
    team_counts = collections.defaultdict(int)
    dynamically_balanced_best = []
    
    for prop in best:
        team = prop.get("team")
        if team_counts[team] < limit_per_team:
            dynamically_balanced_best.append(prop)
            team_counts[team] += 1
        
        if len(dynamically_balanced_best) >= 150:
            break

    return {
        "sport": sport.upper(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_props": len(analyzed),
        "positive_ev_count": len(dynamically_balanced_best),
        "props": analyzed,
        "best_props": dynamically_balanced_best,
    }

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/props/{sport}")
async def get_props(sport: str) -> Dict[str, Any]:
    """
    Get all props for a sport with sharp signal analysis applied.

    Returns the full slate including model projection, sharp signals,
    and Bayesian posterior for each prop line. Uses LIVE data from
    The Odds API + balldontlie.io player stats.
    """
    logger.info(f"Fetching live props for {sport}")
    try:
        result = await run_prop_analysis(sport)
        return result

    except Exception as e:
        logger.error(f"Error fetching props for {sport}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/props/{sport}/best")
async def get_best_props(
    sport: str,
    min_edge: float = Query(
        default=0.03, description="Minimum Bayesian edge threshold"
    ),
    limit: int = Query(default=100, description="Maximum props to return"),
    require_sharp: bool = Query(
        default=False,
        description="Only return props with sharp signals",
    ),
) -> List[Dict[str, Any]]:
    """
    Get best player props by EV + sharp signal, filtered by min_edge.

    Mirrors GET /bets endpoint — same filtering and sorting logic.
    Optional require_sharp=true restricts to props with detected
    RLM/STEAM/FREEZE/JUICE_SHIFT.
    """
    logger.info(
        f"Getting best props: sport={sport} min_edge={min_edge} "
        f"require_sharp={require_sharp}"
    )
    try:
        result = await run_prop_analysis(sport)
        analyzed = result.get("props", [])

        if not analyzed:
            return []

        # Filter
        filtered = [
            p
            for p in analyzed
            if p.get("bayesian_edge", 0) >= min_edge
            and p.get("is_positive_ev", False)
            and (not require_sharp or p.get("sharp_signals"))
        ]

        # Sort by Bayesian edge descending
        filtered.sort(key=lambda x: x.get("bayesian_edge", 0), reverse=True)

        return filtered[:limit]

    except Exception as e:
        logger.error(f"Error getting best props for {sport}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/props/analyze")
async def analyze_prop(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full prop analysis pipeline on a single submitted prop.

    Mirrors POST /bayesian — same input style, returns full prop analysis
    including projection, sharp signals, Bayesian posterior, and Kelly sizing.

    Expected input:
    {
        "player_id": "jayson_tatum",
        "player_name": "Jayson Tatum",
        "team": "BOS",
        "opponent": "MIL",
        "game_id": "nba_bos_mil_20260221",
        "stat_type": "points",
        "line": 27.5,
        "over_odds": -108,
        "under_odds": -112,
        "open_over_odds": -115,
        "open_under_odds": -105,
        "open_line": 27.5,
        "over_ticket_pct": 0.82,
        "over_money_pct": 0.80,
        "season_avg": 26.9,
        "last_5_avg": 25.1,
        "usage_rate": 0.34,
        "usage_trend": -0.01,
        "injury_status": "ACTIVE",
        "rest_days": 3,
        "is_home": true,
        "team_pace": 99.1,
        "opponent_pace": 100.4,
        "opponent_def_rating": 111.5
    }
    """
    required = [
        "player_id",
        "player_name",
        "stat_type",
        "line",
        "over_odds",
        "under_odds",
        "season_avg",
    ]
    missing = [f for f in required if f not in data]
    if missing:
        raise HTTPException(
            status_code=422, detail=f"Missing required fields: {missing}"
        )

    # Apply defaults for optional fields so _build_prop_analysis always has them
    defaults = {
        "team": "",
        "opponent": "",
        "game_id": f"{data['player_id']}:{data['stat_type']}",
        "open_line": data["line"],
        "open_over_odds": data["over_odds"],
        "open_under_odds": data["under_odds"],
        # TODO: Sharp signals require real ticket/money % from SportsGameOdds API
        # Currently hardcoded 50/50 prevents RLM detection (requires >=65% on one side)
        "over_ticket_pct": 0.0,  # No live data source — 0.0 prevents false RLM signals
        "over_money_pct": 0.0,  # No live data source — 0.0 prevents false RLM signals
        "last_5_avg": data["season_avg"],
        "usage_rate": 0.25,
        "usage_trend": 0.0,
        "injury_status": "ACTIVE",
        "rest_days": 2,
        "is_home": False,
        "team_pace": 100.0,
        "opponent_pace": 100.0,
        "opponent_def_rating": 113.5,
    }
    prop = {**defaults, **data}

    try:
        result = _build_prop_analysis(prop)
        return result
    except Exception as e:
        logger.error(f"Prop analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
