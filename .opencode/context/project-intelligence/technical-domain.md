<!-- Context: project-intelligence/technical | Priority: critical | Version: 1.0 | Updated: 2026-02-27 -->

# Technical Domain

**Purpose**: Tech stack, architecture, development patterns, and AI agent model configuration.
**Last Updated**: 2026-02-27

## Quick Reference
**Update Triggers**: Tech stack changes | New patterns | Model config changes | Architecture decisions
**Audience**: Developers, AI agents

## Primary Stack
| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Backend Framework | FastAPI | Python 3.9+ | Async API, auto-docs, Pydantic validation |
| Language (Backend) | Python | 3.11 | ML ecosystem, type hints |
| Language (Frontend) | TypeScript | 5.x | Type safety, React integration |
| Frontend Framework | React | 18 | Hooks, concurrent features, React Query |
| Build Tool | Vite | latest | Fast HMR, proxy config |
| Database | Supabase/PostgreSQL | latest | Real-time, auth, SQLite fallback |
| Cache | Redis | latest | Session, rate limiting, Celery broker |
| Styling | Tailwind CSS | 3.x | Utility-first, custom `primary-*`/`accent-*` |
| ML | XGBoost + PyMC | latest | Calibrated probabilities, Bayesian posteriors |
| Task Queue | Celery | latest | Async pipeline, scheduled reports |
| Logging | Loguru | latest | Structured logging. No `print()` in services |
| HTTP Client | httpx | latest | Async, timeout=15.0 |
| Reporting | Telegram Bot API | latest | 3x daily, 4096 char limit, HTML parse mode |

## AI Agent Model Configuration
**Strategy**: Gemini for token-efficient subagents, OpenCode for premium primary. Only `gemini` + `opencode` providers enabled.

| Agent | Model | Role | Cost Tier |
|-------|-------|------|-----------|
| Default | `gemini/gemini-2.5-pro` | Baseline for unassigned agents | Mid |
| Small | `gemini/gemini-2.5-flash` | Titles, summaries, compaction | Low |
| **OpenAgent** | `opencode/claude-opus-4-6` | Primary orchestrator | Premium |
| ContextScout | `gemini/gemini-2.5-flash` | Read-only codebase discovery | Low |
| ExternalScout | `gemini/gemini-2.5-flash` | External doc fetching | Low |
| DocWriter | `gemini/gemini-2.5-flash` | Documentation generation | Low |
| **TaskManager** | `gemini/gemini-2.5-pro` | Complex task decomposition | Mid |
| ContextOrganizer | `gemini/gemini-2.5-flash` | Context file generation | Low |

**Rationale**: Flash ($0.30/M input) handles ~70% of subagent calls. Pro ($1.25/M) only for reasoning-heavy tasks. Opus 4-6 for primary: best reasoning + coding quality where it matters most.

## Code Patterns
### API Endpoint (FastAPI)
```python
@router.get("/endpoint", response_model=ResponseSchema)
async def get_endpoint(param: str = Query(...)) -> ResponseSchema:
    """Concise docstring explaining business logic."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
        return ResponseSchema(data=response.json())
    except Exception as e:
        logger.error(f"Endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Frontend Component (React)
```typescript
interface Props { name: string; value: number }
export function StatCard({ name, value }: Props) {
  const { data } = useQuery({ queryKey: ['stat', name], queryFn: () => api.get(`/api/stats/${name}`) })
  return <div className="rounded-lg border border-primary-200 p-4"><h3>{name}</h3><p>{value}</p></div>
}
```

## Naming Conventions
| Type | Convention | Example |
|------|-----------|---------|
| Python files | snake_case | `sharp_money_detector.py` |
| Python classes | PascalCase | `BetTracker` |
| Python functions | snake_case | `calculate_ev()` |
| TS/React files | kebab-case | `stat-card.tsx` |
| Components | PascalCase | `StatCard` |
| TS functions | camelCase | `getUserProfile()` |
| Database | snake_case | `bet_records` |
| Imports (Python) | Absolute from `app.` | `from app.services.bet_tracker import BetTracker` |

## Code Standards
- Type hints required on ALL function args and return types
- Loguru `logger` only (no `print()` in services)
- `httpx.AsyncClient` with `timeout=15.0` for HTTP
- Graceful degradation (Supabase → SQLite fallback)
- Config via `app.config.settings` (pydantic-settings)
- React Query for server state. No Redux/Context for global
- Tailwind CSS only. Custom colors: `primary-*`, `accent-*`
- All frontend API requests prefixed with `/api`

## Security Requirements
- Validate all user input (Pydantic models, Zod on frontend)
- Parameterized queries only (no raw SQL interpolation)
- No `as any`, `@ts-ignore`, `@ts-expect-error`
- Env secrets via `.env` (never hardcoded)
- Never Full Kelly — always Quarter or Half Kelly fractions

## 📂 Codebase References
- **Config**: `.opencode/opencode.json` — model assignments, provider restrictions
- **Primary Agent**: `.opencode/agent/core/openagent.md` — orchestrator definition
- **Subagents**: `.opencode/agent/subagents/core/` — ContextScout, ExternalScout, DocWriter, TaskManager
- **Backend Entry**: `backend/app/` — FastAPI services, routers, models
- **Frontend Entry**: `frontend/src/` — React components, hooks, utils
- **Pipeline**: `backend/app/services/` — Bayesian, Kelly, ML, Sharp detection

## Related Files
- AGENTS.md (root) — comprehensive project context and coordination rules
- .opencode/.opencode.yaml — project metadata and commands
