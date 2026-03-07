# Backend Agents — Code Issues & Suggested Fixes

> Generated from full codebase review of `backend/app/agents/`.

---

## orchestrator.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | `self.twitter_agent` can be `None` (line 43) but `twitter_agent.execute()` called without null check (line 223) | Add `if self.twitter_agent:` guard before calling `.execute()` |
| 2 | HIGH | `_evaluate_prediction()` always returns `True` — stub implementation (line 356) | Implement actual evaluation comparing prediction vs outcome |
| 3 | MEDIUM | No timeout handling on `await` calls to agents — could hang indefinitely | Add `asyncio.wait_for(coro, timeout=30)` wrappers |
| 4 | MEDIUM | `results["sentiment"][i]` assumes sentiment results match teams count — index mismatch if partial failure | Use `zip()` instead of index-based iteration |
| 5 | MEDIUM | Comment says "Step 3" but sequence doesn't match actual execution order | Renumber steps to match actual flow |
| 6 | LOW | Step 2 appears missing in orchestration flow | Add missing step or fix step numbering |

---

## base_agent.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `agent_id` uses `datetime.now().timestamp()` — collision risk for agents created same millisecond | Use `uuid.uuid4()` for unique IDs |
| 2 | LOW | `_find_similar_mistakes()` and other methods lack return type hints | Add `-> List[Dict[str, Any]]` return types |
| 3 | LOW | No docstring enforcement for abstract methods | Add docstrings to `execute()` and `learn_from_mistake()` abstracts |

---

## analysis_agent.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Typo: `'probabilty_estimation'` should be `'probability_estimation'` (line 115) | Fix spelling — this will never match mistake_type checks |
| 2 | MEDIUM | `was_correct=True` hardcoded — prediction correctness never tracked | Set to `None` initially, update with actual outcome |
| 3 | LOW | `selection.get('id')` could be None — passed to logger without validation | Add `or 'unknown'` fallback in log message |

---

## odds_agent.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Player name matching uses `in` operator — "Smith" matches "Smitherson" (line 82) | Use `rapidfuzz.fuzz.ratio()` with threshold ≥ 85 |
| 2 | MEDIUM | Silent API failure — if API fails and cache misses, returns empty props | Add explicit cache check and log warning when no data available |
| 3 | LOW | Raises `ValueError` for missing fields but caught generically | Let ValueError propagate or handle specifically in caller |

---

## expert_agent.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Inconsistent mistake type naming: `'decision_error'` (line 85) vs other agents | Standardize mistake types across all agents (define enum) |
| 2 | MEDIUM | `self.similarity_service.find_similar_games()` result could be None | Add `if not similar_games: return default_analysis` guard |
| 3 | LOW | No logging of which similar games were found for debugging | Add `logger.debug(f"Found {len(similar_games)} similar games")` |

---

## dvp_agent.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Returns `{"error": str(e)}` instead of raising exception — caller can't distinguish success/failure | Return explicit `success: bool` field or raise `HTTPException` |
| 2 | MEDIUM | `self._analyze_single_player()` expects analyzer state — crashes if not initialized | Add initialization check at start of method |
| 3 | LOW | Error return doesn't log which player/stat was requested | Add context: `f"Failed to analyze {player_name} {stat}: {e}"` |

---

## ncaab_dvp_agent.py

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Checks `if not self.analyzer.team_efficiency:` but doesn't handle fetch failure | Add `try/except` around efficiency data fetch |
| 2 | LOW | `self.analyzer.league_avg_pace` could be `None` if not initialized | Set default value in constructor: `self.league_avg_pace = 100.0` |

---

## Cross-Cutting Agent Issues

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | HIGH | No consistent error reporting pattern across agents | Define `AgentResult` dataclass with `success`, `data`, `error` fields |
| 2 | MEDIUM | Mistake types are free-form strings — easy to introduce typos | Create `MistakeType` enum: `PROBABILITY_ESTIMATION`, `DECISION_ERROR`, etc. |
| 3 | MEDIUM | No agent health monitoring or heartbeat mechanism | Add `is_healthy()` method to base_agent returning status |
| 4 | LOW | Agent learning (`learn_from_mistake`) not tested in unit tests | Add tests for learning/self-correction in each agent |

---

## Summary

| File | Issues | Highest Severity |
|------|--------|-----------------|
| orchestrator.py | 6 | HIGH |
| base_agent.py | 3 | MEDIUM |
| analysis_agent.py | 3 | MEDIUM |
| odds_agent.py | 3 | MEDIUM |
| expert_agent.py | 3 | MEDIUM |
| dvp_agent.py | 3 | MEDIUM |
| ncaab_dvp_agent.py | 2 | MEDIUM |
| Cross-cutting | 4 | HIGH |

**Total: 27 issues across agent system**
