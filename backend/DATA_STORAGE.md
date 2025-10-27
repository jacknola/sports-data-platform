# Data Storage and Cleaning System

## Overview

This system automatically cleans, validates, and stores betting data from sports data platforms into the database. Every time you fetch best bets, the data is processed and stored properly.

## Components

### 1. Data Cleaner Service (`app/services/data_cleaner.py`)

Handles data validation and normalization:

- **Sport Names**: Normalizes sport names (e.g., "basketball" → "NBA")
- **Team Names**: Cleans special characters and extra whitespace
- **Market Types**: Standardizes market types (e.g., "h2h" → "moneyline")
- **Odds Validation**: Ensures odds are within valid ranges (-10000 to +10000)
- **Probability Validation**: Validates probabilities are between 0 and 1
- **Edge Validation**: Validates edge values and converts percentages
- **DateTime Parsing**: Handles multiple datetime formats

### 2. Bet Storage Service (`app/services/bet_storage.py`)

Manages database operations:

- **Game Management**: Creates or updates game records
- **Bet Storage**: Creates or updates bet records
- **Duplicate Prevention**: Uses unique IDs to prevent duplicates
- **Relationship Management**: Links bets to games properly
- **Batch Operations**: Efficiently stores multiple bets

### 3. Updated Endpoints

#### GET `/bets` - Get Best Bets
Now automatically stores cleaned data in database by default.

**Query Parameters:**
- `sport`: Sport to analyze (default: "nba")
- `min_edge`: Minimum edge threshold (default: 0.05)
- `limit`: Maximum bets to return (default: 10)
- `store_data`: Store in database (default: true)

**Example:**
```bash
curl "http://localhost:8000/bets?sport=nba&min_edge=0.05&store_data=true"
```

**Response includes storage results:**
```json
{
  "sport": "NBA",
  "timestamp": "2025-10-27T10:00:00",
  "total_bets": 5,
  "min_edge": 0.05,
  "bets": [...],
  "storage": {
    "total_bets": 5,
    "saved": 3,
    "updated": 2,
    "failed": 0,
    "errors": []
  }
}
```

#### POST `/bets/store` - Manually Store Bets
Store best bets data from any sports platform.

**Request Body:**
```json
[
  {
    "sport": "NBA",
    "team": "Lakers",
    "market": "moneyline",
    "current_odds": -150,
    "edge": 0.08,
    "probability": 0.60,
    "game": {
      "home_team": "Lakers",
      "away_team": "Warriors",
      "game_date": "2025-10-27T19:00:00Z"
    }
  }
]
```

**Response:**
```json
{
  "success": true,
  "message": "Processed 1 bets",
  "results": {
    "total_bets": 1,
    "saved": 1,
    "updated": 0,
    "failed": 0,
    "errors": []
  }
}
```

#### POST `/odds/store` - Store Odds Data
Store odds data from Odds API or similar platforms.

**Request Body (Odds API format):**
```json
[
  {
    "id": "game123",
    "sport_key": "basketball_nba",
    "commence_time": "2025-10-27T19:00:00Z",
    "home_team": "Lakers",
    "away_team": "Warriors",
    "bookmakers": [
      {
        "key": "draftkings",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              {"name": "Lakers", "price": -150},
              {"name": "Warriors", "price": 130}
            ]
          }
        ]
      }
    ]
  }
]
```

#### GET `/bets/stored` - Retrieve Stored Bets
Get bets from database with filtering.

**Query Parameters:**
- `sport`: Filter by sport (optional)
- `min_edge`: Minimum edge filter (optional)
- `limit`: Maximum bets to return (default: 50)

**Example:**
```bash
curl "http://localhost:8000/bets/stored?sport=NBA&min_edge=0.05"
```

#### GET `/odds/{sport}` - Get and Store Odds
Fetch odds from external API and optionally store them.

**Query Parameters:**
- `store_data`: Store in database (default: false)

**Example:**
```bash
curl "http://localhost:8000/odds/nba?store_data=true"
```

## Data Flow

### Automatic Storage Flow

1. **Fetch Data**: Get best bets from sports platform or ML predictions
2. **Clean Data**: Validate and normalize all fields
3. **Store Game**: Create or update game record in database
4. **Store Bets**: Create or update bet records linked to game
5. **Return Results**: Return both bet data and storage statistics

