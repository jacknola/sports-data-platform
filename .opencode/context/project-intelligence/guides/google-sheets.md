<!-- Context: project-intelligence/guides/google-sheets | Priority: medium | Version: 1.0 | Updated: 2026-02-27 -->

# Google Sheets Integration

**Purpose**: Export bet analysis, predictions, and daily summaries to Google Sheets.
**Last Updated**: 2026-02-27

## Setup

1. Create GCP service account with Sheets + Drive API enabled
2. Download JSON credentials
3. Share target spreadsheet with service account email
4. Set env vars:

```bash
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/credentials.json
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sheets/{id}/bet-analysis` | POST | Write bet analysis rows |
| `/sheets/{id}/sync-predictions` | POST | Sync model predictions |
| `/sheets/{id}/daily-summary` | POST | Write daily P&L summary |
| `/sheets/{id}/info` | GET | Sheet metadata |

## Sheet Structures

**Bet Analysis**: Date, Sport, Game, Bet Type, Edge%, Kelly Stake, Book, Odds, Result
**Predictions**: Date, Game, ML Prob, O/U Prob, Spread, Model Confidence, Actual, CLV, Notes
**Daily Summary**: Total bets, wins, losses, ROI, bankroll, top bets

## Usage

```python
from app.services.google_sheets_service import GoogleSheetsService

sheets = GoogleSheetsService()
sheets.write_bet_analysis(spreadsheet_id, analysis_data)
```

## 📂 Codebase References

- **Service**: `backend/app/services/google_sheets_service.py`
- **Router**: `backend/app/routers/sheets_router.py`
- **MCP**: `sheets-reporting` MCP server
- **Full docs**: `GOOGLE_SHEETS.md` (root)
