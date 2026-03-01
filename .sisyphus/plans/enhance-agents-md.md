# Enhance AGENTS.md Documentation

## TL;DR

> **Quick Summary**: Improve the root AGENTS.md file with comprehensive guidance for AI coding agents, including detailed test commands, code style examples, and TypeScript/React conventions.
> 
> **Deliverables**:
> - Enhanced `/Users/bb.jr/sports-data-platform/AGENTS.md` with ~200 lines
> - Better organized sections with clear examples
> - Consolidated conventions from subdirectory AGENTS.md files
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: NO - Single file edit
> **Critical Path**: Single task

---

## Context

### Original Request
User requested analysis and improvement of the AGENTS.md file to provide comprehensive guidance for AI coding agents (Cursor, Warp, Claude Code, etc.), specifically:
1. Build/lint/test commands (especially single test execution)
2. Code style guidelines (imports, formatting, types, naming, error handling)
3. ~150 lines length (will aim for ~200 for completeness)

### Analysis Summary
**Current AGENTS.md**: 172 lines, well-structured but missing:
- Concrete testing examples (single test file/function)
- Frontend TypeScript/React conventions (currently only in `frontend/AGENTS.md`)
- Code examples for common patterns
- SQLAlchemy model conventions
- TypeScript strict mode and path alias details

**Subdirectory AGENTS.md files** contain valuable context:
- `frontend/AGENTS.md`: React Query patterns, Tailwind conventions, API integration
- `backend/app/services/AGENTS.md`: Service layer patterns, async-first
- `backend/app/routers/AGENTS.md`: FastAPI router patterns
- `backend/app/agents/AGENTS.md`: Multi-agent system conventions

### Research Findings
From codebase analysis:
- **Tests**: `pytest backend/tests/test_api_health.py::test_root_returns_200` pattern confirmed
- **Pytest config**: `backend/pytest.ini` has async mode, log settings
- **Frontend package.json**: Scripts are `dev`, `build`, `lint`
- **TypeScript**: Strict mode enabled, path alias `@/*` → `./src/*`
- **Python imports**: Absolute imports with `app.` prefix pattern confirmed
- **Database**: SQLAlchemy models need `extend_existing=True` (per ACTIVE STATUS notes)

### Skills Discovery
**Comprehensive search** via `npx skills find` identified relevant skills:
- **13 high-value skills** for Python, FastAPI, React, TypeScript, Postgres, testing
- **Top priorities**: python-code-style (2.3K installs), fastapi-templates (4.9K), vercel-react-best-practices (178.7K)
- **Domain-specific**: supabase-postgres-best-practices (26K), sqlalchemy-alembic-expert (125)
- **Quality/Testing**: webapp-testing (16.3K), code-review-excellence (5.8K)

**Decision**: Add "Recommended Skills" section to AGENTS.md to document these for future agents.

---

## Work Objectives

### Core Objective
Enhance the root AGENTS.md to serve as a comprehensive, standalone guide for AI coding agents with all essential build/test/style information consolidated in one place.

### Concrete Deliverables
- Updated `/Users/bb.jr/sports-data-platform/AGENTS.md` (~200 lines)
- All testing commands with concrete examples
- Frontend and backend code style sections with examples
- Consolidated conventions from subdirectory files
- Clear anti-patterns section

### Definition of Done
- [ ] AGENTS.md contains all test command examples (all tests, single file, single function)
- [ ] Code style sections for both Python and TypeScript with examples
- [ ] Import conventions, type hints, error handling documented
- [ ] Frontend-specific conventions (React Query, Tailwind, path aliases) included
- [ ] Anti-patterns section is clear and actionable
- [ ] File is well-organized with clear section headers
- [ ] Length is ~200 lines (acceptable range: 180-220)

### Must Have
- Pytest command examples (all, single file, single function)
- Python import patterns with examples
- TypeScript strict mode and path alias documentation
- Frontend React Query pattern example
- SQLAlchemy `extend_existing=True` convention
- Logging convention (loguru, no print())
- Async/await patterns for HTTP requests

