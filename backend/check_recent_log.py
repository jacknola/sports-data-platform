import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
print(pd.read_sql("SELECT max(game_date) FROM player_game_logs", engine))
