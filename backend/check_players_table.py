import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
try:
    df = pd.read_sql("SELECT count(*) FROM players", engine)
    print(f"Total players in DB: {df.iloc[0,0]}")
    sample = pd.read_sql("SELECT name, team_id FROM players LIMIT 5", engine)
    print(sample)
except Exception as e:
    print(f"Error: {e}")