### Must NOT Have (Guardrails)
- No removal of existing betting logic conventions (critical business logic)
- No removal of sharp money signals section (domain-specific knowledge)
- No removal of current state tracking (agent coordination)
- No duplication of content that belongs in subdirectory AGENTS.md files
- No generic AI-generated fluff ("best practices", "ensure quality", etc.)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: N/A (documentation only)
- **Automated tests**: None (this is a documentation task)
- **Manual verification**: Read-through and structure check

### QA Policy
This is a documentation task. QA will be manual review of the file structure and content.

---

## Execution Strategy

### Single Task
This is a single file edit, no parallel execution needed.

---

## TODOs

- [ ] 1. Enhance AGENTS.md Documentation

  **What to do**:
  - Read current `/Users/bb.jr/sports-data-platform/AGENTS.md` to preserve all existing content
  - Reorganize into clearer sections with better headers:
    - Project Context (keep existing)
    - Build, Run, and Test Commands (enhance with examples)
    - Code Style & Conventions (split Python/Frontend, add examples)
    - Betting Logic Conventions (keep existing, no changes)
    - Sharp Money Signals (keep existing, no changes)
    - Key Services (keep existing table format)
    - Anti-Patterns (expand with examples)
    - Operational Directives (keep existing)
    - Current State & Agent Coordination (keep existing)
  
  **Enhancements to add**:
  
  1. **Testing section** - Add concrete examples:
     ```bash
     # Run ALL tests
     pytest backend/
     
     # Run a SINGLE test file
     pytest backend/tests/test_api_health.py
     
     # Run a SINGLE test function
     pytest backend/tests/test_api_health.py::test_root_returns_200
     ```
     - Note about `PYTHONPATH=$(pwd)/backend` if imports fail
     - Reference to `backend/pytest.ini` for configuration
  
  2. **Python Code Style** - Add examples for:
     - Import pattern with actual code:
       ```python
       from app.services.bet_tracker import BetTracker
       ```
     - Type hints example:
       ```python
       async def get_bets(sport: str, min_edge: float) -> List[Dict[str, Any]]:
       ```
     - Async HTTP pattern:
       ```python
       try:
           async with httpx.AsyncClient(timeout=15.0) as client:
               response = await client.get(url)
       except Exception as e:
           logger.error(f"Failed to fetch {url}: {e}")
       ```
     - SQLAlchemy model convention:
       ```python
       class MyModel(Base):
           __tablename__ = "my_table"
           __table_args__ = {'extend_existing': True}
       ```
  
  3. **Frontend TypeScript/React** - Add section with:
     - Functional components example:
       ```tsx
       export const MyComponent: React.FC = () => {
         const [state, setState] = useState<string>("");
         return <div>{state}</div>;
       };
       ```
     - React Query pattern:
       ```tsx
       const { data, isLoading } = useQuery({
         queryKey: ['bets'],
         queryFn: () => axios.get('/api/v1/bets')
       });
       ```
     - Path alias: `@/*` maps to `./src/*`
     - Tailwind CSS only, custom colors: `primary-*`, `accent-*`
     - No `any` types, no `@ts-ignore`
     - Axios unwraps `response.data` (callers get `T` directly)
  
  4. **Anti-Patterns** - Expand with:
     - Bare except blocks (use `except Exception:`)
     - print() in services (use logger)
     - Full Kelly (always Quarter/Half)
     - Type suppression (`as any`, `@ts-ignore`)
     - Schema changes without verification
  
  5. **Maintain existing sections** exactly as they are:
     - Betting Logic Conventions (devigging, Kelly, edge thresholds, etc.)
     - Sharp Money Signals (RLM, Steam, Line Freeze, etc.)
     - Key Services table
     - Current State & Agent Coordination
  
  6. **Recommended Skills Section** - Add new section documenting helpful skills:
     ```markdown
     ## Recommended Skills for AI Agents
     
     These skills enhance AI agent capabilities when working with this codebase:
     
     ### Core Development
     - `wshobson/agents@python-code-style` - Python style enforcement
     - `wshobson/agents@python-testing-patterns` - Pytest best practices
     - `wshobson/agents@fastapi-templates` - FastAPI patterns
     - `wshobson/agents@async-python-patterns` - Async/await patterns
     
     ### Frontend
     - `vercel-labs/agent-skills@vercel-react-best-practices` - React patterns
     - `wshobson/agents@tailwind-design-system` - Tailwind advanced patterns
     
     ### Database
     - `supabase/agent-skills@supabase-postgres-best-practices` - Postgres optimization
     - `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` - SQLAlchemy/Alembic
     
     ### Testing & Quality
     - `anthropics/skills@webapp-testing` - E2E testing with Playwright
     - `wshobson/agents@code-review-excellence` - Code review standards
     
     ### Documentation
     - `solatis/claude-config@codebase-analysis` - Codebase understanding
     - `wshobson/agents@api-design-principles` - API design patterns
     
     Install all: `npx skills add [skill-name] -g -y`
     ```
  
  **Must NOT do**:
  - Don't remove or alter betting logic formulas
  - Don't remove sharp money signal definitions
  - Don't remove current state tracking
  - Don't add generic fluff language
  - Don't duplicate content from subdirectory AGENTS.md files verbatim
  
  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file documentation edit, clear requirements, no complex logic
  - **Skills**: `['wshobson/agents@python-code-style', 'wshobson/agents@fastapi-templates']`
    - `wshobson/agents@python-code-style`: Validates Python code examples in documentation
    - `wshobson/agents@fastapi-templates`: Ensures FastAPI patterns are accurate
  - **Skills Evaluated but Omitted**:
    - `vercel-labs/agent-skills@vercel-react-best-practices`: Useful but frontend examples are straightforward
    - `anthropics/skills@webapp-testing`: Not needed for documentation-only task
  
  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: N/A (single task)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)
  
  **References** (CRITICAL - Be Exhaustive):
  
  **Current file to enhance**:
  - `/Users/bb.jr/sports-data-platform/AGENTS.md` - Current version to preserve and improve
  
  **Subdirectory AGENTS.md files for context** (don't copy verbatim, extract key patterns):
  - `/Users/bb.jr/sports-data-platform/frontend/AGENTS.md` - React Query, Tailwind, API patterns
  - `/Users/bb.jr/sports-data-platform/backend/app/services/AGENTS.md` - Service layer conventions
  - `/Users/bb.jr/sports-data-platform/backend/app/routers/AGENTS.md` - FastAPI patterns
  - `/Users/bb.jr/sports-data-platform/backend/app/agents/AGENTS.md` - Agent system patterns
  
  **Code examples for style reference**:
  - `/Users/bb.jr/sports-data-platform/backend/app/routers/bets.py` - Import style, type hints, docstrings
  - `/Users/bb.jr/sports-data-platform/frontend/package.json` - Frontend scripts
  - `/Users/bb.jr/sports-data-platform/frontend/tsconfig.json` - TypeScript config, path aliases
  
  **Configuration files**:
  - `/Users/bb.jr/sports-data-platform/backend/pytest.ini` - Test configuration
  - `/Users/bb.jr/sports-data-platform/backend/requirements.txt` - Dependencies context
  
  **WHY Each Reference Matters**:
  - Current AGENTS.md: Base document to enhance, contains critical business logic (betting conventions, signals) that MUST be preserved exactly
  - Subdirectory AGENTS.md files: Source of specific conventions to consolidate (React Query patterns, async-first, router patterns)
  - bets.py: Real code example showing import style, type hints, FastAPI patterns, docstrings
  - package.json: Scripts for frontend build/dev/lint commands
  - tsconfig.json: Path alias configuration and strict mode settings
  - pytest.ini: Test configuration to reference in testing section
  
  **Acceptance Criteria**:
  
  **File Structure:**
  - [ ] File has clear section headers with markdown formatting
  - [ ] Length is 180-220 lines
  - [ ] All existing critical sections preserved (betting logic, signals, current state)
  
  **Testing Section:**
  - [ ] Contains example for running ALL tests
  - [ ] Contains example for running single test file
  - [ ] Contains example for running single test function
  - [ ] References pytest.ini configuration file
  - [ ] Includes PYTHONPATH note for import issues
  
  **Python Style Section:**
  - [ ] Import pattern documented with example
  - [ ] Type hints requirement with example
  - [ ] Async HTTP pattern with httpx example
  - [ ] Error handling pattern (try/except with logger)
  - [ ] SQLAlchemy extend_existing convention
  - [ ] Logging convention (loguru, no print)
  
  **Frontend Style Section:**
  - [ ] Functional components with hooks example
  - [ ] React Query pattern example
  - [ ] Path alias documentation (@/* → ./src/*)
  - [ ] Tailwind CSS convention
  - [ ] TypeScript strict mode mentioned
  - [ ] No any/ts-ignore rule
  - [ ] Axios unwrapping behavior documented
  
  **Anti-Patterns Section:**
  - [ ] Bare except prohibition
  - [ ] print() prohibition
  - [ ] Full Kelly prohibition
  - [ ] Type suppression rule
  
  **QA Scenarios** (Manual Review):
  
  ```
  Scenario: Verify enhanced AGENTS.md structure
    Tool: Read file
    Steps:
      1. Read /Users/bb.jr/sports-data-platform/AGENTS.md
      2. Count lines (should be 180-220)
      3. Check section headers are present and clear
      4. Verify all existing betting logic sections unchanged
    Expected Result: Well-structured file with all sections present
    Evidence: Manual inspection (no automated test for docs)
  
  Scenario: Verify testing examples are complete
    Tool: Grep
    Steps:
      1. Grep for "pytest backend/" in AGENTS.md
      2. Grep for "pytest backend/tests/test_api_health.py" in AGENTS.md
      3. Grep for "::test_" in AGENTS.md
    Expected Result: All three pytest patterns present
    Evidence: Manual grep verification
  
  Scenario: Verify code examples are present
    Tool: Grep
    Steps:
      1. Search for "```python" blocks in file
      2. Search for "```tsx" or "```typescript" blocks
      3. Verify examples show actual code patterns
    Expected Result: At least 3 Python examples and 2 TypeScript examples
    Evidence: Manual inspection of code blocks
  
  Scenario: Verify critical sections preserved
    Tool: Diff
    Steps:
      1. Compare "Betting Logic Conventions" section before/after
      2. Compare "Sharp Money Signals" section before/after
      3. Compare "Current State" section before/after
    Expected Result: These sections identical to original
    Evidence: Git diff shows no changes to these sections
  ```
  
  **Commit**: YES
  - Message: `docs(agents): enhance AGENTS.md with test examples and code style patterns`
  - Files: `AGENTS.md`
  - Pre-commit: N/A (documentation only)

---

## Success Criteria

### Verification Commands
```bash
wc -l AGENTS.md                          # Expected: 180-220 lines
grep -c "pytest backend/" AGENTS.md      # Expected: ≥3 (examples present)
grep -c "\`\`\`python" AGENTS.md         # Expected: ≥3 (code examples)
grep -c "\`\`\`tsx" AGENTS.md            # Expected: ≥1 (TypeScript examples)
```

### Final Checklist
- [ ] All testing command examples present (all/file/function)
- [ ] Python style section with examples
- [ ] Frontend TypeScript/React section with examples
- [ ] All existing betting logic preserved unchanged
- [ ] Anti-patterns section expanded
- [ ] File length 180-220 lines
- [ ] Well-organized with clear headers
