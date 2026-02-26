import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
print("Teams table names:")
print(pd.read_sql("SELECT name FROM teams LIMIT 10", engine))
print("\nPlayer game logs scenario sample:")
print(pd.read_sql("SELECT scenario FROM player_game_logs LIMIT 10", engine))
