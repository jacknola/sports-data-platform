# Plan: Model Output Bug Fixes
**Created:** 2026-02-27  
**Status:** Ready for /start-work  
**Scope:** Fix 10 confirmed bugs across NBA, NCAAB, and Props pipelines  
**Goal:** Eliminate broken defaults (50/50 win %, 0 proj spread, empty AdjOE/BPI, no picks, negative-edge props, recycled history) so all Sheets exports reflect real model outputs.

---

## Constraints (Non-Negotiable)
- **NO** changes to `bayesian.py`, `multivariate_kelly.py`, `sharp_money_detector.py`
- **NO** new dependencies
- **NO** schema changes
- **NO** Full Kelly — all sizing remains Half or Quarter Kelly
- `from loguru import logger` — no `print()` in services
- Absolute imports: `from app.services.X import Y`
- Type hints on all new/modified function signatures
- Run `pytest backend/` after every wave — all 262 tests must pass

---

## Wave 1 — NBA: Fix True Win % + Projected Spread (Root Cause)

### Task 1.1 — Fix `home_win_probability` key mismatch in `google_sheets.py`
**File:** `backend/app/services/google_sheets.py`  
**Line:** 276  
**Root cause:** `export_nba()` reads `p.get("home_win_probability", 0.5)` but `NBAMLPredictor.predict_game()` returns `{"moneyline_prediction": {"home_win_prob": ...}}` (nested). The flat key `home_win_probability` is never set → always defaults to 0.5.

**Change:**
```python
# BEFORE (line 276)
home_prob = p.get("home_win_probability", 0.5)

# AFTER
home_prob = p.get("moneyline_prediction", {}).get("home_win_prob", 0.5)
```

**Also update away_prob (line 277):**
```python
# AFTER
away_prob = p.get("moneyline_prediction", {}).get("away_win_prob", 1 - home_prob)
```

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
import asyncio
from app.services.nba_ml_predictor import NBAMLPredictor
predictor = NBAMLPredictor()
pred = asyncio.run(predictor.predict_game('Milwaukee Bucks', 'New York Knicks', {
    'odds': {'home_odds': 251, 'away_odds': -300},
    'home_off_rating': 115.0, 'home_def_rating': 109.0,
    'away_off_rating': 118.0, 'away_def_rating': 107.0,
    'home_win_pct': 0.52, 'away_win_pct': 0.65
}))
hp = pred.get('moneyline_prediction', {}).get('home_win_prob', -1)
assert 0.05 < hp < 0.95 and hp != 0.5, f'FAIL: home_win_prob={hp}'
print(f'PASS: home_win_prob={hp:.4f}')
"
```

**Note:** Bug #2 (Proj Spread = 0) auto-fixes when this is fixed. `(home_prob - 0.5) * -26` now uses real probability.

---

### Task 1.2 — Verify `book` field is correctly populated (or fix)
**File:** `backend/app/services/nba_ml_predictor.py`  
**Metis finding:** `predict_today_games()` line ~491 sets `best_book_used` and line ~562 sets `pred["book"] = game.get("book", "")`. The field may only be blank for ESPN-only games with no odds data — which is expected.

**Action:** Search for all `pred["book"]` assignments in `nba_ml_predictor.py`. If `book` is never populated even when Pinnacle odds ARE present, add `pred["book"] = game.get("best_book_used", game.get("book", "pinnacle"))`. If it IS populated from odds data, no change needed.

**AST grep to verify:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
import ast, pathlib
src = pathlib.Path('app/services/nba_ml_predictor.py').read_text()
lines = [i+1 for i,l in enumerate(src.splitlines()) if 'book' in l.lower() and ('pred[' in l or 'book_used' in l)]
print('book-related lines:', lines)
"
```

**QA:** Run `predict_today_games('nba')` with live data and verify `pred['book']` is non-empty when Pinnacle odds are available.

---

### Task 1.3 — Run tests after Wave 1
```bash
cd backend && source venv/bin/activate && pytest -x --tb=short
```
Assert: all previously passing tests still pass. Any test that was asserting `home_win_probability == 0.5` must be updated to use the nested key.

---

## Wave 2 — NCAAB Data: Fix 50/50 True Prob + AdjOE/BPI + Game Profiler Keys

### Task 2.1 — Fix Pinnacle spread default → devig fallback
**File:** `backend/run_ncaab_analysis.py`  
**Lines:** 251-254 (defaults) and 588-590 (devig call)  
**Root cause:** When Pinnacle has no spread market, `pinnacle_home = -110` and `pinnacle_away = -110` are used. `devig(-110, -110)` = exactly 50/50. For low-major NCAAB, Pinnacle rarely offers spread markets.

