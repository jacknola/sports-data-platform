# Track Specification: NBA Player Props Historical Backfill and Sheets Export

## Objective
The primary goal of this track is to create a robust historical foundation for NBA player prop analysis and automate the export of these RAG-enhanced predictions to Google Sheets. This includes backfilling several seasons of player game logs, vectorizing situational "player performance profiles" in Qdrant, and updating the reporting layer.

## Scope

### 1. Player Stats Historical Backfill
- **Game Logs Ingestion:** Implement a bulk ingestion utility using `nba_api` to pull player game logs for the last 2-3 seasons.
- **PostgreSQL Schema:** Ensure `players` and a new `player_game_logs` table (or similar) are optimized for historical queries.
- **Stat Coverage:** Points, Rebounds, Assists, Threes, Blocks, Steals, and combined stats (PRA).

### 2. Player-Centric Situational Analysis (Qdrant)
- **Player Profiling:** Implement logic to vectorize player performances in specific situations (e.g., "LeBron vs high-pace teams on 0 days rest").
- **Similarity Search:** Enable searching for "Similar Situations" for a specific player when evaluating a live prop line.

### 3. Google Sheets Export Enhancement
- **Prop Integration:** Enhance `GoogleSheetsService.export_props` to include deep situational context (e.g., "Analog Similarity Outcome: 70% Over").
- **Automated Slate Export:** Create a runner script that performs the full prop analysis for today's NBA slate and exports it to the configured Google Sheet.

## Success Criteria
- [ ] PostgreSQL contains comprehensive player game logs for the last 2 seasons.
- [ ] Qdrant contains situational embeddings for top 100 NBA players.
- [ ] Google Sheets 'Props' tab is automatically populated with daily prop predictions, including edge, confidence, and RAG context.

## Technical Constraints
- Must adhere to `nba_api` rate limits (~1 request per second).
- Must use existing `loguru` and `Pydantic` conventions.
- Sheets export requires a valid `GOOGLE_SERVICE_ACCOUNT_PATH` and `GOOGLE_SPREADSHEET_ID`.
