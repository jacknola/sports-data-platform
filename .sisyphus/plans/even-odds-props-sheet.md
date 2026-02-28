# Work Plan: High Value Player Props Dashboard

This plan outlines the steps to upgrade the existing Google Sheets export functionality to create a beautifully formatted, filtered dashboard for player props, specifically targeting "even odds" or "edge < 30%".

## Phase 1: Backend Logic Update

- [ ] **Task 1: Implement Filtering Logic in Python.**
  - Modify `backend/app/services/google_sheets.py` (specifically the `export_props` method or create a new method `export_high_value_props`).
  - Add logic to filter the `prop_data` for:
    - Even odds (e.g., American odds between -110 and +110).
    - OR Edge < 30% (0.30).
  - Ensure the data is sorted logically (e.g., by Edge descending).

## Phase 2: Sheet Formatting & Presentation

- [ ] **Task 2: Enhance gspread Formatting.**
  - Update the Python code to apply advanced formatting to the new sheet using `gspread`'s `format` method or batch update API.
  - Set appropriate column widths for readability.
  - Apply a clean color scheme to the header row (e.g., dark background, white text).
  - Format percentage columns (Edge %, Kelly %) as actual percentages.

- [ ] **Task 3: Apply Conditional Formatting.**
  - Use the Google Sheets API (via `gspread`) to add conditional formatting rules to the sheet.
  - Highlight the "Edge %" column (e.g., green for higher edges).
  - Highlight the "Confidence" column based on text value (High = Green, Medium = Yellow, etc.).

## Phase 3: Integration & Testing

- [ ] **Task 4: Update Export Runner.**
  - Ensure the main export script (`backend/run_prop_export.py` or similar) calls the new/updated export method.
  - Run the export script to verify the new sheet is created and formatted correctly.

- [ ] **Task 5: Update AGENTS.md.**
  - Document the new sheet structure and filtering logic in `AGENTS.md` for future reference.
