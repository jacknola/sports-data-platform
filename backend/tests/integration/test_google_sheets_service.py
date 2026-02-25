
import pytest
from unittest.mock import MagicMock, patch
import gspread
from app.services.google_sheets import GoogleSheetsService

@patch('gspread.service_account')
def test_export_ml_predictions_creates_and_writes_to_tab(mock_service_account):
    """
    Test that export_ml_predictions creates a new tab and writes the correct data.
    """
    # Mock the gspread client and sheet
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_client.open_by_key.return_value = mock_sheet
    
    # Simulate worksheet not found on first call, then return it
    mock_sheet.worksheet.side_effect = [gspread.exceptions.WorksheetNotFound, mock_worksheet]
    mock_sheet.add_worksheet.return_value = mock_worksheet
    
    # Patch gspread.exceptions.WorksheetNotFound
    with patch('gspread.exceptions.WorksheetNotFound', gspread.exceptions.WorksheetNotFound):
        sheets_service = GoogleSheetsService()
        sheets_service.client = mock_client

    spreadsheet_id = "test_sheet_id"
    nba_predictions = [
        {
            "home_team": "Team A",
            "away_team": "Team B",
            "moneyline_prediction": {"home_win_prob": 0.6},
            "underover_prediction": {"total_points": 220.5},
            "features": {"home_off_rating": 115.0}
        }
    ]

    sheets_service.export_ml_predictions(spreadsheet_id, nba_predictions)

    # Assert that the worksheet was updated in a single batch
    mock_worksheet.update.assert_called_once()
    
    # Check the data passed to the update call
    update_args = mock_worksheet.update.call_args[1]
    assert "values" in update_args
    values = update_args["values"]
    
    # Check headers
    assert values[0][0] == "Date"
    
    # Check data
    assert values[1][1] == "Team B" # Away team
    assert values[1][2] == "Team A" # Home team
    assert values[1][4] == 60.0 # Winner Prob %
