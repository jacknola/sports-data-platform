from unittest.mock import MagicMock, patch

from app.services.google_sheets import GoogleSheetsService


def test_export_daily_picks_includes_high_value_props_tab() -> None:
    service = GoogleSheetsService(credentials_path=None)
    service.client = MagicMock()

    service.export_props = MagicMock(return_value={"status": "success", "tab": "Props"})
    service.export_high_value_props = MagicMock(
        return_value={"status": "success", "tab": "HighValueProps"}
    )
    service.export_nba = MagicMock(return_value={"status": "success", "tab": "NBA"})
    service.export_ncaab = MagicMock(return_value={"status": "success", "tab": "NCAAB"})
    service.export_summary = MagicMock(
        return_value={"status": "success", "tab": "Summary"}
    )

    prop_data = {"props": [{"player_name": "Test Player", "bayesian_edge": 0.04}]}
    results = service.export_daily_picks(
        spreadsheet_id="sheet123",
        ncaab_data=None,
        nba_predictions=None,
        nba_bets=None,
        prop_data=prop_data,
    )

    assert "props" in results
    assert "high_value_props" in results
    service.export_props.assert_called_once_with("sheet123", prop_data)
    service.export_high_value_props.assert_called_once_with("sheet123", prop_data)


def test_export_props_handles_string_odds_without_crashing() -> None:
    prop_data = {
        "props": [
            {
                "player_name": "LeBron James",
                "stat_type": "points",
                "line": 25.5,
                "best_side": "over",
                "bayesian_edge": 0.08,
                "situational_context": "Analog similarity: 70% Over",
                "over_odds": "+105",
                "under_odds": "-120",
            }
        ]
    }

    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_ws = MagicMock()
    mock_client.open_by_key.return_value = mock_sheet
    mock_sheet.worksheet.return_value = mock_ws

    with (
        patch("app.services.google_sheets.Credentials.from_service_account_file"),
        patch("app.services.google_sheets.gspread.authorize", return_value=mock_client),
    ):
        service = GoogleSheetsService(credentials_path="mock_creds.json")
        result = service.export_props("mock_id", prop_data)

    assert result.get("status") == "success"
    args, kwargs = mock_ws.update.call_args
    rows = kwargs["values"]
    assert rows[1][8] == "+105"
    assert rows[1][19] == "+105"
    assert rows[1][20] == "-120"
