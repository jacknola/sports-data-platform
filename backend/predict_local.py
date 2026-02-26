import pandas as pd
import xgboost as xgb
from sqlalchemy import create_engine
from rapidfuzz import process, utils
from loguru import logger

# 1. Database Connection
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")

def get_team_stats(team_name, eff_df):
    """Fuzzy match team name and return their latest stats"""
    if not team_name:
        return None, None
        
    match = process.extractOne(team_name.lower(), eff_df['team'].tolist(), processor=utils.default_process)
    
    # Only return if we have a high-confidence match (score > 60)
    if match and match[1] > 60:
        return eff_df[eff_df['team'] == match[0]].iloc[0], match[0]
    return None, None

def run_manual_prediction(home_name, away_name, league='nba'):
    try:
        # Load the correct model file
        model = xgb.XGBRegressor()
        model_file = f"{league}_model.json"
        model.load_model(model_file)
        
        # Pull latest stats from your Postgres data
        query = """
            SELECT DISTINCT ON (team) 
                team, home_off_eff, home_def_eff, home_power_rank 
            FROM (
                SELECT home_team as team, home_off_eff, home_def_eff, home_power_rank, game_date 
                FROM model_training_data
            ) t 
            ORDER BY team, game_date DESC
        """
        eff_df = pd.read_sql(query, engine)

        # Get stats with the NoneType safety check
        h_stats, h_full = get_team_stats(home_name, eff_df)
        a_stats, a_full = get_team_stats(away_name, eff_df)

        if h_stats is not None and a_stats is not None:
            # Prepare features (must match your model's training columns exactly)
            features = pd.DataFrame([[
                h_stats['home_off_eff'], h_stats['home_def_eff'], 
                a_stats['home_off_eff'], a_stats['home_def_eff'], 
                h_stats['home_power_rank'], a_stats['home_power_rank']
            ]], columns=['home_off_eff', 'home_def_eff', 'away_off_eff', 'away_def_eff', 'home_power_rank', 'away_power_rank'])
            
            prediction = model.predict(features)[0]
            
            # Use .upper() only now that we know they aren't None
            h_display = str(h_full).upper()
            a_display = str(a_full).upper()
            
            print(f"\n--- {league.upper()} PREDICTION ---")
            print(f"{a_display} @ {h_display}")
            print(f"Model Predicted Margin: {h_display} by {prediction:.1f} points")
            print(f"---------------------------\n")
        else:
            logger.warning(f"Could not find a reliable match for '{home_name}' or '{away_name}' in the database.")

    except Exception as e:
        logger.error(f"Prediction failed: {e}")

if __name__ == "__main__":
    print("Local Model Engine Ready (Feb 26, 2026).")
    h = input("Enter Home Team: ")
    a = input("Enter Away Team: ")
    l = input("League (nba/ncaab): ").lower()
    run_manual_prediction(h, a, l)