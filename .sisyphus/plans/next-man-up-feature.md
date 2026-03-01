# Work Plan: "Next Man Up" (Injury Replacement) Feature

**Objective**: Detect when a starter is injured and automatically highlight the bench player who is projected to replace them and see increased usage.

---

## Phase 1: Backend Data Integration

### Task 1.1: Fetch ESPN Depth Charts
- **File**: `backend/app/services/nba_stats_service.py`
- **Goal**: Fetch team depth charts to understand positional hierarchies.
- **Actions**:
  1. Add a method `get_team_depth_chart(team_abbr: str)`.
  2. Map the team abbreviation to the ESPN Team ID.
  3. Call `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{teamId}/depthchart`.
  4. Parse the JSON to create a mapping: `{ "PG": ["D. Russell", "G. Vincent"], "SF": ["L. James", "T. Prince"] }`.
  5. Cache this data (depth charts don't change frequently during the day).

### Task 1.2: Fetch Daily Starting Lineups
- **File**: `backend/app/services/nba_stats_service.py`
- **Goal**: Get the confirmed or projected starting 5 for today's games.
- **Actions**:
  1. Add a method `get_daily_lineups(date_str: str)`.
  2. Call `https://stats.nba.com/js/data/leaders/00_daily_lineups_{date_str}.json` (add standard headers like User-Agent to avoid blocks).
  3. Parse the JSON to return a list of starting players for each team.

### Task 1.3: "Next Man Up" Logic in Prop Analyzer
- **File**: `backend/app/services/prop_analyzer.py`
- **Goal**: Identify props belonging to backup players stepping into a starting role due to injury.
- **Actions**:
  1. In `run_prop_analysis()`, after fetching `injuries`, fetch the `depth_charts` and `lineups`.
  2. Create a detection loop: For each player marked `OUT` or `QUESTIONABLE` in the injury report, look up their position on the depth chart.
  3. Identify the #2 player on the depth chart for that position.
  4. Check if that #2 player is listed in the `lineups` as a starter today.
  5. If yes, tag any props for that #2 player with a new flag: `is_injury_replacement = True` and add a note to the analysis (e.g., "Starting in place of injured LeBron James").

---

## Phase 2: Frontend Highlighting

### Task 2.1: Highlight Replacement Props in UI
- **Files**: `frontend/src/components/PropCard.tsx` (or similar prop display component)
- **Goal**: Visually alert the user that this prop is for a bench player replacing a starter.
- **Actions**:
  1. Add `is_injury_replacement` to the `PlayerProp` TypeScript interface.
  2. In the UI component, check if `prop.is_injury_replacement` is true.
  3. If true, add a prominent badge (e.g., 🚨 **Injury Replacement: High Value**) and highlight the row/card to draw attention to the potential usage bump.