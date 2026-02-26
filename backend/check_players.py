import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
try:
    df = pd.read_sql("SELECT count(*) FROM player_stats_table", engine)
    print(f"player_stats_table count: {df.iloc[0,0]}")
    df_sample = pd.read_sql("SELECT * FROM player_stats_table LIMIT 5", engine)
    print("\nSample:")
    print(df_sample)
except Exception as e:
    print(f"Error: {e}")
