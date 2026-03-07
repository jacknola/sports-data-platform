# Copilot Agent Instructions

> Global instructions for GitHub Copilot when working on this repository.

## Repository Context

Quantitative sports betting platform that identifies +EV wagers by comparing
devigged market-maker odds (Pinnacle/Circa) against retail books (FanDuel,
DraftKings). Uses Bayesian modeling, XGBoost ML, and sharp money signals.

## Agent Roles

This repository defines five specialized agent roles that Copilot should
adopt depending on the task context:

### Backend Agent
- **Trigger:** Changes to `backend/app/**`, `backend/run_*.py`, `backend/requirements.txt`
- **Instructions:** See `docs/agents/backend-agent.md`
- **Key rules:** Use loguru (not print), type hints required, Quarter/Half Kelly only

### Frontend Agent
- **Trigger:** Changes to `frontend/src/**`, `frontend/package.json`
- **Instructions:** See `docs/agents/frontend-agent.md`
- **Key rules:** Functional components, React Query, Tailwind CSS, no `any` types

### Test Agent
- **Trigger:** Changes to `backend/tests/**`, `frontend/src/**/*.test.*`
- **Instructions:** See `docs/agents/test-agent.md`
- **Key rules:** Mock external services, use parametrize, test edge cases

### Deployment Agent
- **Trigger:** Changes to `docker-compose.yml`, `Dockerfile`, `.github/workflows/**`
- **Instructions:** See `docs/agents/deployment-agent.md`
- **Key rules:** Health checks, resource limits, SSL/TLS

### Source Control Agent
- **Trigger:** Changes to `.github/**`, `.gitignore`, branch/tag operations
- **Instructions:** See `docs/agents/source-control-agent.md`
- **Key rules:** Conventional commits, branch protection, no secrets in code

## Code Review Checklist

When reviewing code in this repository, always check:

1. **No hardcoded credentials** — Use `os.getenv()` or `settings.*`
2. **No bare `except:`** — Always specify exception types
3. **Type hints present** on all function signatures
4. **Edge values are decimals** — 0.05 means 5%, multiply by 100 for display
5. **Kelly sizing capped** — Never full Kelly, max 5% of bankroll per bet
6. **Loguru logging** — `from loguru import logger`, no `print()`
7. **DB sessions managed** — Use context managers, always close
8. **Tests updated** — Any logic change needs test coverage

## Known Issues

See `docs/todo-*.md` files for comprehensive issue tracking.
Priority fixes documented in `docs/todo-security.md`.
