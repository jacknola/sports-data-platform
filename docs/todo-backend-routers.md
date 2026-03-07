# Backend Routers — Code Issues & Suggested Fixes

> Generated from full codebase review of `backend/app/routers/`.

---

## props.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Global service instances created at import time (lines 33-40) — entire router fails if any service init fails | Use FastAPI dependency injection (`Depends()`) for lazy-loading |
| 2 | MEDIUM | Exception silently creates empty dict for NBA team lookup (lines 46-57) | Log warning: `logger.warning("NBA team lookup failed, using empty dict")` |
| 3 | MEDIUM | `_BANKROLL: float = 100.0` hardcoded, not from settings | Use `settings.BETTING_BANKROLL` from config |
| 4 | LOW | No rate limiting on prop analysis endpoints | Add `slowapi` or custom rate limiter middleware |

---

## analyze.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | Endpoint returns dummy response: "Analysis pipeline not yet fully implemented" | Integrate with `OrchestratorAgent` or return proper 501 status |
| 2 | MEDIUM | `data.get('sport', 'nfl')` doesn't validate sport value — accepts invalid sports | Add Pydantic enum: `sport: Literal["nba", "ncaab", "nfl"]` |
| 3 | MEDIUM | Endpoint is async but does nothing async | Either implement async agent calls or make synchronous |
| 4 | LOW | No input validation on request body | Add Pydantic request model with field validators |

---

## bets.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `min_edge` and `limit` query params not validated for ranges | Add `Query(ge=0.0, le=1.0)` for edge, `Query(ge=1, le=100)` for limit |
| 2 | MEDIUM | Non-NBA sports return hardcoded fallback data | Return 400 with message: "Sport not yet supported" |
| 3 | LOW | No pagination support for bet listing | Add `skip` and `limit` query parameters |

---

## predictions.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No validation that `date_limit` is not in the future — could cause data leakage | Add validator: `if date_limit > date.today(): raise ValueError` |
| 2 | LOW | Request validation schema not shown — unclear if all fields have bounds | Verify `PropPredictionRequest` has `Field()` constraints |

---

## dvp.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No caching on DvP data fetches — each request hits external APIs | Add Redis cache with 15-minute TTL |
| 2 | LOW | Missing position validation | Validate against enum: `Literal["PG", "SG", "SF", "PF", "C"]` |

---

## google_sheets.py (router)

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No authentication on export endpoints — anyone can trigger Sheet updates | Add API key middleware or OAuth |
| 2 | LOW | No rate limiting — rapid-fire exports could hit Google API quotas | Add 60-second cooldown between exports |

---

## parlays.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No validation on number of legs requested | Add `Query(ge=2, le=8)` constraint |
| 2 | LOW | Missing error handling for parlay generation failures | Return 500 with descriptive error message |

---

## Cross-Cutting Router Issues

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | No consistent error response schema across routers | Create `ErrorResponse` Pydantic model: `{"error": str, "code": int, "detail": str}` |
| 2 | MEDIUM | No request logging/tracing middleware | Add `X-Request-ID` header and log all requests |
| 3 | MEDIUM | No OpenAPI tags properly organized | Add `tags=["props"]`, `tags=["bets"]` to router decorators |
| 4 | LOW | Missing health check endpoint for each router | Add `/api/v1/{resource}/health` endpoints |

---

## Summary

| Router | Issues | Highest Severity |
|--------|--------|-----------------|
| props.py | 4 | MEDIUM |
| analyze.py | 4 | HIGH |
| bets.py | 3 | MEDIUM |
| predictions.py | 2 | MEDIUM |
| dvp.py | 2 | MEDIUM |
| google_sheets.py | 2 | MEDIUM |
| parlays.py | 2 | MEDIUM |
| Cross-cutting | 4 | HIGH |

**Total: 23 issues across router layer**
