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


def test_export_parlays_writes_correct_columns() -> None:
    """Test that export_db_parlays formats parlay data correctly."""
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

        parlays = [
            {
                "title": "NBA Sunday Special",
                "sport": "NBA",
                "confidence_level": "HIGH",
                "confidence_score": 78.5,
                "legs": [
                    {"pick": "Lakers ML", "odds": -150},
                    {"pick": "Over 215.5", "odds": -110},
                ],
                "total_odds": 450,
                "potential_payout_multiplier": 5.5,
                "suggested_unit_size": 25.0,
                "status": "pending",
                "profit_loss": None,
                "roi": None,
                "tags": ["revenge-game", "pace-up"],
                "risks": ["Injury risk", "B2B fatigue"],
                "tweet_text": "Locking in this 2-leg parlay 🔥",
                "event_date": "2026-03-02",
            }
        ]
        result = service.export_db_parlays("mock_id", parlays)

    assert result.get("status") == "success"
    assert result.get("rows") == 1
    _, kwargs = mock_ws.update.call_args
    rows = kwargs["values"]
    assert rows[0][0] == "Date"  # header
    assert rows[1][1] == "NBA Sunday Special"
    assert rows[1][3] == 2  # 2 legs
    assert rows[1][4] == "HIGH"


def test_export_live_props_writes_correct_columns() -> None:
    """Test that export_live_props formats projection data correctly."""
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

        projections = [
            {
                "player_name": "Ty Jerome",
                "stat_type": "threes",
                "threshold": 3.5,
                "current_stat": 2,
                "minutes_remaining": 18.5,
                "projected_final": 4.1,
                "hot_hand_factor": 1.25,
                "pace_factor": 1.05,
                "garbage_time_discount": 1.0,
                "foul_discount": 1.0,
                "true_p_over": 0.62,
                "implied_p_over": 0.52,
                "edge_over": 0.10,
                "edge_under": -0.05,
                "kelly_fraction": 0.045,
                "verdict": "LEAN OVER",
            }
        ]
        result = service.export_live_props("mock_id", projections)

    assert result.get("status") == "success"
    assert result.get("rows") == 1
    _, kwargs = mock_ws.update.call_args
    rows = kwargs["values"]
    assert rows[0][0] == "Player"  # header
    assert rows[1][0] == "Ty Jerome"
    assert rows[1][1] == "3PM"  # stat_type mapped through _STAT_DISPLAY
    assert rows[1][16] == "LEAN OVER"
    assert rows[1][17] == "✅"  # positive EV


def test_export_daily_picks_includes_parlays_and_live_props() -> None:
    """Test that export_daily_picks calls parlay and live prop exports when data is provided."""
    service = GoogleSheetsService(credentials_path=None)
    service.client = MagicMock()

    service.export_props = MagicMock(return_value={"status": "success", "tab": "Props"})
    service.export_high_value_props = MagicMock(
        return_value={"status": "success", "tab": "HighValueProps"}
    )
    service.export_summary = MagicMock(
        return_value={"status": "success", "tab": "Summary"}
    )
    service.export_bet_slip = MagicMock(
        return_value={"status": "success", "tab": "BetSlip"}
    )
    service.export_parlays = MagicMock(
        return_value={"status": "success", "tab": "Parlays"}
    )
    service.export_live_props = MagicMock(
        return_value={"status": "success", "tab": "LiveProps"}
    )
    service.export_legend = MagicMock(
        return_value={"status": "success", "tab": "Legend"}
    )
    service.export_top10_plays = MagicMock(
        return_value={"status": "success", "tab": "Top10"}
    )
    service.export_bet_tracker = MagicMock(
        return_value={"status": "success", "tab": "BetTracker"}
    )

    parlay_suggestions = [{"title": "Test Parlay", "legs": []}]
    live_props_data = [{"player_name": "Test", "edge_over": 0.05}]

    results = service.export_daily_picks(
        spreadsheet_id="sheet123",
        prop_data={"props": [{"player_name": "X", "bayesian_edge": 0.04}]},
        parlay_suggestions=parlay_suggestions,
        live_props_data=live_props_data,
    )

    assert "parlays" in results
    assert "live_props" in results
    service.export_live_props.assert_called_once_with("sheet123", live_props_data)
