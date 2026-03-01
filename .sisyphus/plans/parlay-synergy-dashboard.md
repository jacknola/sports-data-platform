

# Work Plan: Parlay Synergy Dashboard

**Objective**: First, stabilize the existing Parlays page by fixing critical bugs. Second, build a new "synergy search" feature that suggests correlated parlay legs by analyzing historical player prop data. Finally, integrate this feature into an enhanced, light-themed frontend dashboard.

---

## Phase 0: Fix the Foundation (Prerequisites)

*Metis analysis revealed critical bugs that must be fixed before adding new features. This phase addresses that technical debt.*

### Task 0.1: Fix Frontend API Routing
- **Files**: `frontend/src/pages/Parlays.tsx`, `frontend/src/utils/api.ts`
- **Goal**: Correct all API calls to use the required `/api/v1` prefix.
- **Actions**:
    1.  Use `ast_grep_search` with patterns like `api.get('/parlays` to find all incorrect calls.
    2.  Prepend `/api/v1` to every parlay-related API call (e.g., `/parlays` becomes `/api/v1/parlays`).
- **QA & Verification**:
    ```bash
    # Verify backend parlay endpoints respond correctly
    curl -s http://localhost:8000/api/v1/parlays | python -c "import sys, json; assert isinstance(json.load(sys.stdin), list)"
    curl -s http://localhost:8000/api/v1/parlays/stats/performance | python -c "import sys, json; assert 'total_parlays' in json.load(sys.stdin)"
    ```

### Task 0.2: Fix Backend Router Double Prefix
- **File**: `backend/app/routers/historical.py`
- **Goal**: Correct the malformed API route `/api/v1/api/historical`.
- **Actions**:
    1. In `historical.py`, remove the `prefix="/api/historical"` argument from the `APIRouter` initialization. The prefix is already correctly applied in `main.py`.
- **QA & Verification**:
    ```bash
    # Verify the historical endpoint responds on the correct URL
    curl -s http://localhost:8000/api/v1/historical/player_props | python -c "import sys, json; assert isinstance(json.load(sys.stdin), list)"
    ```

### Task 0.3: Align Frontend Types with Backend API
- **File**: `frontend/src/types/api.ts`
- **Goal**: Correct the `ParlayStats` TypeScript type to match the actual data returned by the backend.
- **Actions**:
    1.  Rename `total_roi` to `overall_roi`.
    2.  Rename `total_profit_loss` to `net_profit`.
    3.  Confirm with the backend team if `pending` and `partial` counts can be added to the API. If not, remove them from the frontend type to prevent runtime errors.
- **QA & Verification**:
    ```bash
    # Verify frontend builds without TypeScript errors
    cd frontend && npm run build
    npx tsc --noEmit
    ```
---

## Phase 1: Backend - Historical Correlation Service

*Build the service that powers the synergy search by mining the `historical_player_props` table.*

### Task 1.1: Create Correlation Service
- **File**: `backend/app/services/correlation_service.py` (new file)
- **Goal**: Create a service to find combinations of player props that have historically hit together in the same game.
- **Actions**:
    1.  Create a `CorrelationService` class.
    2.  Implement a `find_correlated_props` method. This method will take a list of base props (e.g., "LeBron James points > 25.5") as input.
    3.  The core logic will be a SQL query (using SQLAlchemy) that:
        - Self-joins the `historical_player_props` table on `game_date` and `opponent`.
        - Filters for games where the input props were successful (e.g., `actual > line`).
        - Aggregates and counts other props that also succeeded in those same games.
        - Returns a list of props with the highest co-occurrence rate.
- **QA & Verification**:
    - Add a unit test in `backend/tests/services/test_correlation_service.py` that seeds the test database with historical data and asserts that the service returns the expected correlated props.

### Task 1.2: Add Correlation API Endpoint
- **File**: `backend/app/routers/parlays.py`
- **Goal**: Expose the new correlation service via a public API endpoint.
- **Actions**:
    1.  Inject the `CorrelationService` into the router.
    2.  Create Pydantic models for the request and response.
    3.  Add a new endpoint: `POST /api/v1/parlays/search/correlations`.
- **QA & Verification**:
    ```bash
    # Verify synergy search endpoint exists and responds correctly
    curl -s -X POST http://localhost:8000/api/v1/parlays/search/correlations \
      -H "Content-Type: application/json" \
      -d '{"legs": [{"player_name": "LeBron James", "prop_type": "points", "line": 25.5}]}' \
      | python -c "import sys, json; assert 'suggestions' in json.load(sys.stdin)"
    ```
---

## Phase 2: Frontend - Enhanced Dashboard

*Fix the existing UI, apply a consistent light theme, and build the interface for the new correlation search.*

### Task 2.1: Fix and Refactor Parlays Page
- **File**: `frontend/src/pages/Parlays.tsx`
- **Goal**: Apply the API routing fixes from Phase 0 and refactor the page to be a clean, functional host for the dashboard components.
- **Actions**:
    1.  Ensure all `api.get` and `api.post` calls are correct.
    2.  Refactor the styling to use the light theme (e.g., use the standard `.card` class) for consistency with the rest of the application.
- **QA & Verification**:
    - The Parlays page should now load and display data correctly.

