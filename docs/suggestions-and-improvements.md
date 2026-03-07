# Additional Suggestions & Improvements

> Architecture, performance, and feature recommendations beyond bug fixes.

---

## 1. RAG Pipeline Improvements (Data Retrieval)

The current `rag_pipeline.py` has limited retrieval quality. Here's a plan for improving data retrieval:

### Current Problems
- Single-pass embedding search without re-ranking
- No chunking strategy — large documents embedded as single vectors
- No hybrid search (only semantic, no keyword matching)
- Embeddings not cached — recalculated on every request
- No relevance feedback loop

### Recommended Architecture
```
Query → Keyword Pre-filter → Semantic Search (Top-K)
      → Cross-Encoder Re-ranker → Contextual Scoring
      → Result Fusion → Response
```

### Implementation Steps
1. **Add document chunking** — Split large texts into 512-token overlapping chunks
2. **Implement hybrid search** — Combine BM25 keyword matching with vector similarity
3. **Add cross-encoder re-ranking** — Use `cross-encoder/ms-marco-MiniLM-L-6-v2` to re-rank top-K results
4. **Cache embeddings in Redis** — Avoid recomputation on identical queries
5. **Add relevance scoring** — Weight results by recency, source authority, and match quality
6. **Implement feedback loop** — Track which retrievals led to successful predictions

---

## 2. ML Prediction Engine (predict_props_v2.py)

### Architecture Recommendation
```
Input Features → Feature Engineering → [XGBoost 35%, LightGBM 30%, Bayesian 35%]
             → Stacked Meta-Learner → Platt Calibration → Edge Detection
             → Kelly Sizing → Output
```

### Key Features to Implement
- Walk-forward TimeSeriesSplit validation (prevent overfitting)
- Negative binomial distribution for extreme performances
- EWMA decay with stat-specific alpha values
- SHAP feature importance tracking
- De-vigging at 4.5% standard overround
- Quarter-Kelly sizing with max 5% single bet cap

---

## 3. Service Architecture Improvements

### Dependency Injection
Replace module-level singleton creation in routers:
```python
# Bad (current):
_ev_calc = EVCalculator()  # Crashes if deps unavailable

# Good (recommended):
def get_ev_calc():
    return EVCalculator()

@router.get("/props")
async def get_props(ev_calc = Depends(get_ev_calc)):
    ...
```

### Error Response Standardization
Create consistent error response format:
```python
class APIError(BaseModel):
    error: str
    code: int
    detail: Optional[str]
    request_id: str

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content=APIError(
            error="internal_error",
            code=500,
            detail=str(exc) if settings.DEBUG else None,
            request_id=request.state.request_id
        ).dict()
    )
```

### Agent Result Standardization
Create `AgentResult` dataclass:
```python
@dataclass
class AgentResult:
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    agent_name: str = ""
```

---

## 4. Performance Improvements

### Database Connection Pooling
```python
# In database.py
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, poolclass=NullPool)
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )
```

### Batch Google Sheets Formatting
The current row-by-row formatting in `google_sheets.py` is extremely slow:
```python
# Collect all format requests, then send once:
requests = []
for row_idx, row_data in enumerate(data):
    requests.append(format_request_for_row(row_idx, row_data))
worksheet.batch_update(requests)  # Single API call
```

### Redis Cache Strategy
```python
# Cache frequently accessed data with appropriate TTLs:
CACHE_CONFIG = {
    "odds_data": 300,        # 5 minutes
    "dvp_rankings": 3600,    # 1 hour
    "team_stats": 86400,     # 24 hours
    "player_baselines": 604800,  # 1 week
    "embeddings": None,      # No expiry
}
```

---

## 5. Monitoring & Observability

### Add Request Logging Middleware
```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} "
        f"duration={duration:.3f}s"
    )
    return response
```

### Add Performance Metrics
Track key metrics:
- API response times (p50, p95, p99)
- Cache hit/miss rates
- External API call latency
- Prediction accuracy (CLV tracking)
- Database query counts per request

---

## 6. Data Quality Improvements

### Add Data Validation Layer
```python
class PropDataValidator:
    """Validate incoming prop data before processing."""
    
    @staticmethod
    def validate_odds(odds: int) -> bool:
        """American odds should be reasonable."""
        return -10000 < odds < 10000 and odds != 0
    
    @staticmethod
    def validate_line(line: float, stat: str) -> bool:
        """Lines should be within reasonable ranges."""
        ranges = {
            "points": (0.5, 60.5),
            "rebounds": (0.5, 25.5),
            "assists": (0.5, 20.5),
            "threes": (0.5, 12.5),
        }
        low, high = ranges.get(stat, (0.5, 100.5))
        return low <= line <= high
```

### Add Stale Data Detection
```python
def check_data_freshness(cache_key: str, max_age_seconds: int) -> bool:
    """Alert if cached data is stale."""
    cached_at = redis.get(f"{cache_key}:timestamp")
    if cached_at and (time.time() - float(cached_at)) > max_age_seconds:
        logger.warning(f"Stale data detected: {cache_key} is {age}s old")
        return False
    return True
```

---

## 7. Code Organization

### Extract Magic Numbers to Constants Module
Create `backend/app/constants.py`:
```python
# Betting Constants
MAX_KELLY_FRACTION = 0.05
QUARTER_KELLY = 0.25
HALF_KELLY = 0.50
DEFAULT_JUICE = -110
DEFAULT_OVERROUND = 0.045  # 4.5%

# Edge Thresholds
EDGE_STRONG = 0.08    # 8%
EDGE_LEAN = 0.05      # 5%
EDGE_MARGINAL = 0.025 # 2.5%

# DvP Tiers
DVP_ELITE = range(1, 6)      # 1-5: Lock-down
DVP_GOOD = range(6, 11)      # 6-10: Tough matchup
DVP_AVERAGE = range(11, 21)  # 11-20: Neutral
DVP_WEAK = range(21, 26)     # 21-25: Soft
DVP_BOTTOM = range(26, 31)   # 26-30: Exploitable

# Cache TTLs (seconds)
CACHE_ODDS = 300           # 5 minutes
CACHE_DVP = 3600           # 1 hour
CACHE_TEAM_STATS = 86400   # 24 hours
```

### Consolidate API Key Configuration
In `settings.py`, document the priority order:
```python
@property
def odds_api_key(self) -> Optional[str]:
    """Get the active Odds API key in priority order."""
    return (
        self.ODDS_API_KEY
        or self.ODDSAPI_API_KEY
        or self.THE_ODDS_API_KEY
        or self.ODDS_API_KEY_FALLBACK
    )
```

---

## Priority Order

| Priority | Category | Effort | Impact |
|----------|----------|--------|--------|
| 1 | Security fixes (credentials, CORS, auth) | Low | Critical |
| 2 | RAG pipeline improvements | Medium | High |
| 3 | Error handling standardization | Medium | High |
| 4 | predict_props_v2.py implementation | High | High |
| 5 | Test coverage improvements | Medium | Medium |
| 6 | Performance optimizations | Medium | Medium |
| 7 | Monitoring & observability | Medium | Medium |
| 8 | Code organization | Low | Low |
