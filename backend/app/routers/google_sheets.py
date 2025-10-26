"""
Google Sheets integration endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from loguru import logger

from app.services.google_sheets import GoogleSheetsService

router = APIRouter()
sheets_service = GoogleSheetsService()


@router.post("/sheets/{spreadsheet_id}/bet-analysis")
async def write_bet_analysis(
    spreadsheet_id: str,
    analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Write bet analysis to Google Sheet
    
    Args:
        spreadsheet_id: ID of the Google Sheet
        analysis: Analysis data to write
        
    Returns:
        Write result
    """
    try:
        result = await sheets_service.write_bet_analysis(
            spreadsheet_id,
            analysis
        )
        return result
    except Exception as e:
        logger.error(f"Write bet analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/{spreadsheet_id}/sync-predictions")
async def sync_predictions(
    spreadsheet_id: str,
    predictions: List[Dict[str, Any]],
    worksheet_name: str = "Predictions"
) -> Dict[str, Any]:
    """
    Sync predictions to Google Sheet
    
    Args:
        spreadsheet_id: ID of the Google Sheet
        predictions: List of predictions to sync
        worksheet_name: Name of worksheet
        
    Returns:
        Sync result
    """
    try:
        result = await sheets_service.sync_predictions(
            spreadsheet_id,
            predictions,
            worksheet_name
        )
        return result
    except Exception as e:
        logger.error(f"Sync predictions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/{spreadsheet_id}/daily-summary")
async def create_daily_summary(
    spreadsheet_id: str,
    summary: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create daily summary in Google Sheet
    
    Args:
        spreadsheet_id: ID of the Google Sheet
        summary: Summary data
        
    Returns:
        Create result
    """
    try:
        result = await sheets_service.create_daily_summary(
            spreadsheet_id,
            summary
        )
        return result
    except Exception as e:
        logger.error(f"Create summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sheets/{spreadsheet_id}/info")
async def get_spreadsheet_info(spreadsheet_id: str) -> Dict[str, Any]:
    """
    Get spreadsheet information
    
    Args:
        spreadsheet_id: ID of the Google Sheet
        
    Returns:
        Spreadsheet info
    """
    try:
        result = await sheets_service.get_spreadsheet_info(spreadsheet_id)
        return result
    except Exception as e:
        logger.error(f"Get info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

