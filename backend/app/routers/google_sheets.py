"""
Google Sheets export endpoints

Exports daily picks (Props, NBA, NCAAB, Summary) to Google Sheets.
Uses the GoogleSheetsService which requires a service account JSON
configured via GOOGLE_SERVICE_ACCOUNT_PATH.

Endpoints:
  POST /sheets/export-daily          — Full daily export (all tabs)
  POST /sheets/{id}/export-props     — Props tab only
  POST /sheets/{id}/export-nba       — NBA tab only
  POST /sheets/{id}/export-ncaab     — NCAAB tab only
  GET  /sheets/{id}/info             — Spreadsheet metadata
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from loguru import logger

from app.config import settings
from app.services.google_sheets import GoogleSheetsService

router = APIRouter()
_sheets = GoogleSheetsService()


# ───────────────────────────────────────────────────────────────
# Full daily export
# ───────────────────────────────────────────────────────────────


@router.post("/sheets/export-daily")
async def export_daily_picks(
    spreadsheet_id: Optional[str] = Query(
        default=None,
        description="Google Sheets ID (defaults to GOOGLE_SPREADSHEET_ID from .env)",
    ),
    ncaab_data: Optional[Dict[str, Any]] = None,
    nba_predictions: Optional[List[Dict[str, Any]]] = None,
    nba_bets: Optional[List[Dict[str, Any]]] = None,
    prop_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Export all daily picks to Google Sheets (Props + NBA + NCAAB + Summary).

    If no spreadsheet_id is provided, falls back to GOOGLE_SPREADSHEET_ID
    from settings. Pass analysis data in the request body, or call with
    empty body to export a blank template.
    """
    sid = spreadsheet_id or settings.GOOGLE_SPREADSHEET_ID
    if not sid:
        raise HTTPException(
            status_code=400,
            detail="No spreadsheet_id provided and GOOGLE_SPREADSHEET_ID not set",
        )
    if not _sheets.is_configured:
        raise HTTPException(status_code=503, detail="Google Sheets not configured")

    try:
        result = _sheets.export_daily_picks(
            spreadsheet_id=sid,
            ncaab_data=ncaab_data,
            nba_predictions=nba_predictions,
            nba_bets=nba_bets,
            prop_data=prop_data,
        )
        return result
    except Exception as e:
        logger.error(f"Daily export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────────────────────────────────────
# Per-tab exports
# ───────────────────────────────────────────────────────────────


@router.post("/sheets/{spreadsheet_id}/export-props")
async def export_props(
    spreadsheet_id: str,
    prop_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Export player prop analysis to the Props tab."""
    if not _sheets.is_configured:
        raise HTTPException(status_code=503, detail="Google Sheets not configured")
    try:
        return _sheets.export_props(spreadsheet_id, prop_data)
    except Exception as e:
        logger.error(f"Props export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/{spreadsheet_id}/export-nba")
async def export_nba(
    spreadsheet_id: str,
    predictions: List[Dict[str, Any]],
    bets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Export NBA game predictions to the NBA tab."""
    if not _sheets.is_configured:
        raise HTTPException(status_code=503, detail="Google Sheets not configured")
    try:
        return _sheets.export_nba(spreadsheet_id, predictions, bets or [])
    except Exception as e:
        logger.error(f"NBA export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/{spreadsheet_id}/export-ncaab")
async def export_ncaab(
    spreadsheet_id: str,
    ncaab_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Export NCAAB sharp money analysis to the NCAAB tab."""
    if not _sheets.is_configured:
        raise HTTPException(status_code=503, detail="Google Sheets not configured")
    try:
        return _sheets.export_ncaab(spreadsheet_id, ncaab_data)
    except Exception as e:
        logger.error(f"NCAAB export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────────────────────────────────────
# Info
# ───────────────────────────────────────────────────────────────


@router.get("/sheets/{spreadsheet_id}/info")
async def get_spreadsheet_info(spreadsheet_id: str) -> Dict[str, Any]:
    """Get spreadsheet metadata (title, URL, worksheet names)."""
    if not _sheets.is_configured:
        raise HTTPException(status_code=503, detail="Google Sheets not configured")
    try:
        return _sheets.get_spreadsheet_info(spreadsheet_id)
    except Exception as e:
        logger.error(f"Get info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