**Change in `_parse_bookmaker_spreads()`:** After the bookmaker loop, if `not found_pinnacle`, check if any sharp book offered a **moneyline** market. If yes, store those ML odds in `pinnacle_home_ml`/`pinnacle_away_ml`. Return a new boolean flag `has_sharp_spread`.

```python
# ADD to _parse_bookmaker_spreads() return dict
"has_sharp_spread": found_pinnacle,
"pinnacle_home_ml": pinnacle_home_ml,  # new: from moneyline market if no spread
"pinnacle_away_ml": pinnacle_away_ml,
```

**Change in `run_analysis()` loop** (lines 588-590): Use ML odds for devig when no sharp spread exists:
```python
# BEFORE
true_home_prob, true_away_prob = devig(
    game["pinnacle_home_odds"], game["pinnacle_away_odds"]
)

# AFTER
if game.get("has_sharp_spread"):
    true_home_prob, true_away_prob = devig(
        game["pinnacle_home_odds"], game["pinnacle_away_odds"]
    )
elif game.get("pinnacle_home_ml") and game.get("pinnacle_away_ml"):
    # No sharp spread market — fall back to moneyline devig
    true_home_prob, true_away_prob = devig(
        game["pinnacle_home_ml"], game["pinnacle_away_ml"]
    )
    logger.debug(f"Using moneyline devig for {game['home']} vs {game['away']} (no Pinnacle spread)")
else:
    # No Pinnacle data at all — use model-only estimate
    model_p = game["model_home_prob"]
    true_home_prob, true_away_prob = model_p, 1.0 - model_p
    logger.debug(f"Using model-only prob for {game['home']} vs {game['away']} (no Pinnacle data)")
```

**Also update `get_live_ncaab_games()`** to extract moneyline market odds from Pinnacle in `_parse_bookmaker_spreads()`:
```python
# Inside the bookmaker loop in _parse_bookmaker_spreads(),
# add moneyline market extraction alongside spreads:
pinnacle_home_ml = -110
pinnacle_away_ml = -110

# In the loop where book_key in sharp_books:
if market.get("key") == "h2h":  # moneyline
    for out in market.get("outcomes", []):
        if out["name"] == home_team or out["name"].lower() in home_team.lower():
            pinnacle_home_ml = round(out.get("price", -110))
        else:
            pinnacle_away_ml = round(out.get("price", -110))
```

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
from run_ncaab_analysis import _parse_bookmaker_spreads
# Game with Pinnacle moneyline but NO spread market
fake_game = {'bookmakers': [{
    'key': 'pinnacle',
    'markets': [{'key': 'h2h', 'outcomes': [
        {'name': 'Cornell', 'price': -150},
        {'name': 'Yale', 'price': 130}
    ]}]
}]}
result = _parse_bookmaker_spreads(fake_game, 'Cornell')
assert not result['has_sharp_spread'], 'FAIL: should have no sharp spread'
assert result['pinnacle_home_ml'] == -150, f'FAIL: ML odds wrong: {result}'
print(f'PASS: has_sharp_spread=False, pinnacle_home_ml={result[\"pinnacle_home_ml\"]}')
"
```

---

### Task 2.2 — Fix NCAABStatsService silent failure
**File:** `backend/app/services/ncaab_stats_service.py`  
**Root cause:** ESPN BPI scraper uses fragile regex HTML parsing. On failure → `return {}` → all efficiency cells blank.

**Actions:**
1. Read `ncaab_stats_service.py` fully to understand current scraper and `fetch_all_team_stats()`.
2. Add structured logging for each team fetch attempt: log team names found vs. expected.
3. Add retry logic (up to 2 retries with 2s delay) for the HTTP fetch.
4. Ensure the return format matches keys the consumer expects: `{"Team Name": {"AdjOE": float, "AdjDE": float, "BPI": float}}`.
5. Add fallback: if ESPN BPI fetch fails, use Odds-API-implied spread-based efficiency proxy: `AdjOE = 106.0, AdjDE = 106.0` (league average) so cells show a value rather than blank.

**Return dict format verification:** Check `run_ncaab_analysis.py:403-404`:
```python
h_stats = get_stats(matched_odds.get("home_team", home))
a_stats = get_stats(matched_odds.get("away_team", away))
```
Keys used downstream: `h_stats["AdjOE"]`, `h_stats["AdjDE"]`, `h_stats.get("BPI", "")`. Ensure ncaab_stats_service returns exactly these keys.

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
import asyncio
from app.services.ncaab_stats_service import NCAABStatsService
svc = NCAABStatsService()
stats = asyncio.run(svc.fetch_all_team_stats())
print(f'Teams fetched: {len(stats)}')
if stats:
    sample = next(iter(stats.items()))
    assert 'AdjOE' in sample[1], f'FAIL: AdjOE missing from stats: {sample}'
    assert 'AdjDE' in sample[1], f'FAIL: AdjDE missing from stats: {sample}'
    print(f'PASS: sample team={sample[0]}, AdjOE={sample[1][\"AdjOE\"]}')
else:
    print('WARN: No stats fetched (API may be unavailable) — verify retry logic added')
"
```

