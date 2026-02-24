# Track Specification: Historical Backfill and Qdrant Situational Analysis

## Objective
The primary objective of this track is to ingest extensive historical sports data (NBA and NCAAB) into PostgreSQL and integrate the Qdrant vector database. This will enable the platform to perform situational similarity analysis—identifying historical games with similar betting signals, market moves, and qualitative context—and provide RAG (Retrieval-Augmented Generation) capabilities for the intelligence agents.

## Scope

### 1. Historical Data Ingestion
- **NBA Backfill:** Utilize `nba_api` to pull the last 3 seasons of games, including scores and closing lines.
- **NCAAB Backfill:** Implement a crawler/scraper to ingest historical NCAAB scores and odds (where available).
- **Data Standardization:** Map historical data into the existing `games` and `bets` PostgreSQL schema.

### 2. Qdrant Infrastructure
- **Setup:** Deploy Qdrant via Docker Compose.
- **Service Integration:** Implement a `VectorStoreService` to manage embeddings and collection management.
- **Schema Design:** Define the vector payload schema for "Game Profiles" (combining quantitative stats and qualitative sentiment).

### 3. Situational Similarity Analysis
- **Embedding Generation:** Implement logic to vectorize game scenarios using relevant features (e.g., [Spread, Total, RLM Direction, Public Splits, Rest Days]).
- **Search Utility:** Create a utility to find the Top-K most similar historical games for any given live slate entry.

### 4. Agent Integration (RAG)
- **ExpertAgent Enhancement:** Update the `ExpertAgent` to query Qdrant for "Similar Historical Scenarios" when performing its sequential thinking process.
- **Contextual Prompting:** Inject historical outcomes of similar situations into LLM prompts to improve qualitative decision-making.

## Success Criteria
- [ ] PostgreSQL contains at least 2 seasons of historical NBA and NCAAB data.
- [ ] Qdrant is successfully running and accessible via the backend.
- [ ] A similarity search for a live game returns relevant historical "analog" games.
- [ ] The `ExpertAgent` provides context like: "Historically, in 8 similar situations with these public splits and RLM, the underdog covered 65% of the time."

## Technical Constraints
- Must use `Crawl4AI` or `Playwright` for any new scraping logic.
- Embeddings should be generated using a lightweight model (e.g., `sentence-transformers` as already used in project).
- Must adhere to the existing `loguru` and `Pydantic` conventions.
