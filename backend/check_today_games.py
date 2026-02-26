import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
try:
    # Check for games today or tomorrow
    query = "SELECT * FROM games WHERE game_date >= '2026-02-26' AND game_date <= '2026-02-27' LIMIT 10"
    df = pd.read_sql(query, engine)
    print(f"Games found for today/tomorrow: {len(df)}")
    if not df.empty:
        print(df[['home_team', 'away_team', 'game_date', 'status']])
except Exception as e:
    print(f"Error: {e}")
