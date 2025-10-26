# Google Sheets Integration

## Overview

The platform integrates with Google Sheets for automatic data syncing and analysis tracking.

## Setup

### 1. Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "Google Sheets API" and "Google Drive API"
4. Create credentials → Service Account
5. Download JSON key file
6. Save as `service-account.json` in the project root

### 2. Share Spreadsheet

1. Create a Google Sheet
2. Click "Share" → Add service account email from JSON
3. Give "Editor" permissions
4. Copy the Spreadsheet ID from URL

### 3. Configure Environment

Add to `.env`:
```bash
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
```

## Features

### 1. Write Bet Analysis
Automatically writes bet analysis results to sheets.

### 2. Sync Predictions
Bulk sync predictions with data validation.

### 3. Daily Summary
Creates date-stamped daily summary sheets.

### 4. Spreadsheet Info
Get information about your spreadsheet.

## API Endpoints

### Write Bet Analysis
```bash
POST /api/v1/sheets/{spreadsheet_id}/bet-analysis

{
  "date": "2024-01-15",
  "sport": "NFL",
  "game": "Bills vs Chiefs",
  "market": "Spread",
  "edge": 0.085,
  "probability": 0.65,
  "odds": -110,
  "recommendation": "BET",
  "confidence": 0.75
}
```

### Sync Predictions
```bash
POST /api/v1/sheets/{spreadsheet_id}/sync-predictions

[
  {
    "date": "2024-01-15",
    "team": "Bills",
    "opponent": "Chiefs",
    "market": "Spread",
    "prediction": "Bills -3.5",
    "probability": 0.65,
    "confidence": 0.75,
    "edge": 0.08,
    "recommendation": "BET"
  }
]
```

### Create Daily Summary
```bash
POST /api/v1/sheets/{spreadsheet_id}/daily-summary

{
  "total_bets": 50,
  "value_bets": 5,
  "avg_edge": 0.06,
  "win_rate": 0.65,
  "top_bets": [
    {
      "team": "Bills",
      "market": "Spread",
      "edge": 0.12,
      "confidence": 0.85
    }
  ]
}
```

### Get Spreadsheet Info
```bash
GET /api/v1/sheets/{spreadsheet_id}/info
```

## Usage Examples

### In Agent Orchestrator
```python
from app.services.google_sheets import GoogleSheetsService

sheets_service = GoogleSheetsService()

# After analysis, sync to sheet
await sheets_service.write_bet_analysis(
    spreadsheet_id="abc123",
    analysis={
        'date': '2024-01-15',
        'sport': 'NFL',
        'edge': 0.085,
        'recommendation': 'BET'
    }
)
```

## Sheet Structure

### Bet Analysis Sheet
```
| Date | Sport | Game | Market | Edge | Probability | Odds | Recommendation | Confidence |
```

### Predictions Sheet
```
| Date | Team | Opponent | Market | Prediction | Probability | Confidence | Edge | Recommendation |
```

### Daily Summary Sheet
```
Daily Summary | 2024-01-15 14:30

Total Bets Analyzed | 50
Value Bets Found | 5
Average Edge | 0.06
Win Rate | 0.65

Top Recommendations
Team | Market | Edge | Confidence
```

## Benefits

✅ **Automated Tracking** - No manual data entry  
✅ **Historical Analysis** - Track performance over time  
✅ **Team Collaboration** - Share sheets with team  
✅ **Data Visualization** - Use Google Sheets charts  
✅ **Export Capabilities** - Export to Excel/CSV  

## Next Steps

1. Set up service account credentials
2. Create Google Sheet
3. Configure environment variables
4. Start syncing data!

