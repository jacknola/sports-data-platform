import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
query = """
    SELECT team_id, count(*) as log_count 
    FROM player_game_logs 
    GROUP BY team_id 
    ORDER BY log_count DESC 
    LIMIT 10
"""
print(pd.read_sql(query, engine))
