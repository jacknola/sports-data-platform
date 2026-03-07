# Security — Code Issues & Suggested Fixes

> Generated from full security review of the codebase.

---

## CRITICAL Issues

### 1. Hardcoded Database Credentials
- **File:** `backend/predict_props.py:11`
- **Issue:** `"postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"` — password exposed in source
- **Risk:** Credential theft, unauthorized database access
- **Fix:**
  ```python
  engine = create_engine(os.getenv("DATABASE_URL"))
  ```
- **Priority:** IMMEDIATE — rotate password after fixing

### 2. Unsafe Pickle Deserialization
- **File:** `backend/app/services/nba_ml_predictor.py`
- **Issue:** `pickle.load()` executes arbitrary code during deserialization
- **Risk:** Remote code execution if model file is tampered with
- **Fix:** Use `joblib.load()` or native model formats (`xgboost.Booster().load_model()`)
- **Priority:** HIGH

---

## HIGH Issues

### 3. Missing CORS Configuration
- **File:** `backend/main.py`
- **Issue:** No `CORSMiddleware` visible — API may accept requests from any origin
- **Risk:** Cross-site request forgery, unauthorized API access
- **Fix:**
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:3000"],  # Production: specific domains
      allow_methods=["GET", "POST", "PUT", "DELETE"],
      allow_headers=["*"],
  )
  ```
- **Priority:** HIGH

### 4. Insecure Default SECRET_KEY
- **File:** `backend/app/config/settings.py`
- **Issue:** `SECRET_KEY = "dev_secret_key_change_in_production"` not enforced
- **Risk:** JWT/session token forgery in production
- **Fix:** Raise `ValueError` on startup if SECRET_KEY unchanged and `DEBUG=False`
- **Priority:** HIGH

### 5. No API Authentication on Sensitive Endpoints
- **Files:** `backend/app/routers/google_sheets.py`, `bets.py`, `analyze.py`
- **Issue:** No auth required to trigger Sheet exports, place bets, or run analysis
- **Risk:** Unauthorized data modification, resource abuse
- **Fix:** Add API key middleware or JWT-based authentication
- **Priority:** HIGH

---

## MEDIUM Issues

### 6. SQL Injection Risk
- **File:** `backend/predict_props.py:51`
- **Issue:** Raw SQL queries without parameterization
- **Risk:** Database manipulation through crafted inputs
- **Fix:** Use parameterized queries: `pd.read_sql(query, engine, params={})`

### 7. No Rate Limiting
- **Files:** All API routers
- **Issue:** No request rate limiting on any endpoint
- **Risk:** Denial of service, API quota exhaustion
- **Fix:** Add `slowapi` middleware with per-IP rate limits

### 8. No Input Validation on Several Endpoints
- **Files:** `analyze.py`, `bets.py`, `props.py`
- **Issue:** Free-form inputs accepted without sanitization
- **Risk:** Injection attacks, unexpected behavior
- **Fix:** Add Pydantic request models with strict validation

### 9. Embedding Model Downloaded at Runtime
- **File:** `backend/app/services/vector_store.py:25`
- **Issue:** `SentenceTransformer("all-MiniLM-L6-v2")` downloads from HuggingFace Hub
- **Risk:** Supply chain attack if model is compromised
- **Fix:** Pin model hash or use local model copy

### 10. No HTTPS Enforcement
- **File:** `docker-compose.yml`
- **Issue:** No TLS/SSL termination configured
- **Risk:** Data interception in transit
- **Fix:** Add nginx reverse proxy with Let's Encrypt SSL

### 11. Redis Without Authentication
- **File:** `backend/app/config/settings.py`
- **Issue:** Default Redis URL has no password: `redis://localhost:6379/0`
- **Risk:** Unauthorized cache access and data poisoning
- **Fix:** Use `redis://:password@host:port/db` format

### 12. Session Management Weaknesses
- **Files:** `ev_calculator.py`, `rag_pipeline.py`
- **Issue:** Database sessions not properly managed — potential resource leaks
- **Risk:** Connection pool exhaustion, data corruption
- **Fix:** Use context managers consistently

---

## LOW Issues

### 13. Verbose Error Messages
- **Files:** Multiple routers return raw exception messages
- **Issue:** Stack traces may leak implementation details
- **Risk:** Information disclosure
- **Fix:** Return generic error messages; log details server-side

### 14. No Security Headers
- **File:** `backend/main.py`
- **Issue:** Missing `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`
- **Risk:** XSS, clickjacking
- **Fix:** Add security headers middleware

### 15. No Audit Logging
- **Files:** All data-modifying endpoints
- **Issue:** No audit trail for bet placements, settings changes, exports
- **Risk:** No accountability for actions, forensics gap
- **Fix:** Add audit log table and middleware

---

## Dependency Vulnerabilities

| Package | Risk | Notes |
|---------|------|-------|
| `tensorflow` | MEDIUM | Large attack surface; verify if actually needed |
| `playwright` + `selenium` | LOW | Both web scraping tools; reduce to one |
| `beautifulsoup4` | LOW | HTML parsing — ensure no XSS from parsed content |
| `openai` | LOW | API key must be protected; ensure no key logging |

---

## Recommendations by Priority

### Immediate (Do Today)
1. ✅ Remove hardcoded database password from `predict_props.py`
2. ✅ Replace `pickle.load()` with safe alternative in `nba_ml_predictor.py`
3. ✅ Add CORS middleware to `main.py`

### This Week
4. Add API authentication to sensitive endpoints
5. Add rate limiting middleware
6. Enforce SECRET_KEY in production mode
7. Add parameterized queries everywhere

### This Month
8. Configure HTTPS/TLS
9. Add security headers
10. Set up Redis authentication
11. Implement audit logging
12. Pin dependency versions

---

## Summary

| Severity | Count | Key Risk |
|----------|-------|----------|
| CRITICAL | 2 | Credential exposure, RCE via pickle |
| HIGH | 3 | Missing auth, CORS, insecure defaults |
| MEDIUM | 7 | SQL injection, rate limiting, input validation |
| LOW | 3 | Error verbosity, headers, audit logs |

**Total: 15 security issues identified**
