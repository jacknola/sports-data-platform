"""
Export Daily Picks to Google Sheets

Runs NCAAB, NBA, Player Prop, and Parlay analysis, then writes results to
Google Sheets with separate tabs: Props, HighValueProps, NBA, NCAAB, Parlays,
LiveProps, Predictions, Summary, BetSlip.

Usage:
    python backend/export_to_sheets.py                   # Full export
    python backend/export_to_sheets.py --props-only      # Props tab only
    python backend/export_to_sheets.py --nba-only        # NBA tab only
    python backend/export_to_sheets.py --ncaab-only      # NCAAB tab only
    python backend/export_to_sheets.py --parlays-only    # Parlays tab only
    python backend/export_to_sheets.py --predictions-only# Predictions tab only
    python backend/export_to_sheets.py --test            # Test connection
"""

import sys
import os
import argparse
import asyncio
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.services.google_sheets import GoogleSheetsService
from app.config import settings

os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/sheets_export.log",
    rotation="7 days",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------


async def _run_nba() -> tuple:
    """Run NBA ML analysis via run_nba_analysis(). Returns (predictions, bets)."""
    import concurrent.futures

    def _sync_nba() -> Dict[str, Any]:
        from run_nba_analysis import run_nba_analysis as _run
        import asyncio as _aio
        return _aio.run(_run())

    try:
        logger.info("Running NBA ML analysis...")
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, _sync_nba)
        predictions = result.get("predictions", [])
        bets = result.get("bets", [])
        logger.info(f"NBA: {len(predictions)} games, {len(bets)} qualifying bets")
        return predictions, bets
    except Exception as e:
        logger.error(f"NBA analysis failed: {e}")
        return [], []


async def _run_ncaab() -> Optional[Dict[str, Any]]:
    """Run NCAAB sharp money analysis."""
    import concurrent.futures

    def _sync_ncaab() -> Dict[str, Any]:
        from run_ncaab_analysis import run_analysis as run_ncaab
        return run_ncaab()

    try:
        logger.info("Running NCAAB analysis...")
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, _sync_ncaab)
        logger.info(
            f"NCAAB: {result['game_count']} games, "
            f"{len(result.get('bets', []))} bets"
        )
        return result
    except Exception as e:
        logger.error(f"NCAAB analysis failed: {e}")
        return None


async def _run_props() -> Optional[Dict[str, Any]]:
    """Run player prop analysis."""
    try:
        from app.routers.props import run_prop_analysis

        logger.info("Running player prop analysis...")
        result = await run_prop_analysis("nba")
        logger.info(
            f"Props: {result.get('total_props', 0)} scanned, "
            f"{result.get('positive_ev_count', 0)} +EV"
        )
        return result
    except Exception as e:
        logger.error(f"Prop analysis failed: {e}")
        return None


