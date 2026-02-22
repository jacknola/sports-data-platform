Start a fresh slate for a new date by clearing TONIGHT_GAMES in run_ncaab_analysis.py.

Ask the user: "What date is the new slate for? (YYYY-MM-DD)"

Then:
1. Read `backend/run_ncaab_analysis.py`
2. Replace the TONIGHT_GAMES list with an empty list and update the date in the module docstring
3. Update the docstring date at the top of the file

Empty slate template:
```python
TONIGHT_GAMES = [
    # Add games with /add-game or manually using the format below:
    # {
    #     'game_id': 'NCAAB_YYYYMMDD_01',
    #     'home': 'Home Team',
    #     'away': 'Away Team',
    #     'conference': 'Big 12',
    #     'pinnacle_home_odds': -108,
    #     'pinnacle_away_odds': -108,
    #     'retail_home_odds': -110,
    #     'retail_away_odds': -110,
    #     'spread': -3.5,
    #     'open_spread': -3.5,
    #     'home_ticket_pct': 0.60,
    #     'home_money_pct': 0.55,
    #     'model_home_prob': 0.55,
    #     'notes': 'Notes on line movement.',
    # },
]
```

After clearing, confirm and prompt: "Slate cleared for [DATE]. Use /add-game to add tonight's matchups."