### Task 2.2: Build Correlation Search UI
- **File**: `frontend/src/pages/parlays/components/CorrelationSearch.tsx` (new file)
- **Goal**: Create a UI for users to input props and see suggested correlated props.
- **Actions**:
    1.  Create a form where a user can add one or more player props.
    2.  On submit, use `useMutation` from React Query to call the `POST /api/v1/parlays/search/correlations` endpoint.
    3.  Display the returned `suggestions` in a clear, readable table.
- **QA & Verification**:
    - The search UI correctly calls the backend and displays the results.

### Task 2.3: Assemble the New Dashboard
- **File**: `frontend/src/pages/Parlays.tsx`
- **Goal**: Integrate the new `CorrelationSearch` component into the main Parlays page.
- **Actions**:
    1.  Structure the page with the `CorrelationSearch` component prominently displayed.
    2.  The existing parlay list can be used to show parlays that contain the selected correlated props.
- **QA & Verification**:
    ```bash
    # Verify frontend builds and passes linting
    cd frontend && npm run build && npm run lint
    ```
---

## Final Verification Wave

- **V1**: All Phase 0 fixes are applied and verified with `curl`.
- **V2**: The new backend correlation service has unit tests that pass.
- **V3**: The new frontend search component successfully fetches and displays data from the new backend endpoint.
- **V4**: The final Parlays page is styled consistently with the light theme and is fully functional.

---

## Phase 3: Update Project Intelligence Context

*Document the new architecture decisions and critical bug patterns discovered during this session so future AI agents have accurate context.*

### Task 3.1: Create Parlay RAG Pipeline Concept File
- **File**: `.opencode/context/project-intelligence/concepts/parlay-rag-pipeline.md` (new file)
- **Goal**: Document the parlay/RAG/synergy architecture, critical bugs, and decisions for future agents.
- **Frontmatter**: `<!-- Context: project-intelligence/concepts/parlay-rag-pipeline | Priority: high | Version: 1.0 | Updated: {today} -->`
- **Content to include**:
    1. Architecture overview: RAG (text-similarity) vs Synergy Search (SQL co-occurrence) — two distinct systems.
    2. Key services/files table: `rag_pipeline.py`, `parlays.py`, planned `correlation_service.py`, `Parlays.tsx`.
    3. Synergy search architecture decision: Use `historical_player_props` SQL JOINs (NOT in-memory embeddings, NOT Qdrant for MVP).
    4. **Bug 1**: Frontend API routing — all parlay API calls must use `/api/v1/parlays` prefix, NOT `/parlays`.
    5. **Bug 2**: Router double-prefix in `historical.py` — do NOT set `prefix` in the router if `main.py` already adds it.
    6. **Bug 3**: `ParlayStats` type mismatch — frontend type must use `overall_roi` (not `total_roi`), `net_profit` (not `total_profit_loss`), and `win_rate` is a percentage (60.0), not decimal (0.6).
    7. UI standards: Light theme (`.card` class), follow `CollegeBasketball.tsx` layout pattern.
    8. Out-of-scope: parlay creation UI, Twitter posting, real-time odds, parlay builder.
    9. Codebase references section linking to all key files.
- **MVI Compliance**: Keep under 200 lines, scannable in <30 seconds.
- **QA & Verification**:
    ```bash
    # Verify file exists and is under 200 lines
    wc -l .opencode/context/project-intelligence/concepts/parlay-rag-pipeline.md
    # Verify frontmatter is present
    head -1 .opencode/context/project-intelligence/concepts/parlay-rag-pipeline.md | grep 'Context:'
    ```

### Task 3.2: Update navigation.md
- **File**: `.opencode/context/project-intelligence/navigation.md`
- **Goal**: Add the new `parlay-rag-pipeline.md` concept file to the navigation index.
- **Actions**:
    1. Add a new row to the concepts table: `concepts/parlay-rag-pipeline.md` | Parlay RAG, synergy search, critical bugs | high
    2. Increment the version in the frontmatter (1.1 → 1.2).
    3. Update the `Updated` date to today.
- **QA & Verification**:
    ```bash
    # Verify navigation.md contains the new entry
    grep 'parlay-rag-pipeline' .opencode/context/project-intelligence/navigation.md
    ```

### Task 3.3: Update technical-domain.md with New Anti-Patterns
- **File**: `.opencode/context/project-intelligence/technical-domain.md`
- **Goal**: Add a brief anti-patterns section documenting the critical bugs found by Metis.
- **Actions**:
    1. Add a `## Anti-Patterns Discovered` section (or append to existing anti-patterns if present).
    2. Include the three parlay bugs as concise rules (one-liners preferred).
    3. Increment version (1.0 → 1.1) and update date in frontmatter.
- **Content to add**:
    ```markdown
    - **API Prefix**: Frontend API calls MUST use `/api/v1/` prefix — Vite proxy requires it. `/parlays` will 404.
    - **Router Prefix**: Do NOT set `prefix=` in an APIRouter if `main.py` already adds the prefix — causes double routes.
    - **Type Drift**: Validate frontend TypeScript types against actual backend responses before building on them.
    ```
- **MVI Compliance**: File must stay under 200 lines after update.
- **QA & Verification**:
    ```bash
    wc -l .opencode/context/project-intelligence/technical-domain.md
    grep 'API Prefix' .opencode/context/project-intelligence/technical-domain.md
    ```
