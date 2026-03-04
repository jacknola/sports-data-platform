import asyncio
import io
import os
import sys
from contextlib import redirect_stdout
from typing import Any, Dict, List, Optional

from loguru import logger

# Ensure backend/ root is on sys.path so the top-level run_*.py scripts are
# importable regardless of the calling context (uvicorn, tests, routers, etc.).
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Dynamic pick-count scaling
# ---------------------------------------------------------------------------


def calculate_max_picks(game_count: int) -> int:
    """Determine the maximum number of picks to surface based on slate size.

    Rules:
        <=4  games  → up to 2 picks  (thin slate, very selective)
        5-8  games  → up to 4 picks
        9-12 games  → up to 6 picks
        13-16 games → up to 8 picks
        17+  games  → up to 10 picks

    The function never returns fewer than 1 (so a single strong play is always
    surfaced even on a 1-game slate).
    """
    if game_count <= 0:
        return 0
    if game_count <= 4:
        return 2
    if game_count <= 8:
        return 4
    if game_count <= 12:
        return 6
    if game_count <= 16:
        return 8
    return 10


# ---------------------------------------------------------------------------
# Legacy stdout-capture path (kept for backward compatibility)
# ---------------------------------------------------------------------------


def capture_analysis() -> str:
    """
    Run both NCAAB and NBA analysis and capture stdout.

    Returns:
        Raw text output from run_ncaab_analysis and run_nba_analysis
    """
    from run_nba_analysis import main as run_nba
    from run_ncaab_analysis import run_analysis as run_ncaab

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            run_ncaab()
            # Visual separator between NCAAB and NBA output (removed per AGENTS.md - no print() in services)
            run_nba()
        output = buf.getvalue()
        logger.info(f"Analysis captured: {len(output)} chars")
        return output
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return f"Analysis error: {e}"


# ---------------------------------------------------------------------------
# Orchestrated analysis (new path — structured data)
# ---------------------------------------------------------------------------


async def _run_orchestrator_for_sport(
    sport_key: str,
    teams: List[str],
    prediction_only: bool = False,
) -> Optional[Dict[str, Any]]:
    """Run the OrchestratorAgent pipeline for a single sport.

    Gracefully returns *None* if the orchestrator fails so the caller can
    fall back to the basic analysis path.
    """
    try:
        from app.agents.orchestrator import OrchestratorAgent

        orchestrator = await OrchestratorAgent.create()
        result = await orchestrator.execute_full_analysis(
            {
                "sport": sport_key,
                "teams": teams,
            },
            prediction_only=prediction_only,
        )
        logger.info(
            f"Orchestrator completed for {sport_key}: "
            f"{len(result.get('agents_used', []))} agents used"
        )
        return result
    except Exception as e:
        logger.warning(f"Orchestrator failed for {sport_key}, skipping enrichment: {e}")
        return None


