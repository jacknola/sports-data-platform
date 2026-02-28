<!--
Sync Impact Report:
- Version change: 0.0.0 -> 1.0.0 (Initial Ratification)
- Principles Defined:
  - Scientific Betting Logic
  - Rigorous Engineering Standards
  - Resilience & Data Integrity
  - Observable Operations
  - Capital Preservation
- Added Sections: Technical Constraints, Development Workflow
- Templates Impacted:
  - .specify/templates/tasks-template.md (✅ updated to enforce mandatory testing)
  - .specify/templates/plan-template.md (✅ updated with principle-specific checklist)
-->

# Sports Data Intelligence Platform Constitution

## Core Principles

### I. Scientific Betting Logic
All value calculations must be mathematically grounded using devigged sharp book odds (Pinnacle/Circa) and Bayesian modeling. EV calculation (`(True Prob * Decimal Odds) - 1`) is the source of truth. Bet sizing strictly follows Multivariate Fractional Kelly (Quarter/Half). No "gut feeling" or retail logic.

### II. Rigorous Engineering Standards
Code quality must equal senior engineering standards. Mandatory Python type hints (`typing`), strict linting (Black/Isort/Ruff), and comprehensive testing (`pytest`). No `print()` statements in production code; use `loguru`. No type suppression (`as any`, `ignore`) without documented justification.

### III. Resilience & Data Integrity
The system assumes external APIs (Odds API, ESPN) are unreliable. Robust error handling, circuit breakers, and database fallbacks (Supabase → SQLite) are mandatory. "Bad data is worse than no data"—validate inputs aggressively.

### IV. Observable Operations
Operational visibility is critical. All services must emit structured logs and meaningful metrics. Telegram reports and Notion/Sheets syncs serve as the primary user interfaces for monitoring system health and betting signals.

### V. Capital Preservation
Risk management supersedes potential returns. Never bet >5% of bankroll on a single event. Portfolio risk is managed via convex optimization for correlated bets. Closing Line Value (CLV) > 0 is the primary success metric.

## Technical Constraints

- **Backend**: Python 3.9+, FastAPI, Supabase (PostgreSQL), Redis, Celery.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS (no inline styles).
- **Data**: All odds internal calculations in Decimal format.
- **Environment**: Strict separation of secrets via `.env`.

## Development Workflow

- **Testing**: All logic changes require passing tests (`pytest`).
- **Verification**: Run `run_ncaab_analysis.py` (or equivalent) to smoke-test before committing.
- **Documentation**: Update `AGENTS.md` after major changes.
- **Dependencies**: Keep `requirements.txt` minimal and pinned.

## Governance

- This Constitution supersedes all previous "unwritten rules".
- Amendments require a semantic version bump and justification in the commit message.
- All Pull Requests must be checked against these principles before merge.
- Exceptions to principles must be explicitly documented in code comments with rationale.

**Version**: 1.0.0 | **Ratified**: 2026-02-28 | **Last Amended**: 2026-02-28
