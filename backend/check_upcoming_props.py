import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
try:
    df = pd.read_sql("SELECT * FROM historical_player_props WHERE game_date >= '2026-02-26' LIMIT 10", engine)
    print(f"Upcoming props found: {len(df)}")
except Exception as e:
    print(f"Error: {e}")