def run_orchestrated_analysis(prediction_only: bool = False) -> Dict[str, Any]:
    """Run the full analysis pipeline with orchestrator enrichment.

    Flow:
        1. Run NCAAB analysis → structured picks + stdout capture
        2. Run NBA analysis   → structured picks + stdout capture
        3. Run OrchestratorAgent per sport for sentiment / scraping / expert
        4. Merge orchestrator context into the pick data
        5. Apply dynamic pick-count limits based on total slate size

    Returns a dict consumed by ``ReportFormatter.format_live_report()``:
        {
            "raw_output": str,            # legacy stdout for fallback rendering
            "ncaab": Dict | None,         # structured NCAAB result
            "nba": Dict | None,           # structured NBA result
            "orchestrator_ncaab": Dict | None,
            "orchestrator_nba": Dict | None,
            "total_game_count": int,
            "max_picks": int,
            "picks": List[dict],          # final merged & trimmed pick list
        }
    """
    from run_nba_analysis import run_nba_analysis
    from run_ncaab_analysis import run_analysis as run_ncaab

    # ------------------------------------------------------------------
    # 1. Run the core analysis scripts (capture stdout + structured data)
    # ------------------------------------------------------------------
    ncaab_data: Optional[Dict[str, Any]] = None
    nba_data: Optional[Dict[str, Any]] = None
    buf = io.StringIO()

    try:
        with redirect_stdout(buf):
            ncaab_data = run_ncaab(prediction_only=prediction_only)
            # Visual separator between NCAAB and NBA output (removed per AGENTS.md - no print() in services)
            nba_data = asyncio.run(run_nba_analysis(prediction_only=prediction_only))
    except Exception as e:
        logger.error(f"Core analysis failed: {e}")

    raw_output = buf.getvalue()

    # ------------------------------------------------------------------
    # 2. Determine slate size & dynamic pick count
    # ------------------------------------------------------------------
    ncaab_game_count = (ncaab_data or {}).get("game_count", 0)
    nba_game_count = (nba_data or {}).get("game_count", 0)
    total_game_count = ncaab_game_count + nba_game_count
    max_picks = calculate_max_picks(total_game_count)

    logger.info(
        f"Slate: {ncaab_game_count} NCAAB + {nba_game_count} NBA = "
        f"{total_game_count} total → max {max_picks} picks"
    )

    # ------------------------------------------------------------------
    # 3. Extract teams for orchestrator enrichment
    # ------------------------------------------------------------------
    ncaab_teams: List[str] = []
    nba_teams: List[str] = []

    if ncaab_data:
        for g in ncaab_data.get("games", []):
            ncaab_teams.extend([g.get("home", ""), g.get("away", "")])
    if nba_data:
        for p in nba_data.get("predictions", []):
            nba_teams.extend([p.get("home_team", ""), p.get("away_team", "")])

    ncaab_teams = [t for t in ncaab_teams if t]
    nba_teams = [t for t in nba_teams if t]

    # ------------------------------------------------------------------
    # 4. Run orchestrator enrichment (sentiment, scraping, expert)
    # ------------------------------------------------------------------
    orch_ncaab: Optional[Dict[str, Any]] = None
    orch_nba: Optional[Dict[str, Any]] = None

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if ncaab_teams:
                orch_ncaab = loop.run_until_complete(
                    _run_orchestrator_for_sport(
                        "basketball_ncaab",
                        ncaab_teams[:10],

                    )
                )
            if nba_teams:
                orch_nba = loop.run_until_complete(
                    _run_orchestrator_for_sport(
                        "basketball_nba",
                        nba_teams[:10],

                    )
                )
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Orchestrator enrichment failed: {e}")

    # ------------------------------------------------------------------
    # 5. Merge all picks into a single ranked list, apply dynamic limit
    # ------------------------------------------------------------------
    all_picks: List[Dict[str, Any]] = []

    # NCAAB scored plays
    if ncaab_data and ncaab_data.get("scored_plays"):
        for play in ncaab_data.get("scored_plays", []):
            play["sport"] = "ncaab"
            # Attach orchestrator sentiment if available
            if orch_ncaab:
                _enrich_pick_with_orchestrator(play, orch_ncaab)
            all_picks.append(play)

    if ncaab_data and not ncaab_data.get("scored_plays"):
        for pred in ncaab_data.get("predictions", [])[:20]:
            all_picks.append(
                {
                    "sport": "ncaab",
                    "bet_on": pred.get("winner"),
                    "matchup": f"{pred.get('away', '')} @ {pred.get('home', '')}",
                    "score": pred.get("confidence", 0) * 100,
                    "edge": pred.get("confidence", 0),
                    "mode": "prediction_only",
                }
            )

    # NBA bets
    if nba_data and nba_data.get("bets"):
        for bet in nba_data.get("bets", []):
            bet["sport"] = "nba"
            if orch_nba:
                _enrich_pick_with_orchestrator(bet, orch_nba)
            all_picks.append(bet)

    if nba_data and not nba_data.get("bets"):
        for pred in nba_data.get("predictions", [])[:20]:
            best_team = (
                pred.get("home_team")
                if pred.get("home_win_prob", 0.5) >= 0.5
                else pred.get("away_team")
            )
            confidence = abs(pred.get("home_win_prob", 0.5) - 0.5) * 2
            all_picks.append(
                {
                    "sport": "nba",
                    "bet_on": best_team,
                    "matchup": f"{pred.get('away_team', '')} @ {pred.get('home_team', '')}",
                    "score": confidence * 100,
                    "edge": confidence,
                    "mode": "prediction_only",
                }
            )

    # Sort by score (NCAAB) or edge (NBA) — unified ranking
    all_picks.sort(
        key=lambda p: p.get("score", 0) or (p.get("edge", 0) * 100),
        reverse=True,
    )

    # Apply dynamic pick-count limit
    final_picks = all_picks[:max_picks]

    logger.info(
        f"Orchestrated analysis complete: {len(all_picks)} total plays → "
        f"{len(final_picks)} surfaced (max_picks={max_picks})"
    )

    # ------------------------------------------------------------------
    # 6. Collect data source + quota metadata (Phase 4)
    # ------------------------------------------------------------------
    data_source = "unknown"
    api_quota_remaining = None

    if ncaab_data:
        data_source = ncaab_data.get("data_source", "unknown")
    # If NCAAB source is fallback but NBA had live data, prefer live label
    if data_source in ("fallback", "unknown") and nba_data:
        nba_src = nba_data.get("data_source", "")
        if nba_src and nba_src not in ("fallback", "unknown"):
            data_source = nba_src

    # Try to get quota from the SportsAPIService (if it ran)
    try:
        from app.services.sports_api import SportsAPIService

        svc = SportsAPIService()
        api_quota_remaining = svc.quota_remaining
    except Exception:
        pass

    return {
        "raw_output": raw_output,
        "ncaab": ncaab_data,
        "nba": nba_data,
        "orchestrator_ncaab": orch_ncaab,
        "orchestrator_nba": orch_nba,
        "total_game_count": total_game_count,
        "max_picks": max_picks,
        "picks": final_picks,
        "data_source": data_source,
        "api_quota_remaining": api_quota_remaining,
    }


