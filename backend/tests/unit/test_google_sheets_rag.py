"""
Unit tests for GoogleSheetsService RAG enhancement.
"""
from unittest.mock import MagicMock, patch
from app.services.google_sheets import GoogleSheetsService

def test_export_props_with_rag_context():
    # Setup mock prop data
    prop_data = {
        "props": [
            {
                "player_name": "LeBron James",
                "stat_type": "pts",
                "line": 25.5,
                "best_side": "over",
                "bayesian_edge": 0.08,
                "situational_context": "Analog similarity: 70% Over"
            }
        ]
    }
    
    # Mock gspread and spreadsheet
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_ws = MagicMock()
    mock_client.open_by_key.return_value = mock_sheet
    mock_sheet.worksheet.return_value = mock_ws
    
    mock_creds = MagicMock()
    mock_gspread = MagicMock()
    mock_gspread.authorize.return_value = mock_client
    mock_gspread.WorksheetNotFound = Exception
    with patch("app.services.google_sheets.Credentials", mock_creds), \
         patch("app.services.google_sheets.gspread", mock_gspread):
        
        service = GoogleSheetsService(credentials_path="mock_creds.json")
        service.export_props("mock_id", prop_data)
        
        # Verify batch_write was called with correct data
        # We need to capture the values passed to update() or the internal _batch_write
        args, kwargs = mock_ws.update.call_args
        rows = kwargs["values"]
        
        # Headers should contain Situational Context
        assert "Situational Context" in rows[0]
        # Data row should contain the mock context
        assert "Analog similarity: 70% Over" in rows[1]
