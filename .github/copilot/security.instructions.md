---
name: security-instructions
description: >
  Security-focused instructions for handling credentials, API keys, secrets,
  input validation, and safe coding patterns across the entire codebase.
applyTo: '**'
---

# Security Instructions

These security rules apply to ALL code changes in the sports-data-platform.

## Secrets Management (Critical)

### Never Hardcode

- API keys, tokens, passwords, or connection strings
- Sportsbook credentials or account identifiers
- Service account JSON content
- Encryption keys or certificates

### Always Use

```python
# Python — load from Pydantic settings
from app.config import settings
api_key = settings.THE_ODDS_API_KEY

# Python — fallback to os.getenv
import os
api_key = os.getenv("THE_ODDS_API_KEY")
```

```typescript
// TypeScript — use Vite env vars
const apiUrl = import.meta.env.VITE_API_URL;
// NEVER expose backend secrets to frontend
```

### Required .gitignore Coverage

The following MUST be gitignored:
```
.env
.env.*
credentials.json
service-account*.json
*.pem
*.key
*.p12
*.pfx
```

## Input Validation

### API Endpoints

- Validate all request parameters with Pydantic models
- Bound numeric inputs (probabilities ∈ [0,1], odds within reasonable ranges)
- Sanitize string inputs before database queries
- Use parameterized queries (SQLAlchemy handles this automatically)

### Betting Logic

- Win probability must be bounded [0, 1] — enforced in `bet_tracker.py`
- Kelly fraction must be ≤ 0.5 (Half Kelly maximum) — never Full Kelly
- Single bet stake must be ≤ 5% of bankroll
- Edge values must be reasonable (flag anything > 30% edge as suspicious)

## Error Handling

```python
# NEVER do this
try:
    result = await fetch_data()
except:  # bare except catches SystemExit, KeyboardInterrupt
    pass

# ALWAYS do this
try:
    result = await fetch_data()
except httpx.TimeoutException as e:
    logger.warning(f"Timeout fetching data: {e}")
    return fallback_value
except Exception as e:
    logger.error(f"Unexpected error fetching data: {e}")
    raise
```

## External Service Resilience

- All external API calls must have timeouts (`timeout=15.0` for httpx)
- Implement circuit breaker patterns for flaky APIs
- Always have fallback paths (Supabase → SQLite, API → cached data)
- Never trust external data — validate before processing
- Rate limit awareness: Odds API has usage limits, respect them

## Database Security

- Use SQLAlchemy ORM — never raw SQL string concatenation
- Database credentials via environment variables only
- SQLite fallback must use a local file path, not in-memory for persistence
- Close DB sessions in `finally` blocks

## Logging Security

- Never log full API keys, tokens, or passwords
- Redact sensitive data: `logger.info(f"Using API key: {key[:4]}...{key[-4:]}")`
- Log security-relevant events (failed auth, suspicious inputs, rate limit hits)
- Use loguru structured logging — never `print()` for security events

## Dependency Security

- Pin dependency versions in `requirements.txt` and `package.json`
- Review new dependencies before adding — check for known vulnerabilities
- Avoid heavy or unnecessary dependencies (`torch`, `crawl4ai`) unless justified
- Keep dependencies up to date for security patches
