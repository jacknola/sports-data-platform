# Implementation Plan - NBA Player Props Historical Backfill and Sheets Export

This plan outlines the steps to ingest historical player stats, implement situational search for props, and export results to Google Sheets.

## Phase 1: Player Game Log Backfill [checkpoint: 3a2c838]

### Goal: Ingest multi-season player stats into PostgreSQL.

- [x] **Task 1: Define Player Game Log Schema** 103f211
    - [x] Create or update SQLAlchemy models for player game logs.
    - [x] Run migrations if necessary.
- [x] **Task 2: Ingestion Script Implementation** 931a035
    - [x] Write unit tests for player log ingestion.
    - [x] Implement `NBAPlayerBackfillService` to pull logs via `nba_api`.
- [x] **Task 3: Conductor - User Manual Verification 'Phase 1: Player Game Log Backfill' (Protocol in workflow.md)**

## Phase 2: Player-Centric Situational Analysis [checkpoint: 0f9cadf]

### Goal: Vectorize player performances for RAG-enhanced prop analysis.

- [x] **Task 1: Player Performance Profiler** d225537
    - [x] Implement `PlayerProfiler` to vectorize game logs (Scenario + Outcome).
    - [x] Write tests for player situational embeddings.
- [x] **Task 2: Bulk Vectorization Script** 2d3a8c7
    - [x] Implement script to vectorize all historical player logs into a new Qdrant collection `player_performances`.
- [x] **Task 3: Conductor - User Manual Verification 'Phase 2: Player-Centric Situational Analysis' (Protocol in workflow.md)**

## Phase 3: Sheets Export & Automation

### Goal: Automate the RAG-enhanced prop export to Google Sheets.

- [x] **Task 1: Enhance Sheets Service** c1fdebf
    - [x] Update `GoogleSheetsService` to include situational context in the 'Props' tab.
    - [x] Write unit tests for the updated export logic.
- [x] **Task 2: Prop Analysis Runner** b4db9f4
    - [x] Create a script to run the full RAG-enhanced prop analysis for today's slate and export to Sheets.
- [~] **Task 3: Conductor - User Manual Verification 'Phase 3: Sheets Export & Automation' (Protocol in workflow.md)**
