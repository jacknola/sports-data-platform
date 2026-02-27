"""
Export Daily Picks to Google Sheets

Runs NCAAB, NBA, and Player Prop analysis, then writes results to
Google Sheets with separate tabs: Props, NBA, NCAAB, Summary.

Usage:
    python backend/export_to_sheets.py              # Full export
    python backend/export_to_sheets.py --props-only # Props tab only
    python backend/export_to_sheets.py --nba-only   # NBA tab only
    python backend/export_to_sheets.py --ncaab-only # NCAAB tab only
    python backend/export_to_sheets.py --test       # Test connection
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

BANKROLL = 100.0


# ---------------------------------------------------------------------------
# Pipelines (same as send_slack_report.py)
# ---------------------------------------------------------------------------


async def _run_nba() -> tuple:
    """Run NBA ML analysis. Returns (predictions, bets)."""
    from app.services.nba_ml_predictor import NBAMLPredictor
    from datetime import datetime

    logger.info("Running NBA ML analysis...")
    predictor = NBAMLPredictor()
    predictions = await predictor.predict_today_games("nba")

    if not predictions:
        logger.warning("No NBA games found today")
        return [], []

    bets: List[Dict[str, Any]] = []
    for p in predictions:
        if "error" in p:
            continue

        ev = p["expected_value"]
        best_bet = ev["best_bet"]
        home_edge = ev.get("home_ev", 0)
        away_edge = ev.get("away_ev", 0)
        kelly_fraction = p.get("kelly_criterion", 0)

        best_side_team = p["home_team"] if best_bet == "home" else p["away_team"]
        best_side_odds = ev["home_odds"] if best_bet == "home" else ev["away_odds"]
        best_side_edge = home_edge if best_bet == "home" else away_edge

        if kelly_fraction > 0.001 and best_side_edge > 0.025:
            bets.append({
                "game_id": f"NBA_{p['home_team']}_{p['away_team']}_{datetime.now().strftime('%Y%m%d')}".replace(" ", ""),
                "sport": "nba",
                "side": best_side_team,
                "market": "moneyline",
                "odds": best_side_odds,
                "edge": best_side_edge,
                "bet_size": kelly_fraction * BANKROLL,
            })

    logger.info(f"NBA: {len(predictions)} games, {len(bets)} qualifying bets")
    return predictions, bets


async def _run_ncaab_ml() -> List[Dict[str, Any]]:
    """Run NCAAB ML predictor (Pythagorean / XGBoost). Returns list of predictions."""
    try:
        from app.services.ncaab_ml_predictor import NCAABMLPredictor

        logger.info("Running NCAAB ML predictions...")
        predictor = NCAABMLPredictor()
        predictions = await predictor.predict_today_games()
        logger.info(f"NCAAB ML: {len(predictions)} predictions")
        return predictions
    except Exception as e:
        logger.error(f"NCAAB ML predictor failed: {e}")
        return []


async def _run_ncaab() -> Optional[Dict[str, Any]]:
    """Run NCAAB sharp money analysis."""
    import concurrent.futures

    def _sync_ncaab() -> Dict[str, Any]:
        from run_ncaab_analysis import run_analysis as run_ncaab
        return run_ncaab()

    try:
        logger.info("Running NCAAB analysis...")
        loop = asyncio.get_event_loop()
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_and_export(
    include_ncaab: bool = True,
    include_nba: bool = True,
    include_props: bool = True,
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
    ncaab_ml_predictions: List[Dict[str, Any]] = []
    nba_predictions: List[Dict[str, Any]] = []
    nba_bets: List[Dict[str, Any]] = []
    prop_data: Optional[Dict[str, Any]] = None

    # Run pipelines
    if include_ncaab:
        ncaab_data = await _run_ncaab()
        ncaab_ml_predictions = await _run_ncaab_ml()

    if include_nba:
        nba_predictions, nba_bets = await _run_nba()

    if include_props:
        prop_data = await _run_props()

    # Check if we have anything
    has_ncaab = ncaab_data and ncaab_data.get("game_analyses")
    has_ncaab_ml = bool(ncaab_ml_predictions)
    has_nba = bool(nba_predictions)
    has_props = prop_data and prop_data.get("props")

    if not has_ncaab and not has_ncaab_ml and not has_nba and not has_props:
        logger.warning("No data from any pipeline — nothing to export")
        return False

    # Export core tabs via export_daily_picks (NBA odds, NBA ML Predictions, NCAAB sharp, Props, Summary)
    results = sheets.export_daily_picks(
        spreadsheet_id=spreadsheet_id,
        ncaab_data=ncaab_data if has_ncaab else None,
        nba_predictions=nba_predictions if has_nba else None,
        nba_bets=nba_bets,
        prop_data=prop_data if has_props else None,
    )

    # Export NCAAB ML predictions to its own tab
    if has_ncaab_ml:
        results["ncaab_ml"] = sheets.export_ml_predictions(
            spreadsheet_id=spreadsheet_id,
            predictions=ncaab_ml_predictions,
            sport="NCAAB",
            tab_name="NCAAB ML",
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

    if args.props_only:
        include_ncaab, include_nba, include_props = False, False, True
    elif args.nba_only:
        include_ncaab, include_nba, include_props = False, True, False
    elif args.ncaab_only:
        include_ncaab, include_nba, include_props = True, False, False
    else:
        include_ncaab, include_nba, include_props = True, True, True

    ok = asyncio.run(run_and_export(
        include_ncaab=include_ncaab,
        include_nba=include_nba,
        include_props=include_props,
    ))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
