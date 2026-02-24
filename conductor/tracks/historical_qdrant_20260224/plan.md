# Implementation Plan - Historical Backfill and Qdrant Situational Analysis

This plan outlines the steps to ingest historical data and implement vector-based situational analysis.

## Phase 1: PostgreSQL Historical Backfill [checkpoint: e72b285]

### Goal: Populate the relational database with multi-season historical data.

- [x] **Task 1: NBA API Backfill Script** 8199c87
    - [ ] Write unit tests for NBA historical ingestion.
    - [ ] Implement script to pull and save last 3 seasons of NBA data.
- [x] **Task 2: NCAAB Historical Scraper** 8e99f99
    - [ ] Write tests for historical NCAAB scraping logic.
    - [ ] Implement scraper for historical college basketball odds and scores.
- [x] **Task 3: Conductor - User Manual Verification 'Phase 1: PostgreSQL Historical Backfill' (Protocol in workflow.md)**

## Phase 2: Qdrant Infrastructure & Vector Store Service [checkpoint: 6cddeec]

### Goal: Integrate Qdrant and implement the core vector management logic.

- [x] **Task 1: Infrastructure Setup** 1dac9e6
    - [ ] Add Qdrant to `docker-compose.yml`.
    - [ ] Verify connection and collection initialization.
- [x] **Task 2: VectorStoreService Implementation** 6fa4d58
    - [ ] Write tests for `VectorStoreService` (insert, search, delete).
    - [ ] Implement service to handle embeddings and Qdrant queries.
- [x] **Task 3: Conductor - User Manual Verification 'Phase 2: Qdrant Infrastructure & Vector Store Service' (Protocol in workflow.md)**

## Phase 3: Game Profile Vectorization & Similarity Search

### Goal: Enable searching for similar historical game scenarios.

- [ ] **Task 1: Scenario Vectorization Logic**
    - [ ] Define the feature vector for a "Game Profile".
    - [ ] Write tests for embedding generation.
    - [ ] Implement script to vectorize all historical games into Qdrant.
- [ ] **Task 2: Similarity Search Utility**
    - [ ] Write tests for the similarity search interface.
    - [ ] Implement utility to find similar games for a given slate entry.
- [ ] **Task 3: Conductor - User Manual Verification 'Phase 3: Game Profile Vectorization & Similarity Search' (Protocol in workflow.md)**

## Phase 4: Agent Integration (RAG)

### Goal: Enhance Agent reasoning with retrieved historical context.

- [ ] **Task 1: ExpertAgent RAG Enhancement**
    - [ ] Update `ExpertAgent` to perform a similarity search during analysis.
    - [ ] Update prompts to incorporate retrieved historical results.
- [ ] **Task 2: Comprehensive End-to-End Validation**
    - [ ] Run a full analysis on a live game and verify the presence of historical situational context.
- [ ] **Task 3: Conductor - User Manual Verification 'Phase 4: Agent Integration (RAG)' (Protocol in workflow.md)**
