# Backend Code Cleanup - Remove Debug Code & Apply Formatting

## TL;DR

> **Quick Summary**: Clean 24 modified Python files to remove debug code, apply consistent formatting, and ensure AGENTS.md compliance.
> 
> **Deliverables**:
> - `analysis_runner.py` with `print()` removed (CRITICAL - violates service convention)
> - All 24 modified files formatted with `black`
> - Imports optimized with `isort`
> - Linting issues auto-fixed with `ruff`
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: NO - Sequential (install tools → fix critical → format all)
> **Critical Path**: Install tools → Fix service violation → Format → Verify

---

## Context

### Original Request
User requested code cleanup via `/clean` command with no arguments specified.

### Analysis Summary
**Modified Files Analyzed:** 24 Python files
- Service layer: 8 files
- Routers: 3 files
- Agents: 2 files
- Tests: 6 files
- Scripts: 5 files

**Critical Finding:**
- `backend/app/services/analysis_runner.py` contains 2 `print()` statements (lines 68, 149)
- **VIOLATES AGENTS.md:** "No `print()` in services — Use `logger` from loguru"
- These are visual separators (`print("\n\n" + "X" * 76 + "\n\n")`) in captured stdout

**Other Findings:**
- 301 total `print()` statements across codebase (mostly in CLI scripts - acceptable)
- `run_nba_analysis.py` and `run_ncaab_analysis.py` have print statements (OK - entry scripts, not services)
- No syntax errors in any modified files ✅
- Test files are clean ✅
- Formatting tools (`black`, `ruff`, `isort`) not installed

### Research Findings
**AGENTS.md Conventions:**
- "No `print()` in services — Use `logger` from loguru"
- "Use `black` + `isort` conventions (88-100 char lines)"
- "Use `ruff` or `flake8` for static analysis"

**Entry Scripts Exception:**
- `backend/run_*.py` scripts are CLI entry points, not services
- `print()` acceptable there for user-facing output
- Only service layer must use `logger` exclusively

---

## Work Objectives

### Core Objective
Ensure all service layer code follows AGENTS.md conventions (no print statements), install code quality tools, and apply consistent formatting to all modified files.

### Concrete Deliverables
- Fixed `backend/app/services/analysis_runner.py` (remove 2 print statements)
- Installed tools: `black`, `ruff`, `isort` in backend venv
- All 24 modified Python files formatted with `black`
- Imports sorted with `isort`
- Auto-fixable linting issues resolved with `ruff`
- All tests passing after cleanup

### Definition of Done
- [ ] `analysis_runner.py` has zero `print()` statements
- [ ] `black`, `ruff`, `isort` installed in backend environment
- [ ] All 24 modified files formatted consistently
- [ ] Imports sorted alphabetically and grouped properly
- [ ] `pytest backend/` passes (262 tests)
- [ ] Git diff shows only formatting changes (no logic changes)

### Must Have
- Remove print() from `analysis_runner.py` lines 68 and 149
- Install black, ruff, isort
- Format all modified files
- Verify tests still pass

### Must NOT Have (Guardrails)
- No logic changes - formatting only
- No changes to entry scripts (`run_*.py`) - their print() statements are acceptable
- No changes to test files - they're already clean
- No introduction of new bugs

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES - pytest with 262 tests
- **Automated tests**: Run after each phase to ensure no breakage
- **Framework**: pytest

### QA Policy
After each task, run `pytest backend/` to verify no regressions.

---

## Execution Strategy

### Sequential Execution (3 Phases)
Tasks must run in order:
1. **Phase 1**: Fix critical service violation
2. **Phase 2**: Install tools
3. **Phase 3**: Format all files
4. **Phase 4**: Verify

---

## TODOs

