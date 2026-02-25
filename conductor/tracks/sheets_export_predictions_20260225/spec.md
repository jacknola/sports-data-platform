## Specification: Improve Sheet Export & Ensure Model Predictions

### 1.0 Overview

This track addresses the current issues with Google Sheet exports, specifically the lack of consistent model predictions and poor formatting. The goal is to ensure that model predictions, including Moneyline (ML), Spread, and Player Prop predictions, are always exported to the Google Sheet in a clear, well-formatted manner, prioritizing the use of historical data for predictions even when live odds API access is limited.

### 2.0 Functional Requirements

*   **2.1 Persistent Model Predictions:** The Google Sheet export process MUST always generate and display model predictions (ML, Spread, Player Props) for all identified games, regardless of the status of live odds API access.
*   **2.2 Dedicated ML Predictions Tab:** A dedicated "ML Predictions" tab MUST be created and updated to display raw model outputs (Matchup, Winner Prob %, Fair Odds, Proj Total, Proj Spread, and underlying features like Offensive/Defensive Ratings, Pace, Win %).
*   **2.3 Enhanced Sheet Formatting:** The exported data across all relevant tabs (NBA, NCAAB, ML Predictions) MUST adhere to a clean, readable table format. This includes:
    *   Clear column headers.
    *   Consistent data types and formatting within columns (e.g., percentages, odds values).
    *   Appropriate column order for easy readability (e.g., Team1, Team2, ML_Odds, Spread_Line, Total_Line, Model_Prediction).
*   **2.4 Historical Data Integration:** The prediction pipeline MUST always leverage available historical data from the database to generate predictions, even if live odds are not available. This includes using historical data to calculate probabilities for ML, Spread, and Player Prop markets.

### 3.0 Non-Functional Requirements

*   **3.1 Robustness:** The system should gracefully handle exhausted odds API tiers by falling back to historical data and available scraped information for predictions.
*   **3.1 Performance:** The export process should remain efficient, completing within acceptable timeframes.

### 4.0 Acceptance Criteria

*   **4.1:** Upon running the `export_to_sheets.py` script, the "ML Predictions" tab in the Google Sheet (`1Ape6MIzwQeJEBApRyyXjz9YSrZYyBWV2S6xP__IpWs0`) contains a correctly formatted table with:
    *   "Date", "Away", "Home", "Winner", "Winner Prob %", "Fair Odds", "Proj Total", "Proj Spread".
    *   All predictions for tomorrow's NBA games are present.
*   **4.2:** The "NBA" tab in the Google Sheet displays comprehensive predictions, including ML, Spread, and Player Prop predictions, leveraging all available data.
*   **4.3:** The "NCAAB" tab in the Google Sheet displays comprehensive predictions, including ML and Spread predictions, leveraging all available data.
*   **4.4:** The formatting across "NBA", "NCAAB", and "ML Predictions" tabs is clean, with appropriate headers, column order, and data presentation.
*   **4.5:** The predictive models (ML, Spread, Player Prop) successfully use historical data to generate predictions, even if live odds API access is exhausted for `the-odds-api.com` or `odds-api.io`.

### 5.0 Out of Scope

*   Acquiring new paid API subscriptions for live odds.
*   Implementing new predictive models beyond the existing XGBoost models.
*   Major refactoring of existing data models or database schemas (unless strictly necessary for this feature).