def _enrich_pick_with_orchestrator(
    pick: Dict[str, Any],
    orch_result: Dict[str, Any],
) -> None:
    """Attach orchestrator context (sentiment, expert) to a pick in-place."""
    # Sentiment: find matching team
    team_name = pick.get("bet_on", pick.get("team", "")).lower()
    for sent in orch_result.get("sentiment", []):
        target = sent.get("target", "").lower()
        if target and target in team_name or team_name in target:
            pick["sentiment"] = sent.get("sentiment", {})
            break

    # Expert recommendation (applies to top value bet only — attach if present)
    expert = orch_result.get("expert_recommendation", {})
    if expert and not pick.get("expert"):
        pick["expert"] = expert.get("decision", {})

    # Scraped news context
    for scraped in orch_result.get("scraped_data", []):
        if team_name in str(scraped.get("data", "")).lower():
            pick["news_context"] = scraped.get("data")
            break


# ---------------------------------------------------------------------------
# DvP analysis pipeline (separate Telegram message)
# ---------------------------------------------------------------------------


def run_dvp_analysis_pipeline() -> Optional[Dict[str, Any]]:
    """Run the DvP +EV analysis pipeline for NBA.

    Called AFTER run_prop_analysis_pipeline() and produces a SEPARATE
    Telegram message for DvP-based prop targets.

    Returns:
        Dict from DvPAgent.execute() or None on failure.
    """
    try:
        from app.agents.dvp_agent import DvPAgent

        agent = DvPAgent()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(agent.execute({"type": "full_analysis"}))
        finally:
            loop.close()

        if "error" in result:
            logger.warning(f"DvP pipeline returned error: {result['error']}")
            return None

        count = result.get("count", 0)
        hv = result.get("high_value_count", 0)
        logger.info(f"DvP pipeline complete: {count} projections, {hv} HIGH VALUE")
        return result

    except Exception as e:
        logger.error(f"DvP analysis pipeline failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Player prop analysis pipeline (separate Telegram message)
# ---------------------------------------------------------------------------


def run_prop_analysis_pipeline(sport: str = "nba") -> Optional[Dict[str, Any]]:
    """Run the player prop analysis pipeline.

    This is designed to be called AFTER run_orchestrated_analysis()
    and produces a SEPARATE Telegram message for player props.

    Flow:
        1. Import and call run_prop_analysis() from the props router
        2. Return structured data for ReportFormatter.format_prop_report()

    Returns:
        Dict with keys: sport, date, total_props, positive_ev_count,
        props, best_props. Returns None if the prop pipeline fails.
    """
    try:
        from app.routers.props import run_prop_analysis

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_prop_analysis(sport))
        finally:
            loop.close()

        total = result.get("total_props", 0)
        ev_count = result.get("positive_ev_count", 0)

        logger.info(
            f"Prop pipeline complete: {total} props scanned, "
            f"{ev_count} +EV opportunities"
        )

        return result

    except Exception as e:
        logger.error(f"Prop analysis pipeline failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Google Sheets export pipeline
# ---------------------------------------------------------------------------


def run_sheets_export_pipeline(
    ncaab_data: Optional[Dict[str, Any]] = None,
    nba_data: Optional[Dict[str, Any]] = None,
    prop_data: Optional[Dict[str, Any]] = None,
    spreadsheet_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Export all daily picks to Google Sheets.

    Called after Telegram sends complete.  Collects NCAAB, NBA, and
    prop data produced by the other pipeline stages and writes them
    to the configured Google Spreadsheet (Props / NBA / NCAAB / Summary tabs).

    Args:
        ncaab_data: Result from run_ncaab_analysis() (contains game_analyses + bets)
        nba_data: Result from run_nba_analysis() (contains predictions + bets)
        prop_data: Result from run_prop_analysis() (contains props + best_props)
        spreadsheet_id: Override sheet ID (defaults to GOOGLE_SPREADSHEET_ID)

    Returns:
        Dict with per-tab results, or None on failure.
    """
    try:
        from app.config import settings
        from app.services.google_sheets import GoogleSheetsService

        sid = spreadsheet_id or getattr(settings, "GOOGLE_SPREADSHEET_ID", None)
        if not sid:
            logger.warning("Google Sheets export skipped: no GOOGLE_SPREADSHEET_ID")
            return None

        sheets = GoogleSheetsService()
        if not sheets.is_configured:
            logger.warning("Google Sheets export skipped: service not configured")
            return None

        # Extract NBA predictions + bets from nba_data
        nba_predictions = (nba_data or {}).get("predictions", [])
        nba_bets = (nba_data or {}).get("bets", [])

        # Generate parlay suggestions from today's props + NBA/NCAAB bets
        # (lazy import — consistent with other service imports in this function
        #  to avoid circular dependency at module load time)
        parlay_suggestions: List[Dict[str, Any]] = []
        try:
            from app.services.parlay_engine import generate_suggestions as _gen_parlays

            parlay_suggestions = _gen_parlays(
                props=(prop_data or {}).get("best_props", []),
                ncaab_analyses=(ncaab_data or {}).get("game_analyses", []),
                nba_bets=nba_bets,
            )
            logger.info(f"Parlay engine: {len(parlay_suggestions)} suggestions generated")
        except Exception as _parlay_err:
            logger.warning(f"Parlay engine failed (non-fatal): {_parlay_err}")

        result = sheets.export_daily_picks(
            spreadsheet_id=sid,
            ncaab_data=ncaab_data,
            nba_predictions=nba_predictions,
            nba_bets=nba_bets,
            prop_data=prop_data,
            parlay_suggestions=parlay_suggestions,
        )

        tabs_ok = sum(
            1
            for r in result.values()
            if isinstance(r, dict) and r.get("status") == "success"
        )
        logger.info(f"Google Sheets export: {tabs_ok}/{len(result)} tabs written")

        qdrant_games = sum(
            1
            for ga in (ncaab_data or {}).get("game_analyses", [])
            if ga.get("qdrant_retrieved")
        )
        logger.info(
            f"Sheets export complete — {qdrant_games} games enriched with Qdrant context"
        )
        return result

    except Exception as e:
        logger.error(f"Google Sheets export pipeline failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Slack report pipeline
# ---------------------------------------------------------------------------


def run_slack_report_pipeline(
    ncaab_data: Optional[Dict[str, Any]] = None,
    nba_data: Optional[Dict[str, Any]] = None,
    prop_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """Format and send unified picks report to Slack.

    Args:
        ncaab_data: Result from run_ncaab_analysis()
        nba_data: Result from run_nba_analysis() (contains predictions + bets)
        prop_data: Result from run_prop_analysis()

    Returns:
        True if sent successfully.
    """
    try:
        from app.services.slack_formatter import format_unified_slack_report
        from app.services.slack_service import SlackService

        nba_predictions = (nba_data or {}).get("predictions", [])
        nba_bets = (nba_data or {}).get("bets", [])

        blocks = format_unified_slack_report(
            ncaab_data=ncaab_data,
            nba_predictions=nba_predictions,
            nba_bets=nba_bets,
            prop_data=prop_data,
        )

        if not blocks:
            logger.info("Slack report skipped: no blocks to send")
            return False

        slack = SlackService()
        ok = slack.send_blocks(blocks, text="Daily Picks Report")
        if ok:
            logger.info("Slack report sent successfully")
        else:
            logger.error("Slack report send FAILED")
        return ok

    except Exception as e:
        logger.error(f"Slack report pipeline failed: {e}")
        return False