- [x] 1. Fix Critical Service Violation

  **What to do**:
  - Read `backend/app/services/analysis_runner.py`
  - Remove `print()` statements on lines 68 and 149
  - Replace with comments explaining they were visual separators
  - Code context:
    ```python
    # Line 68 (inside redirect_stdout):
    run_ncaab()
    print("\n\n" + "X" * 76 + "\n\n")  # REMOVE THIS
    run_nba()
    
    # Line 149 (inside redirect_stdout):
    ncaab_data = run_ncaab()
    print("\n\n" + "X" * 76 + "\n\n")  # REMOVE THIS
    nba_data = asyncio.run(run_nba_analysis())
    ```
  - Replacement:
    ```python
    # Line 68:
    run_ncaab()
    # Visual separator between NCAAB and NBA output (removed - captured in stdout)
    run_nba()
    
    # Line 149:
    ncaab_data = run_ncaab()
    # Visual separator between NCAAB and NBA output (removed - captured in stdout)
    nba_data = asyncio.run(run_nba_analysis())
    ```

  **Must NOT do**:
  - Don't change any logic
  - Don't touch print() in `run_nba_analysis.py` or `run_ncaab_analysis.py` (they're entry scripts)
  - Don't add logger statements (just remove the visual separators)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple find-and-replace in single file
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 2, 3, 4
  - **Blocked By**: None

  **References**:
  - `/Users/bb.jr/sports-data-platform/backend/app/services/analysis_runner.py` - File to fix
  - `/Users/bb.jr/sports-data-platform/AGENTS.md` - Convention: "No print() in services"
  - `/Users/bb.jr/sports-data-platform/backend/app/services/AGENTS.md` - Service layer conventions

  **Acceptance Criteria**:
  - [ ] `grep -n "print(" backend/app/services/analysis_runner.py` returns 0 results
  - [ ] File still compiles: `python3 -m py_compile backend/app/services/analysis_runner.py`
  - [ ] Git diff shows only 2 lines removed

  **QA Scenarios**:
  ```
  Scenario: Verify print() removed
    Tool: Bash (grep)
    Steps:
      1. Run: grep -c "print(" backend/app/services/analysis_runner.py
      2. Assert: Output is "0"
    Expected Result: Zero print statements in file
    Evidence: Command output showing 0 matches
  
  Scenario: Verify file compiles
    Tool: Bash (python compile)
    Steps:
      1. Run: python3 -m py_compile backend/app/services/analysis_runner.py
      2. Check exit code
    Expected Result: Exit code 0 (success)
    Evidence: No compilation errors
  ```

  **Commit**: YES
  - Message: `fix(services): remove print() from analysis_runner per AGENTS.md`
  - Files: `backend/app/services/analysis_runner.py`
  - Pre-commit: `python3 -m py_compile backend/app/services/analysis_runner.py`

---

- [x] 2. Install Code Quality Tools

  **What to do**:
  - Navigate to backend directory
  - Activate venv if exists: `source venv/bin/activate` or `source .venv/bin/activate`
  - Install tools: `pip install black ruff isort`
  - Verify installations:
    ```bash
    which black
    which ruff
    which isort
    black --version
    ruff --version
    isort --version
    ```

  **Must NOT do**:
  - Don't install globally - use backend venv
  - Don't run formatters yet (next task)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple pip install
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 3
  - **Blocked By**: Task 1

  **References**:
  - `/Users/bb.jr/sports-data-platform/backend/requirements.txt` - May need updating
  - `/Users/bb.jr/sports-data-platform/AGENTS.md` - Mentions black, ruff, isort

  **Acceptance Criteria**:
  - [ ] `which black` returns path in backend venv
  - [ ] `which ruff` returns path in backend venv
  - [ ] `which isort` returns path in backend venv
  - [ ] All three commands run without errors

  **QA Scenarios**:
  ```
  Scenario: Verify tools installed
    Tool: Bash
    Steps:
      1. cd backend && source venv/bin/activate
      2. Run: which black ruff isort
      3. Run: black --version && ruff --version && isort --version
    Expected Result: All commands succeed, show version numbers
    Evidence: Terminal output with paths and versions
  ```

  **Commit**: NO (tool installation, not code change)

---