### Manual Storage Flow

1. **Receive Raw Data**: Accept raw data from any sports platform
2. **Clean & Validate**: Process through data cleaner
3. **Store in DB**: Save to database with proper relationships
4. **Return Status**: Provide detailed storage results

## Data Cleaning Examples

### Before Cleaning (Raw Data)
```json
{
  "sport": "basketball",
  "team": "Los Angeles Lakers  ",
  "market": "h2h",
  "current_odds": "-150.0",
  "edge": "8%",
  "probability": "60",
  "game_date": "2025-10-27T19:00:00Z"
}
```

### After Cleaning
```json
{
  "sport": "NBA",
  "team": "Los Angeles Lakers",
  "market": "moneyline",
  "current_odds": -150.0,
  "edge": 0.08,
  "probability": 0.60,
  "game_date": "2025-10-27 19:00:00"
}
```

## Database Schema

### Games Table
- `id`: Primary key
- `external_game_id`: Unique game identifier
- `sport`: Sport name (normalized)
- `home_team`: Home team name
- `away_team`: Away team name
- `game_date`: Game date/time
- `home_score`: Final home score (nullable)
- `away_score`: Final away score (nullable)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### Bets Table
- `id`: Primary key
- `selection_id`: Unique bet identifier
- `sport`: Sport name
- `game_id`: Foreign key to games table
- `team`: Team/selection name
- `market`: Market type (moneyline, spread, total)
- `current_odds`: Current odds value
- `implied_prob`: Implied probability
- `devig_prob`: Devigged probability
- `posterior_prob`: Posterior probability from model
- `fair_american_odds`: Fair odds calculation
- `edge`: Expected value/edge
- `kelly_fraction`: Kelly criterion fraction
- `features`: JSON field with model features
- `confidence_interval`: JSON field with confidence data
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

## Error Handling

The system handles errors gracefully:

- **Validation Errors**: Invalid data is logged and skipped
- **Duplicate Prevention**: Uses unique IDs to avoid duplicates
- **Database Errors**: Rolls back transactions on errors
- **Detailed Logging**: All operations are logged with loguru

## Usage Examples

### Example 1: Automatic Storage with Best Bets
```python
# This happens automatically when you call GET /bets
response = requests.get(
    "http://localhost:8000/bets",
    params={"sport": "nba", "store_data": True}
)
```

### Example 2: Manual Storage
```python
import requests

# Prepare your bets data
bets_data = [
    {
        "sport": "NBA",
        "team": "Lakers",
        "market": "moneyline",
        "current_odds": -150,
        "edge": 0.08,
        "probability": 0.60,
        "game": {
            "home_team": "Lakers",
            "away_team": "Warriors",
            "game_date": "2025-10-27T19:00:00Z"
        }
    }
]

# Store the data
response = requests.post(
    "http://localhost:8000/bets/store",
    json=bets_data
)
```

### Example 3: Fetch and Store Odds
```python
# Fetch odds from external API and store automatically
response = requests.get(
    "http://localhost:8000/odds/nba",
    params={"store_data": True}
)
```

### Example 4: Retrieve Stored Bets
```python
# Get stored bets with filtering
response = requests.get(
    "http://localhost:8000/bets/stored",
    params={
        "sport": "NBA",
        "min_edge": 0.05,
        "limit": 20
    }
)
```

## Benefits

1. **Data Quality**: All data is validated and normalized
2. **No Duplicates**: Unique IDs prevent duplicate entries
3. **Easy Integration**: Works with any sports data platform
4. **Flexible**: Can store automatically or manually
5. **Traceable**: Detailed logging and error reporting
6. **Historical Data**: All bets are timestamped and tracked
7. **Relationships**: Games and bets are properly linked

## Monitoring

Check storage results in API responses:
- `saved`: New bets created
- `updated`: Existing bets updated
- `failed`: Bets that failed validation
- `errors`: List of error messages

## Best Practices

1. **Always use store_data=true** when fetching best bets
2. **Check storage results** in API responses
3. **Monitor error logs** for validation issues
4. **Use selection_id** for tracking individual bets
5. **Leverage filters** when retrieving stored bets
6. **Update game scores** after games complete
