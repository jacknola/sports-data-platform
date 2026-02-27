# Fix NCAAB Google Sheets Export Bug

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the AttributeError crash in NCAAB analysis that prevents Google Sheets export from completing.

**Architecture:** Remove two phantom references to a never-implemented `SportsGameOdds` service in `run_ncaab_analysis.py`. The existing fallback logic (`estimate_public_splits` or 50/50 default) already handles the `public_data = None` case correctly — we just need to let it reach that path.

**Tech Stack:** Python (backend only), single file change.

---

## Context

The NCAAB export pipeline crashes with `AttributeError: 'SportsAPIService' object has no attribute 'sports_game_odds'` because `backend/run_ncaab_analysis.py` references a service class (`SportsGameOdds`) that was **never implemented**. The NBA pipeline does NOT have this problem.

Two identical crash sites exist:
- **Site 1**: Lines 400-402 (inside `get_live_ncaab_games()` helper)
- **Site 2**: Lines 500-502 (inside main analysis loop)

Both follow the same pattern:
```python
# Try to get real public percentages from SportsGameOdds
api = SportsAPIService()
public_data = await api.sports_game_odds.get_public_percentages(game_id)
```

The fallback logic on lines 404-415 and 504-515 already handles `public_data = None` correctly, routing to either `estimate_public_splits(spread_val)` or a 50/50 default.

## Scope Fence

**IN scope:**
- Remove 2 broken call sites in `backend/run_ncaab_analysis.py`
- Verify NCAAB analysis completes end-to-end

**OUT of scope (do NOT touch):**
- No changes to `SportsAPIService` in `sports_api.py`
- No new classes, services, or modules
- No changes to Google Sheets export logic
- No changes to `estimate_public_splits()` function
- No refactoring of duplicated code between the two blocks
- No changes to `ENABLE_SHARP_SIGNALS` default or env var logic
- No new tests (runtime verification only — no way to unit test without extensive API mocking)

---

### Task 1: Fix Crash Site 1 (lines 400-402)

**Files:**
- Modify: `backend/run_ncaab_analysis.py:400-402`

**Step 1: Replace the broken call with `public_data = None`**

Find these exact 3 lines (around line 400-402):
```python
                # Try to get real public percentages from SportsGameOdds
                api = SportsAPIService()
                public_data = await api.sports_game_odds.get_public_percentages(game_id)
```

Replace with these exact 2 lines (preserving the 16-space indentation):
```python
                # TODO: Wire up SportsGameOdds API when implemented
                public_data = None
```

**DO NOT** touch the `if public_data:` block below (lines 404-415) — it already handles `None` correctly.

**Step 2: Verify syntax**

Run: `cd backend && python -c "import run_ncaab_analysis; print('OK')"`
Expected: prints `OK`, exit code 0

---

### Task 2: Fix Crash Site 2 (lines 500-502)

**Files:**
- Modify: `backend/run_ncaab_analysis.py:500-502`

**Step 1: Replace the broken call with `public_data = None`**

Find these exact 3 lines (around line 500-502, note 12-space indentation this time):
```python
            # Try to get real public percentages from SportsGameOdds
            api = SportsAPIService()
            public_data = await api.sports_game_odds.get_public_percentages(game_id)
```

Replace with these exact 2 lines (preserving the 12-space indentation):
```python
            # TODO: Wire up SportsGameOdds API when implemented
            public_data = None
```

**DO NOT** touch the `if public_data:` block below (lines 504-515) — it already handles `None` correctly.

**Step 2: Verify syntax**

Run: `cd backend && python -c "import run_ncaab_analysis; print('OK')"`
Expected: prints `OK`, exit code 0

**Step 3: Commit**

```bash
git add backend/run_ncaab_analysis.py
git commit -m "fix: remove phantom SportsGameOdds references crashing NCAAB export"
```

---

### Task 3: Verify NCAAB Export Works End-to-End

**Step 1: Confirm phantom references are fully removed**

Run: `grep -n "sports_game_odds" backend/run_ncaab_analysis.py`
Expected: Zero matches (exit code 1)

**Step 2: Run full test suite (regression check)**

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: All tests pass (262 expected), exit code 0

**Step 3: Runtime smoke test — NCAAB analysis completes**

Run: `cd backend && source venv/bin/activate && timeout 120 python run_ncaab_analysis.py 2>&1 | tail -5`
Expected: Output reaches "Analysis complete" or similar completion message. NO `AttributeError` in output.

**Step 4: Runtime smoke test — Full Sheets export completes**

Run: `cd backend && source venv/bin/activate && python export_to_sheets.py 2>&1 | grep -iE "(NCAAB|export|complete|error|fail)" | tail -10`
Expected: NCAAB tab exports successfully (may show 0 games if no NCAAB games today, but should NOT crash).

---

## Final Verification Wave

Run all checks in sequence:

```bash
cd backend && source venv/bin/activate

# 1. No phantom references remain
grep -c "sports_game_odds" run_ncaab_analysis.py && echo "FAIL: references remain" || echo "PASS: all removed"

# 2. Module imports cleanly
python -c "import run_ncaab_analysis; print('PASS: imports OK')"

# 3. Test suite passes
python -m pytest tests/ -x -q

# 4. NCAAB analysis doesn't crash
timeout 120 python run_ncaab_analysis.py 2>&1 | grep -c "AttributeError" | xargs -I{} test {} -eq 0 && echo "PASS: no AttributeError" || echo "FAIL: AttributeError found"
```

All 4 checks must pass before considering this complete.
