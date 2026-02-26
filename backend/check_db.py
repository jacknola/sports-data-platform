import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)

def check():
    print("Checking model_training_data count...")
    df = pd.read_sql("SELECT league, count(*) FROM model_training_data GROUP BY league", engine)
    print(df)
    
    print("\nSample teams in model_training_data (NBA):")
    df_nba = pd.read_sql("SELECT DISTINCT home_team FROM model_training_data WHERE league = 'NBA' LIMIT 10", engine)
    print(df_nba)

    print("\nSample teams in model_training_data (NCAAB):")
    df_cbb = pd.read_sql("SELECT DISTINCT home_team FROM model_training_data WHERE league = 'NCAAB' LIMIT 10", engine)
    print(df_cbb)

if __name__ == "__main__":
    check()