def _fetch_parlays() -> List[Dict[str, Any]]:
    """Fetch all parlays from the database."""
    try:
        from app.database import SessionLocal
        from app.models.parlay import Parlay

        db = SessionLocal()
        try:
            parlays = db.query(Parlay).order_by(Parlay.created_at.desc()).all()
            result = []
            for p in parlays:
                result.append({
                    "parlay_id": p.parlay_id,
                    "title": p.title,
                    "sport": p.sport,
                    "confidence_level": p.confidence_level,
                    "confidence_score": p.confidence_score,
                    "legs": p.legs or [],
                    "total_odds": p.total_odds,
                    "potential_payout_multiplier": p.potential_payout_multiplier,
                    "suggested_unit_size": p.suggested_unit_size,
                    "status": p.status,
                    "profit_loss": p.profit_loss,
                    "roi": p.roi,
                    "tags": p.tags or [],
                    "risks": p.risks or [],
                    "tweet_text": p.tweet_text,
                    "event_date": str(p.event_date) if p.event_date else "",
                    "created_at": str(p.created_at) if p.created_at else "",
                })
            logger.info(f"Fetched {len(result)} parlays from database")
            return result
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to fetch parlays: {e}")
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_and_export(
    include_ncaab: bool = True,
    include_nba: bool = True,
    include_props: bool = True,
    predictions_only: bool = False,
    include_parlays: bool = True,
    include_live_props: bool = False,
    live_props_data: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """Run all pipelines and export to Google Sheets."""
    spreadsheet_id = (
        settings.GOOGLE_SPREADSHEET_ID
        or os.getenv("GOOGLE_SPREADSHEET_ID")
    )
    if not spreadsheet_id:
        logger.error("GOOGLE_SPREADSHEET_ID not set in .env")
        return False

    sheets = GoogleSheetsService()
    if not sheets.is_configured:
        logger.error("Google Sheets not configured — check GOOGLE_SERVICE_ACCOUNT_PATH")
        return False

    ncaab_data: Optional[Dict[str, Any]] = None
    nba_predictions: List[Dict[str, Any]] = []
    nba_bets: List[Dict[str, Any]] = []
    prop_data: Optional[Dict[str, Any]] = None
    parlay_data: List[Dict[str, Any]] = []

    # Predictions-only: run NCAAB + NBA (no props needed), export just that tab
    if predictions_only:
        include_ncaab = include_nba = True
        include_props = False

    # Run pipelines
    if include_ncaab:
        ncaab_data = await _run_ncaab()

    if include_nba:
        nba_predictions, nba_bets = await _run_nba()

    if include_props:
        prop_data = await _run_props()

    if include_parlays:
        parlay_data = _fetch_parlays()

    # Check if we have anything
    has_ncaab = ncaab_data and ncaab_data.get("game_analyses")
    has_nba = bool(nba_predictions)
    has_props = prop_data and prop_data.get("props")
    has_parlays = bool(parlay_data)
    has_live_props = bool(live_props_data)

    if not has_ncaab and not has_nba and not has_props and not has_parlays and not has_live_props:
        logger.warning("No data from any pipeline — nothing to export")
        return False

    # Generate parlay suggestions from today's picks
    parlay_suggestions: List[Dict[str, Any]] = []
    try:
        from app.services.parlay_engine import generate_suggestions as _gen_parlays
        parlay_suggestions = _gen_parlays(
            props=prop_data.get("best_props", []) if prop_data else [],
            ncaab_analyses=ncaab_data.get("game_analyses", []) if ncaab_data else [],
            nba_bets=nba_bets,
        )
        logger.info(f"Parlay engine: {len(parlay_suggestions)} suggestions generated")
    except Exception as parlay_err:
        logger.warning(f"Parlay engine failed (non-fatal): {parlay_err}")

    # Export
    if predictions_only:
        results = {
            "predictions": sheets.export_predictions_comparison(
                spreadsheet_id=spreadsheet_id,
                ncaab_data=ncaab_data if has_ncaab else None,
                nba_predictions=nba_predictions if has_nba else None,
            )
        }
    else:
        results = sheets.export_daily_picks(
            spreadsheet_id=spreadsheet_id,
            ncaab_data=ncaab_data if has_ncaab else None,
            nba_predictions=nba_predictions if has_nba else None,
            nba_bets=nba_bets,
            prop_data=prop_data if has_props else None,
            parlay_suggestions=parlay_suggestions,
            live_props_data=live_props_data if has_live_props else None,
        )

    # Report
    errors = [k for k, v in results.items() if isinstance(v, dict) and v.get("error")]
    if errors:
        logger.error(f"Export errors in tabs: {errors}")
        for k in errors:
            logger.error(f"  {k}: {results[k]['error']}")
        return False

    logger.info(
        f"Google Sheets export complete → "
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Export picks to Google Sheets")
    parser.add_argument("--test", action="store_true", help="Test Sheets connection")
    parser.add_argument("--props-only", action="store_true", help="Props tab only")
    parser.add_argument("--nba-only", action="store_true", help="NBA tab only")
    parser.add_argument("--ncaab-only", action="store_true", help="NCAAB tab only")
    parser.add_argument("--parlays-only", action="store_true", help="Parlays tab only")
    parser.add_argument(
        "--predictions-only",
        action="store_true",
        help="Predictions comparison tab only (model vs market, all sports)",
    )
    args = parser.parse_args()

    if args.test:
        sheets = GoogleSheetsService()
        if not sheets.is_configured:
            print("❌ Google Sheets not configured")
            print("   Set GOOGLE_SERVICE_ACCOUNT_PATH in backend/.env")
            sys.exit(1)
        sid = settings.GOOGLE_SPREADSHEET_ID or os.getenv("GOOGLE_SPREADSHEET_ID")
        if not sid:
            print("❌ GOOGLE_SPREADSHEET_ID not set")
            sys.exit(1)
        info = sheets.get_spreadsheet_info(sid)
        if info.get("error"):
            print(f"❌ {info['error']}")
            sys.exit(1)
        print(f"✅ Connected to: {info['title']}")
        print(f"   URL: {info['url']}")
        print(f"   Tabs: {', '.join(info['worksheets'])}")
        sys.exit(0)

    predictions_only = args.predictions_only
    if predictions_only:
        include_ncaab, include_nba, include_props, include_parlays = True, True, False, False
    elif args.props_only:
        include_ncaab, include_nba, include_props, include_parlays = False, False, True, False
    elif args.nba_only:
        include_ncaab, include_nba, include_props, include_parlays = False, True, False, False
    elif args.ncaab_only:
        include_ncaab, include_nba, include_props, include_parlays = True, False, False, False
    elif args.parlays_only:
        include_ncaab, include_nba, include_props, include_parlays = False, False, False, True
    else:
        include_ncaab, include_nba, include_props, include_parlays = True, True, True, True

    ok = asyncio.run(run_and_export(
        include_ncaab=include_ncaab,
        include_nba=include_nba,
        include_props=include_props,
        predictions_only=predictions_only,
        include_parlays=include_parlays,
    ))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
