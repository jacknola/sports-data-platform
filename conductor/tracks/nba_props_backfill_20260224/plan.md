# Implementation Plan - NBA Player Props Historical Backfill and Sheets Export

This plan outlines the steps to ingest historical player stats, implement situational search for props, and export results to Google Sheets.

## Phase 1: Player Game Log Backfill

### Goal: Ingest multi-season player stats into PostgreSQL.

- [ ] **Task 1: Define Player Game Log Schema**
    - [ ] Create or update SQLAlchemy models for player game logs.
    - [ ] Run migrations if necessary.
- [ ] **Task 2: Ingestion Script Implementation**
    - [ ] Write unit tests for player log ingestion.
    - [ ] Implement `NBAPlayerBackfillService` to pull logs via `nba_api`.
- [ ] **Task 3: Conductor - User Manual Verification 'Phase 1: Player Game Log Backfill' (Protocol in workflow.md)**

## Phase 2: Player-Centric Situational Analysis

### Goal: Vectorize player performances for RAG-enhanced prop analysis.

- [ ] **Task 1: Player Performance Profiler**
    - [ ] Implement `PlayerProfiler` to vectorize game logs (Scenario + Outcome).
    - [ ] Write tests for player situational embeddings.
- [ ] **Task 2: Bulk Vectorization Script**
    - [ ] Implement script to vectorize all historical player logs into a new Qdrant collection `player_performances`.
- [ ] **Task 3: Conductor - User Manual Verification 'Phase 2: Player-Centric Situational Analysis' (Protocol in workflow.md)**

## Phase 3: Sheets Export & Automation

### Goal: Automate the RAG-enhanced prop export to Google Sheets.

- [ ] **Task 1: Enhance Sheets Service**
    - [ ] Update `GoogleSheetsService` to include situational context in the 'Props' tab.
    - [ ] Write unit tests for the updated export logic.
- [ ] **Task 2: Prop Analysis Runner**
    - [ ] Create a script to run the full RAG-enhanced prop analysis for today's slate and export to Sheets.
- [ ] **Task 3: Conductor - User Manual Verification 'Phase 3: Sheets Export & Automation' (Protocol in workflow.md)**
