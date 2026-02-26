import pandas as pd
from sqlalchemy import create_engine
from loguru import logger
import os

# 1. Database Connection (Your Postgres Config)
DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)

# 2. Path to your 'ncaab' subfolder
NCAAB_PATH = os.path.join("data", "ncaab") 

def import_ncaab():
    try:
        logger.info(f"Reading NCAAB CSV files from '{NCAAB_PATH}'...")
        
        # Load Teams mapping and Season Results
        teams_file = os.path.join(NCAAB_PATH, "MTeams.csv")
        results_file = os.path.join(NCAAB_PATH, "MRegularSeasonCompactResults.csv")
        
        if not os.path.exists(teams_file) or not os.path.exists(results_file):
            logger.error("Could not find MTeams.csv or MRegularSeasonCompactResults.csv in data/ncaab/")
            return

        teams_df = pd.read_csv(teams_file)
        results_df = pd.read_csv(results_file)
        
        # Create mapping: ID -> Name
        team_map = dict(zip(teams_df['TeamID'], teams_df['TeamName']))
        
        logger.info(f"Transforming {len(results_df)} NCAAB games...")

        ncaab_rows = []
        for _, row in results_df.iterrows():
            w_name = team_map.get(row['WTeamID'], "Unknown")
            l_name = team_map.get(row['LTeamID'], "Unknown")
            
            # WLoc: H=Home, A=Away, N=Neutral
            if row['WLoc'] == 'H':
                home, away = w_name, l_name
                h_score, a_score = row['WScore'], row['LScore']
            elif row['WLoc'] == 'A':
                home, away = l_name, w_name
                h_score, a_score = row['LScore'], row['WScore']
            else: # Neutral
                home, away = w_name, l_name
                h_score, a_score = row['WScore'], row['LScore']

            ncaab_rows.append({
                "game_date": pd.to_datetime(f"{row['Season']}-01-01"), # Placeholder for training
                "season": int(row['Season']),
                "home_team": home.lower(),
                "away_team": away.lower(),
                "home_score": int(h_score),
                "away_score": int(a_score),
                "total_score": int(h_score + a_score),
                "margin": int(h_score - a_score),
                "source": "kaggle_ncaab",
                "external_line_id": f"ncaab_{row['Season']}_{row['DayNum']}_{row['WTeamID']}_{row['LTeamID']}"
            })

        # Convert to DataFrame and upload to Postgres
        df_to_save = pd.DataFrame(ncaab_rows)
        
        # 'append' adds these to your 23k NBA records
        df_to_save.to_sql('historical_game_lines', engine, if_exists='append', index=False)
        
        logger.success(f"Successfully added {len(df_to_save)} NCAAB games to your Postgres database!")

    except Exception as e:
        logger.error(f"Import failed: {e}")

if __name__ == "__main__":
    import_ncaab()