# Sports Data Platform - Export Workflow

## Quick Start (Full Daily Export)

```bash
cd /Users/bb.jr/sports-data-platform

# Option 1: Full automated pipeline (NBA + NCAAB + Props)
python3 backend/export_to_sheets.py

# Option 2: Individual exports
python3 backend/export_to_sheets.py --nba-only    # NBA game predictions only
python3 backend/export_to_sheets.py --props-only  # Player props only
python3 backend/export_to_sheets.py --ncaab-only  # NCAAB only
```

## What Runs During Export

### NBA Export (`--nba-only`)
**No prerequisites - fully automated**
1. Fetches today's games from ESPN/Odds API
2. Gets live team stats from NBA API
3. Runs ML predictions (XGBoost + fallback)
4. Applies O/U reconciliation (compares projected vs market total)
5. Exports to `NBA` tab with game predictions

**Output:** 
- Game predictions with spreads, totals, moneylines
- Projected totals vs market totals
- O/U recommendations (OVER/UNDER/HOLD)
- Edge %, Kelly %, recommended bet sizes

### Props Export (`--props-only`)
**No prerequisites - fully automated**
1. Fetches today's player props from Odds API
2. Runs Bayesian analysis on each prop
3. Queries Qdrant for historical situational context
4. Detects sharp money signals (RLM, Steam, CLV)
5. Exports to 3 tabs:
   - `Props` - All analyzed props grouped by stat type
   - `HighValueProps` - Even odds (-110 to +110) only
   - `FanDuelBets` - FanDuel-specific bets

**Output:**
- Props grouped by category: PTS → REB → AST → 3PM → PRA, etc.
- Section headers: `━━ PTS ━━`, `━━ REB ━━`
- Edge %, Bayesian probability, Kelly sizing
- Sharp signals, situational context from RAG

### NCAAB Export (`--ncaab-only`)
**Requires:** Manual slate configuration in `run_ncaab_analysis.py`
1. Reads hardcoded game slate from `TONIGHT_GAMES`
2. Runs sharp money analysis (RLM, Steam, Line Freeze)
3. Calculates edges against retail books
4. Exports to `NCAAB` tab

**Setup:** Edit `backend/run_ncaab_analysis.py` → `TONIGHT_GAMES` array

## Environment Requirements

### Required (.env file)
```bash
GOOGLE_SPREADSHEET_ID=1Ape6MIzwQeJEBApRyyXjz9YSrZYyBWV2S6xP__IpWs0
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json
ODDS_API_KEY=your_odds_api_key
```

### Optional (for full features)
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
QDRANT_URL=http://localhost:6333  # For historical prop context
```

## Manual Workflow (Step-by-Step)

If you want to run analysis separately before export:

```bash
# 1. Generate NBA predictions
python3 backend/run_nba_analysis.py
# Output: Prints predictions, stores in memory

# 2. Generate player props analysis
python3 backend/run_prop_export.py
# Output: Exports to Props, HighValueProps, FanDuelBets tabs

# 3. Generate NCAAB analysis (after configuring slate)
python3 backend/run_ncaab_analysis.py
# Output: Prints sharp money bets, stores in memory

# 4. Export everything to sheets
python3 backend/export_to_sheets.py
# Runs all pipelines + exports to Google Sheets
```

## Troubleshooting

### Google Sheets API Rate Limiting (429 Error)
**Symptom:** `APIError: [429]: Quota exceeded for quota metric 'Write requests'`

**Cause:** Google Sheets API quota is **60 write requests/minute/user**. Each tab makes multiple write requests (data + formatting), so 11 tabs can exceed this.

**Solution:** Export pipeline includes **3-second delays** between tabs (11 tabs × 3s = 33s total). This ensures each tab's ~5 write requests stay under the 60/min limit.

**If errors persist:**
1. Wait 60 seconds before retrying (quota resets every minute)
2. Increase delay: edit `google_sheets.py` line 1021+, change `time.sleep(3.0)` to `time.sleep(5.0)`
3. Run exports separately: `--nba-only`, `--props-only`, `--ncaab-only`
4. Check for other processes using the same Google service account

### "No games found"
- NBA: Check if games are scheduled today (ESPN API)
- Props: Check Odds API credits/limits
- NCAAB: Verify `TONIGHT_GAMES` is configured in `run_ncaab_analysis.py`

### "Google Sheets not configured"
- Verify `GOOGLE_SPREADSHEET_ID` in `.env`
- Check service account JSON path exists
- Ensure service account has edit access to spreadsheet

### "Odds API rate limit"
- Check remaining credits: `echo $ODDS_API_KEY`
- Free tier: 500 requests/month
- Cached responses last 10 minutes

### O/U recommendations showing blank
- Requires market total from Odds API
- Games from ESPN fallback (no odds) won't have O/U rec
- Check if Odds API returned total lines for the games

## Recent Fixes (2026-03-04)

✅ **O/U Recommendation Bug** - Fixed hardcoded "OVER" logic
- Now compares projected total vs market total
- Correctly shows UNDER when projection < line
- Scales probability based on point difference

✅ **Props Categorization** - Grouped by stat type
- Section headers for each category
- Order: PTS → REB → AST → 3PM → combos → defensive stats

✅ **All 260 tests passing** - Export pipeline verified working