---

### Task 2.3 — Fix game_profiler key mismatch (NCAAB dict uses `home`/`away`)
**File:** `backend/app/services/game_profiler.py`  
**Lines:** 16-17  
**Root cause:** `generate_description()` reads `game_data.get("home_team", "Home")` but NCAAB game dicts (from `run_ncaab_analysis.py:421-422`) use keys `home` and `away`. Every NCAAB query generates description "between Away and Home" → identical embeddings → same 2 games returned from Qdrant for every game.

**Change:**
```python
# BEFORE (game_profiler.py lines 16-17)
home = game_data.get("home_team", "Home")
away = game_data.get("away_team", "Away")

# AFTER — try both key patterns
home = game_data.get("home_team") or game_data.get("home", "Home")
away = game_data.get("away_team") or game_data.get("away", "Away")
```

**Also check** lines below 17 for any other `home_team`/`away_team` references in `game_profiler.py` — apply same dual-key pattern to all.

**Note:** Fixing this also fixes Bug #9 (situational context mismatch) as a free side effect — unique game descriptions → unique Qdrant results → relevant historical context.

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
from app.services.game_profiler import GameProfiler
profiler = GameProfiler()
# NCAAB-style dict
desc_ncaab = profiler.generate_description({'home': 'Duke Blue Devils', 'away': 'UNC Tar Heels', 'spread': -7.0})
assert 'Duke' in desc_ncaab and 'UNC' in desc_ncaab, f'FAIL ncaab: {desc_ncaab}'
# NBA-style dict (should still work)
desc_nba = profiler.generate_description({'home_team': 'Milwaukee Bucks', 'away_team': 'New York Knicks', 'spread': -3.0})
assert 'Milwaukee' in desc_nba, f'FAIL nba: {desc_nba}'
print(f'PASS ncaab: {desc_ncaab[:60]}...')
print(f'PASS nba:   {desc_nba[:60]}...')
"
```

---

### Task 2.4 — Run tests after Wave 2
```bash
cd backend && source venv/bin/activate && pytest -x --tb=short
```
Expect: `test_game_profiler.py` tests may need updating to use dual-key inputs.

---

## Wave 3 — NCAAB Export: Fix Double-Suffix Bets Lookup

### Task 3.1 — Fix double `_HOME`/`_AWAY` suffix in bets_lookup
**File:** `backend/app/services/google_sheets.py`  
**Lines:** 391-393 and 411-412  
**Root cause:** `BettingOpportunity.game_id` is already set with `_HOME`/`_AWAY` suffix at `run_ncaab_analysis.py:634,649`. When `export_ncaab()` builds `bets_lookup`, it appends the suffix AGAIN → keys like `NCAAB_TeamA_TeamB_HOME_HOME` which never match `gid + '_HOME'` (`NCAAB_TeamA_TeamB_HOME`).

**Change:**
```python
# BEFORE (lines 391-393)
for b in bets:
    bets_lookup[b.get("game_id", "") + "_HOME"] = b
    bets_lookup[b.get("game_id", "") + "_AWAY"] = b

# AFTER — game_id from BettingOpportunity already includes suffix
for b in bets:
    bets_lookup[b.get("game_id", "")] = b
```

**Also change lookup (lines 411-412):**
```python
# BEFORE
bet = bets_lookup.get(gid + "_HOME") or bets_lookup.get(gid + "_AWAY", {})

