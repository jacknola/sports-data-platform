## Implementation Plan: Improve Sheet Export & Ensure Model Predictions

### Phase 1: Enhance Model Prediction Robustness & Output Formatting

This phase focuses on ensuring that model predictions are always generated and correctly formatted for export, regardless of live odds API availability.

- [x] Task: Update NBAMLPredictor to ensure robust data output [f830795]
    - [ ] Analyze `backend/app/services/nba_ml_predictor.py` for potential data type or formatting inconsistencies before output.
    - [ ] Implement explicit type casting (e.g., to standard Python floats) for all numerical model outputs to prevent JSON serialization errors during export.
    - [ ] Ensure all relevant prediction data (ML, Spread, Totals, Features) is consistently structured in the output of `predict_today_games`.
- [x] Task: Implement graceful degradation for Odds API in NBAMLPredictor [16072e9]
    - [ ] Modify `backend/app/services/nba_ml_predictor.py`'s `predict_today_games` to explicitly check for `odds_data` availability.
    - [ ] If `odds_data` is unavailable or empty from primary API, ensure fallback to `scrape_action_network` for game discovery and populate with default/estimated odds for prediction.
    - [ ] Ensure the `features` dictionary is fully populated with sensible defaults when actual API odds are missing, to avoid model input errors.
- [x] Task: Create new 'ML Predictions' tab in Google Sheets [fccbc49]
    - [ ] Define the `headers` for the 'ML Predictions' tab based on `spec.md`'s Acceptance Criteria 4.1.
    - [ ] Implement `export_ml_predictions` method in `backend/app/services/google_sheets.py` to write the raw model outputs (Matchup, Winner Prob %, Fair Odds, Proj Total, Proj Spread, Features) to this new tab.
    - [ ] Ensure `export_daily_picks` calls `export_ml_predictions` with the relevant data.
- [ ] Task: Conductor - User Manual Verification 'Enhance Model Prediction Robustness & Output Formatting' (Protocol in workflow.md)

### Phase 2: Improve Existing Tab Formatting and Data Completeness

This phase focuses on refining the formatting and ensuring comprehensive data display in the existing 'NBA' and 'NCAAB' tabs.

- [ ] Task: Review and update 'NBA' tab formatting
    - [ ] Modify `backend/app/services/google_sheets.py`'s `export_nba` method to align column headers and data order with the desired clean format specified in Acceptance Criteria 2.3.
    - [ ] Ensure ML, Spread, and Player Prop predictions are clearly visible and correctly mapped from the `nba_predictions` data.
    - [ ] Verify that relevant historical context (if available) is included.
- [ ] Task: Review and update 'NCAAB' tab formatting
    - [ ] Modify `backend/app/services/google_sheets.py`'s `export_ncaab` method to align column headers and data order with the desired clean format.
    - [ ] Ensure ML and Spread predictions are clearly visible and correctly mapped from the `ncaab_data`.
    - [ ] Verify that relevant historical context (if available) is included.
- [ ] Task: Conductor - User Manual Verification 'Improve Existing Tab Formatting and Data Completeness' (Protocol in workflow.md)

### Phase 3: Player Prop Prediction Integration

This phase ensures player prop predictions are consistently generated and exported when available.

- [ ] Task: Ensure Player Prop predictions are generated and passed to export
    - [ ] Verify that `_run_props` in `backend/export_to_sheets.py` correctly fetches player prop data and that `run_prop_analysis` is robust to API failures.
    - [ ] Ensure player prop data is included in `nba_predictions` or a separate structure for `export_nba` and potentially the new `ML Predictions` tab.
- [ ] Task: Update Google Sheets export for Player Props
    - [ ] Modify `backend/app/services/google_sheets.py`'s `export_nba` or `export_ml_predictions` (or create a new dedicated `export_props_ml` method) to include player prop predictions alongside ML and Spread data.
    - [ ] Define appropriate formatting and headers for player prop data within the target tab(s).
- [ ] Task: Conductor - User Manual Verification 'Player Prop Prediction Integration' (Protocol in workflow.md)