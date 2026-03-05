"""
NBA Player Prop Export — RAG-Enhanced

Runs the full player prop analysis pipeline (including Qdrant similarity search)
and exports the results to Google Sheets.
"""

import sys
import os
import asyncio
from datetime import datetime
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.google_sheets import GoogleSheetsService
from app.routers.props import run_prop_analysis
from app.config import settings

async def export_props_to_sheets():
    """
    Perform prop analysis and export to the configured spreadsheet.
    """
    print("\n" + "=" * 76)
    print(f"  NBA PLAYER PROP EXPORT — {datetime.now().strftime('%A, %B %d, %Y')}")
    print(f"  Methodology: Bayesian + Sharp RLM + Qdrant Situational RAG")
    print("=" * 76)

    # 1. Run Analysis
    import sys
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.info("Running full player prop analysis...")
    prop_data = await run_prop_analysis(sport="nba")
    
    if not prop_data or not prop_data.get("props"):
        print("\n  No player props found or analyzed for today's slate.")
        return

    # 2. Export to Sheets
    spreadsheet_id = settings.GOOGLE_SPREADSHEET_ID
    if not spreadsheet_id:
        logger.error("GOOGLE_SPREADSHEET_ID not configured in .env")
        print("\n  Error: Google Spreadsheet ID not found. Please check your .env file.")
        return

    logger.info(f"Exporting {len(prop_data['props'])} props to Sheets ({spreadsheet_id})...")
    
    sheets_service = GoogleSheetsService()
    if not sheets_service.is_configured:
        print("\n  Error: Google Sheets service not configured. Check service account path.")
        return

    result = sheets_service.export_props(spreadsheet_id, prop_data)
    
    if "error" in result:
        print(f"\n  Export (Raw) failed: {result['error']}")
    else:
        print(f"\n  ✅ Successfully exported {result['rows_written']} raw player props to 'Props' tab!")

    # 3. Export High Value Dashboard
    logger.info("Generating High Value Props Dashboard...")
    high_value_result = sheets_service.export_high_value_props(spreadsheet_id, prop_data)
    
    if "error" in high_value_result:
        print(f"\n  Export (High Value) failed: {high_value_result['error']}")
    else:
        print(f"  ✅ Successfully exported {high_value_result.get('rows_written', 0)} filtered props to 'HighValueProps' tab!")
        info = sheets_service.get_spreadsheet_info(spreadsheet_id)
        print(f"\n  View Dashboard here: {info.get('url')}")
    
    # 4. Export FanDuel Bets Dashboard
    logger.info("Generating FanDuel Bets Dashboard...")
    fanduel_result = sheets_service.export_fanduel_props(spreadsheet_id, prop_data)
    
    if "error" in fanduel_result:
        print(f"\n  Export (FanDuel) failed: {fanduel_result['error']}")
    else:
        print(f"  ✅ Successfully exported {fanduel_result.get('rows_written', 0)} filtered props to 'FanDuelBets' tab!")
        info = sheets_service.get_spreadsheet_info(spreadsheet_id)
        print(f"\n  View Dashboard here: {info.get('url')}")
    
    print("=" * 76 + "\n")
    
    if "error" in result:
        print(f"\n  Export failed: {result['error']}")
    else:
        print(f"\n  ✅ Successfully exported {result['rows_written']} player props to Google Sheets!")
        info = sheets_service.get_spreadsheet_info(spreadsheet_id)
        print(f"  View here: {info.get('url')}")
    
    print("=" * 76 + "\n")

if __name__ == "__main__":
    asyncio.run(export_props_to_sheets())