- [x] 3. Format All Modified Files

  **What to do**:
  - Get list of modified Python files: `git diff --name-only HEAD | grep '\.py$'`
  - Run formatters on each file:
    1. **isort** (sort imports): `isort <file>`
    2. **black** (format code): `black <file>`
    3. **ruff** (lint + auto-fix): `ruff check --fix <file>`
  
  - Modified files to format (24 total):
    ```
    backend/app/agents/analysis_agent.py
    backend/app/agents/orchestrator.py
    backend/app/config/__init__.py
    backend/app/memory/agent_memory.py
    backend/app/models/__init__.py
    backend/app/routers/agents.py
    backend/app/routers/parlays.py
    backend/app/routers/props.py
    backend/app/services/analysis_runner.py
    backend/app/services/bet_tracker.py
    backend/app/services/google_sheets.py
    backend/app/services/nba_ml_predictor.py
    backend/app/services/nba_stats_service.py
    backend/app/services/rag_pipeline.py
    backend/app/services/sharp_money_tracker.py
    backend/run_historical_vectorize.py
    backend/run_nba_analysis.py
    backend/run_ncaab_analysis.py
    backend/telegram_cron.py
    backend/tests/models/test_orm_models.py
    backend/tests/test_nba_dvp_analyzer.py
    backend/tests/unit/test_data_extraction.py
    backend/tests/unit/test_player_backfill.py
    backend/tests/unit/test_player_game_log_model.py
    backend/tests/unit/test_player_vector_backfill.py
    ```
  
  - Batch command:
    ```bash
    cd backend
    git diff --name-only HEAD | grep '\.py$' | while read f; do
      echo "Formatting $f..."
      isort "$f"
      black "$f"
      ruff check --fix "$f" || true
    done
    ```

  **Must NOT do**:
  - Don't format files outside git diff (too broad)
  - Don't change logic - only formatting
  - Don't break imports or functionality

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Automated tool execution, no complex logic
  - **Skills**: `['wshobson/agents@python-code-style']`
    - `wshobson/agents@python-code-style`: Ensures Python formatting follows best practices

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 4
  - **Blocked By**: Task 2

  **References**:
  - All 24 modified Python files listed above
  - `/Users/bb.jr/sports-data-platform/AGENTS.md` - Style conventions

  **Acceptance Criteria**:
  - [ ] `black --check <file>` passes for all files (no changes needed)
  - [ ] `isort --check <file>` passes for all files
  - [ ] `ruff check <file>` shows no auto-fixable errors
  - [ ] Git diff shows only formatting changes (no logic)
  - [ ] All files still compile

  **QA Scenarios**:
  ```
  Scenario: Verify formatting applied
    Tool: Bash
    Steps:
      1. Run: black --check backend/app/services/analysis_runner.py
      2. Run: isort --check backend/app/services/analysis_runner.py
      3. Check exit codes (0 = no changes needed)
    Expected Result: Both commands exit 0
    Evidence: Terminal output "All done! ✨"
  
  Scenario: Verify no logic changes
    Tool: Bash (git diff review)
    Steps:
      1. Run: git diff backend/app/services/analysis_runner.py
      2. Review changes - should be whitespace, import order only
    Expected Result: Only formatting differences visible
    Evidence: Git diff showing spacing/import changes only
  ```

  **Commit**: YES
  - Message: `style(backend): apply black, isort, ruff formatting to modified files`
  - Files: All 24 modified Python files
  - Pre-commit: `black --check <files> && isort --check <files>`

---

- [ ] 4. Verify Tests Pass

  **What to do**:
  - Run full test suite: `cd backend && pytest`
  - Verify all 262 tests still pass
  - Check for any new warnings or errors
  - If tests fail:
    - Identify which file changes broke tests
    - Review git diff for that file
    - Fix formatting issues that broke logic
    - Re-run tests

  **Must NOT do**:
  - Don't skip this step - critical to ensure no breakage
  - Don't commit if tests fail

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Running existing test suite
  - **Skills**: `['wshobson/agents@python-testing-patterns']`
    - `wshobson/agents@python-testing-patterns`: Helps diagnose test failures if any occur

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None (final task)
  - **Blocked By**: Task 3

  **References**:
  - `/Users/bb.jr/sports-data-platform/backend/pytest.ini` - Test configuration
  - `/Users/bb.jr/sports-data-platform/backend/tests/` - All test files

  **Acceptance Criteria**:
  - [ ] `pytest backend/` exits with code 0
  - [ ] Output shows "262 passed"
  - [ ] No new warnings introduced
  - [ ] Test execution time similar to before cleanup

  **QA Scenarios**:
  ```
  Scenario: Verify all tests pass
    Tool: Bash (pytest)
    Steps:
      1. cd backend
      2. Run: pytest -v
      3. Check output for "262 passed"
    Expected Result: All tests pass, zero failures
    Evidence: Pytest output showing 262/262 passed
  
  Scenario: Verify no regressions
    Tool: Bash (pytest comparison)
    Steps:
      1. Compare test count before/after
      2. Check for new test failures or skips
    Expected Result: Same number of tests, same pass rate
    Evidence: Test summary matching pre-cleanup baseline
  ```

  **Commit**: NO (verification only, no changes)

---

## Success Criteria

### Verification Commands
```bash
# Verify print() removed from service
grep -c "print(" backend/app/services/analysis_runner.py  # Expected: 0

# Verify tools installed
which black ruff isort  # Expected: paths in backend venv

# Verify formatting applied
black --check backend/app/services/*.py  # Expected: "All done!"
isort --check backend/app/services/*.py  # Expected: success

# Verify tests pass
cd backend && pytest  # Expected: 262 passed
```

### Final Checklist
- [ ] Zero `print()` statements in service layer files
- [ ] `black`, `ruff`, `isort` installed and working
- [ ] All 24 modified files formatted consistently
- [ ] Imports sorted alphabetically
- [ ] All 262 tests passing
- [ ] Only formatting changes in git diff (no logic changes)
- [ ] AGENTS.md compliance verified
