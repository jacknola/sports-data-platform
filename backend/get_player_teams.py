import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
try:
    query = """
        SELECT DISTINCT ON (player_id) player_id, team_id, game_date 
        FROM player_game_logs 
        ORDER BY player_id, game_date DESC 
        LIMIT 10
    """
    df = pd.read_sql(query, engine)
    print(df)
except Exception as e:
    print(f"Error: {e}")
