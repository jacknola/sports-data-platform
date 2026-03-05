import sys
import os
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.analysis_runner import (
    run_orchestrated_analysis,
    run_sheets_export_pipeline,
    run_prop_analysis_pipeline,
)


def main():
    """Runs the full analysis and export pipeline."""
    logger.info("Step 1: Running orchestrated analysis to generate new predictions...")
    analysis_data = run_orchestrated_analysis()
    ncaab_data = analysis_data.get("ncaab")
    nba_data = analysis_data.get("nba")

    logger.info("Step 2: Running prop analysis pipeline...")
    prop_data = run_prop_analysis_pipeline()

    logger.info("Step 3: Exporting all fresh data to Google Sheets...")
    export_result = run_sheets_export_pipeline(
        ncaab_data=ncaab_data, nba_data=nba_data, prop_data=prop_data
    )

    if export_result:
        logger.info("Pipeline completed successfully and data exported to Google Sheets.")
        return True
    else:
        logger.error("Google Sheets export failed. Check logs for details.")
        return False


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
