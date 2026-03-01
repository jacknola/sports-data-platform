# Work Plan: Fix Player Prop Pagination & Limits

**Objective**: Increase the player prop limit to 100 maximum, distributed dynamically per team based on the number of games on the slate.

---

## Phase 1: Backend Dynamic Limits

### Task 1.1: Implement Dynamic "Props Per Team" Limit
- **File**: `backend/app/routers/props.py`
- **Goal**: Allow up to 100 total high-value props, distributed dynamically per team based on the slate size.
- **Actions**:
  1. In `run_prop_analysis`, calculate the number of unique teams playing on the slate (e.g., extract unique `team` or `opponent` names from `raw_props`).
  2. Calculate `limit_per_team = max(1, 100 // num_unique_teams)`.
  3. Initialize a dictionary `team_counts = collections.defaultdict(int)`.
  4. Iterate through the analyzed `best_props` (which are sorted by edge) and append them to a new list *only* if `team_counts[prop['team']] < limit_per_team`.
  5. Stop when the new list reaches 100 props total.
  6. Return this dynamically balanced list in the response dict instead of `best[:30]`.

### Task 1.2: Increase Default Endpoint Limits
- **File**: `backend/app/routers/props.py`
- **Goal**: Increase the default return size for the `/best` props endpoint.
- **Actions**:
  1. Locate the `GET /props/{sport}/best` route.
  2. Change `limit: int = Query(default=10, ...)` to `default=100`.

### Task 1.3: Remove Hard Caps in NBA Stats Service
- **File**: `backend/app/services/nba_stats_service.py`
- **Goal**: Ensure the data enrichment step doesn't artificially choke the expanded limit.
- **Actions**:
  1. Review the `get_player_prop_research` method or anywhere a `[:30]` slice occurs.
  2. If there is a hardcoded list slice to avoid API rate limits, increase it to 100 but ensure batching or `asyncio.gather` is used so it doesn't timeout.

---

## Phase 2: Frontend Adjustments

### Task 2.1: Update Frontend Fetch Limits
- **Files**: Frontend components fetching props (e.g., `frontend/src/pages/CollegeBasketball.tsx`, etc.)
- **Goal**: Ensure the frontend UI requests the higher limit if it explicitly passes a `limit` parameter.
- **Actions**:
  1. Search for `api.get('/props/` in the frontend.
  2. Update any `params: { limit: 30 }` to `params: { limit: 100 }` (or remove the hardcoded limit entirely to use the new backend default).
