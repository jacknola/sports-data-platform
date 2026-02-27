# Draft Plan: High-Odds Player Props Sheet

## Objective
Create a Google Sheet to automatically ingest and filter player prop betting data, displaying only props with odds of +300 or higher.

## Key Decisions & Requirements
*   **Data Source**: User-provided API (details pending).
*   **Update Frequency**: Daily, via automated Google Apps Script trigger.
*   **Sheet Structure**:
    *   `RawData`: Hidden sheet for all incoming data from the API.
    *   `HighOddsProps`: Protected, user-facing sheet displaying filtered results.
    *   Confirmed with user: Yes.
*   **Filtering Logic**:
    *   Primary: Use a `QUERY` formula to select rows where `Odds >= 300`.
    *   Secondary: Sort results by `Edge %` in descending order.
*   **Advanced Features**:
    *   Conditional formatting to highlight high-edge props.
    *   Email Alerts: Deferred based on user feedback.
*   **Secondary Objective**:
    *   Review and update `AGENTS.md` to improve agent guidance.

