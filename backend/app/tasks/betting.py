"""
Betting-related background tasks
"""
from typing import Dict, Any
from loguru import logger
import anyio

from app.celery_app import app
from app.services.bet_settlement import BetSettlementEngine

@app.task(name="app.tasks.betting.place_bets_daily")
def place_bets_daily() -> Dict[str, Any]:
    """Run daily analysis and place identified +EV bets.
    This task triggers the NCAAB analysis pipeline.
    """
    logger.info("Starting daily bet placement task")
    
    # We'll call the run_analysis function from run_ncaab_analysis.py
    # Since it's in the parent directory, we handle imports carefully
    import sys
    import os
    backend_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
        
    try:
        from run_ncaab_analysis import run_analysis
        result = run_analysis()
        logger.info(f"Daily analysis complete. Identified {len(result.get('bets', []))} bets.")
        return {"ok": True, "bets_count": len(result.get('bets', []))}
    except Exception as e:
        logger.error(f"Daily bet placement failed: {e}")
        return {"ok": False, "error": str(e)}

@app.task(name="app.tasks.betting.settle_bets_daily")
def settle_bets_daily() -> Dict[str, Any]:
    """Settle pending bets by fetching results.
    Runs via celery-beat daily.
    """
    logger.info("Starting daily bet settlement task")
    
    engine = BetSettlementEngine()
    
    async def _settle():
        await engine.settle_pending_bets(sport="ncaab")
        await engine.settle_pending_bets(sport="nba")
        
    try:
        anyio.run(_settle)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Bet settlement task failed: {e}")
        return {"ok": False, "error": str(e)}

@app.task(name="app.tasks.betting.export_to_sheets_daily")
def export_to_sheets_daily() -> Dict[str, Any]:
    """Run full analysis and export results to Google Sheets."""
    logger.info("Starting daily Google Sheets export task")
    
    import sys
    import os
    backend_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
        
    try:
        from export_to_sheets import run_and_export
        async def _run():
            return await run_and_export()
            
        success = anyio.run(_run)
        return {"ok": success}
    except Exception as e:
        logger.error(f"Sheets export task failed: {e}")
        return {"ok": False, "error": str(e)}
