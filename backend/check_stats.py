import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)

def check():
    query = """
        SELECT DISTINCT ON (team) team, home_off_eff, home_def_eff, home_power_rank, game_date, league
        FROM (
            SELECT home_team as team, home_off_eff, home_def_eff, home_power_rank, game_date, league 
            FROM model_training_data
            UNION ALL
            SELECT away_team as team, away_off_eff, away_def_eff, away_power_rank, game_date, league 
            FROM model_training_data
        ) t 
        ORDER BY team, game_date DESC
    """
    stats_df = pd.read_sql(query, engine)
    print(f"Total teams with stats: {len(stats_df)}")
    print("\nLeague breakdown:")
    print(stats_df['league'].value_counts())
    
    print("\nSample NBA teams in stats:")
    print(stats_df[stats_df['league'] == 'NBA']['team'].head(10).tolist())
    
    print("\nSample NCAAB teams in stats:")
    print(stats_df[stats_df['league'] == 'NCAAB']['team'].head(10).tolist())

if __name__ == "__main__":
    check()
