import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)

def find():
    teams = ['nop', 'uta', 'mia', 'phi', 'orl', 'hou', 'ind', 'cha', 'pelicans', 'jazz', 'heat', 'magic', 'pacers', 'hornets']
    for t in teams:
        query = f"SELECT league, count(*) FROM model_training_data WHERE home_team ILIKE '%%{t}%%' OR away_team ILIKE '%%{t}%%' GROUP BY league"
        res = pd.read_sql(query, engine)
        if not res.empty:
            print(f"Found match for '{t}':")
            print(res)
            # Find exact name
            exact = pd.read_sql(f"SELECT DISTINCT home_team FROM model_training_data WHERE home_team ILIKE '%%{t}%%' LIMIT 1", engine)
            print(f"Exact name: {exact.iloc[0,0]}")

if __name__ == "__main__":
    find()