# AFTER
bet = bets_lookup.get(gid + "_HOME") or bets_lookup.get(gid + "_AWAY") or {}
```

**Note:** `gid` at line 401 = `game.get("game_id", "")` which is the BASE game id (e.g. `NCAAB_TeamA_TeamB`). The bets have `NCAAB_TeamA_TeamB_HOME`. So the lookup `bets_lookup.get(gid + "_HOME")` becomes `bets_lookup.get("NCAAB_TeamA_TeamB_HOME")` which now correctly matches the key.

**QA:**
```python
# Inline unit test — run directly
bets = [
    {"game_id": "NCAAB_DukeBlueDevils_UNCTarHeels_HOME", "side": "Duke", "portfolio_fraction_pct": 3.5, "bet_size_$": 3.50},
]
bets_lookup = {}
for b in bets:
    bets_lookup[b.get("game_id", "")] = b

gid = "NCAAB_DukeBlueDevils_UNCTarHeels"
bet = bets_lookup.get(gid + "_HOME") or bets_lookup.get(gid + "_AWAY") or {}
assert bet.get("side") == "Duke", f"FAIL: lookup missed, bet={bet}"
print(f"PASS: found bet side={bet['side']}, fraction={bet['portfolio_fraction_pct']}%")
```

---

### Task 3.2 — Run tests after Wave 3
```bash
cd backend && source venv/bin/activate && pytest -x --tb=short
```

---

## Wave 4 — Props: Fix Negative-Edge Export + Pinnacle Odds + RAG Query

### Task 4.1 — Filter negative-edge props from Sheets export
**File:** `backend/app/services/google_sheets.py`  
**Lines:** 171-174 in `export_props()`  
**Root cause:** `all_props = prop_data.get("props", [])` returns ALL analyzed props including negative-edge ones. No filter exists before writing to Sheets.

**Change:**
```python
# BEFORE (lines 171-174)
all_props = prop_data.get("props", [])
all_props.sort(
    key=lambda x: x.get("bayesian_edge", 0), reverse=True
)

# AFTER — prefer pre-filtered best_props; fall back to props with non-negative edge only
all_props = prop_data.get("best_props") or [
    p for p in prop_data.get("props", [])
    if p.get("bayesian_edge", 0) >= 0
]
all_props.sort(
    key=lambda x: x.get("bayesian_edge", 0), reverse=True
)
```

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
import inspect
from app.services.google_sheets import GoogleSheetsService
src = inspect.getsource(GoogleSheetsService.export_props)
assert 'best_props' in src or 'bayesian_edge' in src and '>= 0' in src, 'FAIL: no edge filter'
print('PASS: export_props contains edge filter')
"
```

---

### Task 4.2 — Add Pinnacle to PROP_BOOKMAKERS
**File:** `backend/app/services/sports_api.py`  
**Lines:** 700-703  
**Root cause:** `PROP_BOOKMAKERS` is a comma-separated string used in the Odds API request. Pinnacle is NOT included → no Pinnacle prop lines fetched → no +200 underdog odds.

**Change:**
```python
# BEFORE (sports_api.py ~line 700-703)
PROP_BOOKMAKERS = (
    "draftkings,fanduel,betmgm,williamhill_us,"
    "pointsbetus,betrivers,unibet_us,superbook"
)

# AFTER — add pinnacle
PROP_BOOKMAKERS = (
    "pinnacle,draftkings,fanduel,betmgm,williamhill_us,"
    "pointsbetus,betrivers,unibet_us,superbook"
)
```

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
from app.services.sports_api import SportsAPIService
assert 'pinnacle' in SportsAPIService.PROP_BOOKMAKERS.lower(), \
    f'FAIL: pinnacle not in PROP_BOOKMAKERS: {SportsAPIService.PROP_BOOKMAKERS}'
print('PASS: pinnacle in PROP_BOOKMAKERS')
"
```

---

### Task 4.3 — Relax `books_offering` filter for Pinnacle props
**File:** `backend/app/routers/props.py`  
**Lines:** ~125-131  
**Root cause:** `books_offering >= 2` filter blocks any prop where only 1 book offers a line. Adding Pinnacle helps, but a Pinnacle-only line (no retail cross-validation) still gets blocked.

**Change:** Allow lines where `books_offering >= 1` AND at least one offering book is in the sharp books set:
```python
# BEFORE
if prop.get("books_offering", 0) < 2:
    continue

# AFTER
SHARP_BOOKS = {"pinnacle", "circa", "betonlineag", "lowvig"}
books_cnt = prop.get("books_offering", 0)
offering_books = set(prop.get("offering_books", []))
has_sharp = bool(offering_books & SHARP_BOOKS)
if books_cnt < 2 and not has_sharp:
    continue
