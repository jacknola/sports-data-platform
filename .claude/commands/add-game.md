Add a new game to the NCAAB slate in backend/run_ncaab_analysis.py.

Collect the following information from the user (ask for anything not provided):

**Required fields:**
- Home team (full name, e.g. "Kansas Jayhawks")
- Away team (full name, e.g. "Baylor Bears")
- Conference (e.g. "Big 12", "SEC", "ACC", "Big Ten", "Big East", "WCC", "Mountain West")
- Pinnacle home spread odds (American, e.g. -108)
- Pinnacle away spread odds (American, e.g. -108)
- Retail home spread odds (American, e.g. -110)
- Retail away spread odds (American, e.g. -110)
- Spread line from home perspective (negative = home favored, e.g. -3.5)
- Opening spread (e.g. -2.5)
- Home ticket % (decimal, e.g. 0.71 for 71%)
- Home money % (decimal, e.g. 0.44 for 44%)
- Model home win probability (KenPom-based, decimal, e.g. 0.567)
- Notes (brief description of the line move story)

Then generate a game_id using the format: `NCAAB_YYYYMMDD_NN` where NN is the next sequential number.

Read the file backend/run_ncaab_analysis.py, find the TONIGHT_GAMES list, and append the new game entry BEFORE the closing `]` of the list.

Format exactly like existing entries:
```python
    {
        'game_id': 'NCAAB_20260222_NN',
        'home': 'Home Team Name',
        'away': 'Away Team Name',
        'conference': 'Conference',
        'pinnacle_home_odds': -108,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -110,
        'retail_away_odds': -110,
        'spread': -3.5,
        'open_spread': -2.5,
        'home_ticket_pct': 0.71,
        'home_money_pct': 0.44,
        'model_home_prob': 0.567,
        'notes': 'Description of line movement and sharp signals.',
    },
```

After adding, confirm the game was added and offer to run /run-analysis to see updated results.
