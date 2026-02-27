# Work Plan: Even Odds & Low Edge Player Props Sheet

This plan outlines the steps to create a fully automated Google Sheet that imports player prop data, filters for specific criteria ("even odds" or "edge < 30%"), and presents it in a clean, user-friendly format.

## Phase 1: Setup & Data Ingestion

- [ ] **Task 1: Create Google Apps Script for Data Fetching.**
  - Create a new Google Apps Script file associated with the target Google Sheet.
  - Write a function to read API credentials from the `backend/.env` file, ignoring the duplicate `THE_ODDS_API_KEY`.
  - Implement a function using `UrlFetchApp` to call the specified sports data API.
  - Add robust error handling to log any API connection or data parsing failures.

- [ ] **Task 2: Implement Data Parsing and Sheet Writing.**
  - In the Apps Script, parse the raw data from the API (assuming JSON or CSV).
  - Clear the `RawData` sheet of any existing content.
  - Write the new, complete dataset to the `RawData` sheet.

- [ ] **Task 3: Set Up Automated Trigger.**
  - Configure a time-driven trigger in the Google Apps Script project to run the data import function once every 24 hours.

## Phase 2: Data Filtering & Presentation

- [ ] **Task 4: Create Filtered View with QUERY.**
  - In the `HighValueProps` sheet, create a `QUERY` formula in cell A1.
  - The query should reference the `RawData` sheet.
  - It must filter for rows that meet the criteria: "even odds" (e.g., American odds between -110 and +110) OR "Edge %" < 0.30.
  - The query should select and arrange the most important columns for display.

- [ ] **Task 5: Apply Conditional Formatting.**
  - Apply conditional formatting rules to the `Edge %` and `Odds` columns in the `HighValueProps` sheet to visually highlight the most promising bets.

- [ ] **Task 6: Protect Sheets.**
  - Protect the `RawData` and `HighValueProps` sheets to prevent accidental manual edits, ensuring data integrity.

## Phase 3: Documentation

- [ ] **Task 7: Update AGENTS.md.**
  - Review the existing `AGENTS.md` file.
  - Add a new section describing the purpose and function of the new "Even Odds" sheet.
  - Clarify any instructions for agents related to data exports or analysis to prevent future confusion.