```

**Prerequisite:** Verify `prop` dict contains `offering_books` list (or similar) from the API response. If not, `offering_books` will be empty set and only `books_cnt >= 2` filter applies (safe fallback).

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
# Verify filter logic
SHARP_BOOKS = {'pinnacle', 'circa', 'betonlineag', 'lowvig'}
props = [
    {'books_offering': 1, 'offering_books': ['pinnacle'], 'player': 'SGA'},  # should pass
    {'books_offering': 1, 'offering_books': ['fanduel'], 'player': 'Test'},  # should fail
    {'books_offering': 2, 'offering_books': ['fanduel', 'draftkings'], 'player': 'LeBron'},  # should pass
]
results = []
for p in props:
    books_cnt = p.get('books_offering', 0)
    offering = set(p.get('offering_books', []))
    has_sharp = bool(offering & SHARP_BOOKS)
    passes = books_cnt >= 2 or has_sharp
    results.append((p['player'], passes))
    print(f'{p[\"player\"]}: books={books_cnt}, sharp={has_sharp} -> {\"PASS\" if passes else \"BLOCK\"}')
assert results[0][1] == True, 'SGA (Pinnacle-only) should pass'
assert results[1][1] == False, 'FanDuel-only should be blocked'
assert results[2][1] == True, '2-book should pass'
print('PASS: filter logic correct')
"
```

---

### Task 4.4 — Enrich RAG query string for props similarity
**File:** `backend/app/routers/props.py`  
**Lines:** 472-475  
**Root cause:** Query string is `"{player_name} vs {opponent} {stat_type}"`. Name tokens dominate the SentenceTransformer embedding → Shai Gilgeous-Alexander matches Nickeil Alexander-Walker by name similarity.

**Change:** Enrich query with role-defining features instead of primarily player name:
```python
# BEFORE (props.py lines 472-475)
analogs = _similarity.vector_store.search_similar_scenarios(
    description=f"{prop['player_name']} vs {prop['opponent']} {prop['stat_type']}",
    collection=settings.QDRANT_COLLECTION_PLAYERS, limit=3
)

# AFTER — stat-role-driven query, name as secondary
stat_label = prop.get("stat_type", "")
line_val = prop.get("line", 0)
team = prop.get("team", "")
opp = prop.get("opponent", "")
role_query = (
    f"{stat_label} line {line_val} "
    f"{'guard' if stat_label in ('assists','threes') else 'big' if stat_label in ('rebounds','blocks') else 'scorer'} "
    f"vs {opp} {team} context"
)
analogs = _similarity.vector_store.search_similar_scenarios(
    description=role_query,
    collection=settings.QDRANT_COLLECTION_PLAYERS, limit=3
)
logger.debug(f"RAG query for {prop['player_name']} {stat_label}: '{role_query}'")
```

**QA:**
```bash
cd backend && PYTHONPATH=$(pwd) python -c "
# Verify query enrichment doesn't break when fields missing
prop = {'player_name': 'Shai Gilgeous-Alexander', 'stat_type': 'assists', 'line': 6.5, 'team': 'OKC Thunder', 'opponent': 'Denver Nuggets'}
stat_label = prop.get('stat_type', '')
line_val = prop.get('line', 0)
team = prop.get('team', '')
opp = prop.get('opponent', '')
role_query = (
    f\"{stat_label} line {line_val} \"
    f\"{'guard' if stat_label in ('assists','threes') else 'big' if stat_label in ('rebounds','blocks') else 'scorer'} \"
    f\"vs {opp} {team} context\"
)
assert 'Shai' not in role_query, f'FAIL: player name should not dominate query: {role_query}'
assert 'assists' in role_query, f'FAIL: stat type missing: {role_query}'
assert '6.5' in role_query, f'FAIL: line value missing: {role_query}'
print(f'PASS: query={role_query}')
"
```

---

### Task 4.5 — Run tests after Wave 4
```bash
cd backend && source venv/bin/activate && pytest -x --tb=short
```

---

## Wave 5 — Final Verification

### Task 5.1 — End-to-end NBA pipeline smoke test
```bash
cd backend && source venv/bin/activate && python run_nba_analysis.py 2>&1 | grep -E "(True prob|home_win_prob|Proj Spread|PASS|FAIL|Error)"
# Assert: no 50/50 probabilities in output for games with ML available
```

