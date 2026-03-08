# Configuration & Infrastructure — Code Issues & Suggested Fixes

> Generated from review of settings, database, Docker, and deployment files.

---

## backend/app/config/settings.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | `SECRET_KEY = "dev_secret_key_change_in_production"` — insecure default not enforced | Add startup validator: `if not DEBUG and SECRET_KEY == "dev_secret_..."`: raise |
| 2 | MEDIUM | `DATABASE_URL = "sqlite:///./test.db"` — SQLite default not suitable for production | Log warning at startup if using SQLite |
| 3 | MEDIUM | Multiple API key aliases confusing (`ODDS_API_KEY`, `ODDSAPI_API_KEY`, `THE_ODDS_API_KEY`, etc.) | Document priority order; consolidate to single key with aliases |
| 4 | MEDIUM | No validation of numeric ranges on edge thresholds and Kelly fractions | Add `Field(ge=0.01, le=1.0)` validators |
| 5 | LOW | Optional API keys could cause runtime failures without clear error messages | Add startup checks that warn about missing optional keys |

---

## backend/app/database.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `poolclass=NullPool` creates new connection per request — poor performance under load | Use `QueuePool` for production, `NullPool` only for SQLite/testing |
| 2 | MEDIUM | `create_all()` doesn't verify database is accessible — fails silently if DB unreachable | Add `try/except` with `logger.error("Cannot connect to database")` |
| 3 | LOW | Session `get_db()` generator properly uses try/finally — OK | No fix needed |

---

## docker-compose.yml

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No health checks defined for services | Add `healthcheck` blocks for backend and frontend |
| 2 | MEDIUM | No resource limits (CPU, memory) defined | Add `deploy.resources.limits` for each service |
| 3 | LOW | No restart policy specified | Add `restart: unless-stopped` to all services |
| 4 | LOW | No log rotation configured | Add `logging.driver: json-file` with `max-size` and `max-file` |

---

## .env.example

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No documentation of which env vars are required vs optional | Add `# REQUIRED` and `# OPTIONAL` comments |
| 2 | LOW | Missing example values for some keys | Add placeholder examples like `your-api-key-here` |

---

## backend/requirements.txt

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No version pinning for most packages — builds not reproducible | Pin all versions or use `pip freeze > requirements.lock` |
| 2 | MEDIUM | `tensorflow` is a heavy dependency — may not be needed if only using XGBoost | Audit if TensorFlow is actually used; remove if not |
| 3 | LOW | No separation of dev vs production dependencies | Create `requirements-dev.txt` for test/lint dependencies |
| 4 | LOW | `selenium` and `playwright` both included — redundant scraping frameworks | Choose one and remove the other |

---

## backend/pytest.ini

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | LOW | `log_cli_level = WARNING` may hide useful INFO logs during debugging | Consider `INFO` for local development |
| 2 | LOW | No coverage configuration in pytest.ini | Add `--cov=app --cov-report=term-missing` to addopts |

---

## Security Concerns

| # | Severity | Issue | Location | Suggested Fix |
|---|----------|-------|----------|---------------|
| 1 | CRITICAL | Hardcoded database password in source code | `backend/predict_props.py:11` | Use `os.getenv("DATABASE_URL")` |
| 2 | HIGH | `pickle.load()` used for model loading — arbitrary code execution risk | `nba_ml_predictor.py` | Use `joblib.load()` or XGBoost native format |
| 3 | HIGH | No CORS configuration visible — API may be open to all origins | `backend/main.py` | Add `CORSMiddleware` with specific allowed origins |
| 4 | MEDIUM | No rate limiting on API endpoints | All routers | Add `slowapi` rate limiter middleware |
| 5 | MEDIUM | No API authentication required for data-modifying endpoints | `google_sheets.py`, `bets.py` routers | Add API key or JWT middleware |
| 6 | LOW | SQL injection risk in raw queries | `predict_props.py:51` | Use parameterized queries |

---

## Summary

| Area | Issues | Highest Severity |
|------|--------|-----------------|
| settings.py | 5 | HIGH |
| database.py | 3 | MEDIUM |
| docker-compose.yml | 4 | MEDIUM |
| .env.example | 2 | MEDIUM |
| requirements.txt | 4 | MEDIUM |
| pytest.ini | 2 | LOW |
| Security | 6 | CRITICAL |

**Total: 26 issues across configuration & infrastructure**