### Task 5.2 — End-to-end NCAAB pipeline smoke test
```bash
cd backend && source venv/bin/activate && python run_ncaab_analysis.py 2>&1 | grep -E "(True prob|model_home_prob|AdjOE|BPI|Pick|PASS|FAIL|Error)"
# Assert: True prob shows differentiated values (not all 50/50)
# Assert: AdjOE shown for at least some teams (or WARN if ESPN BPI unavailable)
```

### Task 5.3 — End-to-end props smoke test
```bash
cd backend && source venv/bin/activate && python run_prop_export.py 2>&1 | head -50
# Assert: No negative edge % in output
# Assert: At least one prop with odds > +200 if Pinnacle has such lines today
```

### Task 5.4 — Full Sheets export smoke test (dry run structure check)
```bash
cd backend && source venv/bin/activate && python export_to_sheets.py --test
# Assert: connection succeeds, tabs exist
```

### Task 5.5 — Full regression suite
```bash
cd backend && source venv/bin/activate && pytest --tb=short 2>&1 | tail -10
# Assert: all previously passing tests pass (262+ tests)
```

---

## Execution Order & Dependencies

```
Wave 1 (NBA)       → No dependencies. Start here.
Wave 2 (NCAAB)     → No dependencies on Wave 1. Can run in parallel.
Wave 3 (NCAAB exp) → DEPENDS on Wave 2 completing (needs to understand bet structure)
Wave 4 (Props)     → No dependencies on Waves 1-3. Can run in parallel with Wave 1.
Wave 5 (Verify)    → DEPENDS on all prior waves complete.
```

**Parallel execution plan:**
- Agent A: Wave 1 (NBA — 2 tasks)
- Agent B: Waves 2+3 (NCAAB — 5 tasks)  
- Agent C: Wave 4 (Props — 4 tasks)
- All converge at Wave 5

---

## Bug Registry

| #   | Bug                                        | File                          | Lines        | Status    | Wave |
| --- | ------------------------------------------ | ----------------------------- | ------------ | --------- | ---- |
| 1   | NBA home_win_probability key mismatch      | google_sheets.py              | 276          | READY     | 1    |
| 2   | NBA proj_spread = 0                        | google_sheets.py              | 303-305      | AUTO-FIX  | 1    |
| 3   | NBA no trained models                      | nba_ml_predictor.py           | 90-93        | DROPPED   | —    |
| 4   | NBA book field blank                       | nba_ml_predictor.py           | ~562         | VERIFY    | 1    |
| 5   | NCAAB 50/50 true prob (default -110/-110)  | run_ncaab_analysis.py         | 251-254,588  | READY     | 2    |
| 6   | NCAAB AdjOE/BPI empty (stats service)      | ncaab_stats_service.py        | ~177-179     | READY     | 2    |
| 7   | NCAAB double suffix bets_lookup            | google_sheets.py              | 391-412      | READY     | 3    |
| 8   | NCAAB game_profiler key mismatch           | game_profiler.py              | 16-17        | READY     | 2    |
| 9   | NCAAB situational context wrong            | —                             | —            | MERGED→8  | —    |
| 10  | Props negative-edge exported               | google_sheets.py              | 171-174      | READY     | 4    |
| 11  | Props RAG name-similarity matching         | props.py                      | 472-475      | READY     | 4    |
| 12  | Props odds >+200 excluded (no Pinnacle)    | sports_api.py + props.py      | 700-703, 125 | READY     | 4    |

**Active fixes: 9** (Bugs 2, 9 auto-resolved; Bug 3 dropped as existing fallback works; Bug 4 verify-first)

---

## Acceptance Criteria (Overall)

After all waves complete:
1. NBA sheet shows `Home Win %` ≠ 50.0 for games where one team is heavily favored (e.g., -242 favorite should show ~68-72%)
2. NBA sheet shows `Proj Spread` ≠ 0 for all games
3. NCAAB sheet shows `True Home %` ≠ 50.0 for any game with Pinnacle ML data
4. NCAAB sheet shows `AdjOE`/`AdjDE` populated (or explicit fallback value) for all games
5. NCAAB sheet shows `Pick` column populated for any game clearing 2.5% edge threshold
6. NCAAB sheet shows unique historical context per game (not same 2 games repeated)
7. Props sheet shows zero rows with negative `Edge %`
8. Props sheet includes at least one prop with `Odds > +200` on days when Pinnacle offers such lines
9. All 262+ backend tests pass
10. `python backend/export_to_sheets.py --test` succeeds
