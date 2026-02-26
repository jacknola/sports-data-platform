import pandas as pd
import xgboost as xgb
import gspread
import os
from sqlalchemy import create_engine
from typing import List, Any
from loguru import logger
from gspread.utils import ValueInputOption

# 1. Configuration
# Updated for the 'sports_app' user and database
DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)
SHEET_NAME = "warp props"

def train_missing_models():
    """Builds models if missing. Skips props if table is not found."""
    tasks = {
        'nba': "SELECT * FROM model_training_data WHERE league = 'NBA'",
        'ncaab': "SELECT * FROM model_training_data WHERE league = 'NCAAB'"
    }
    
    # We handle spreads first
    for m_type, query in tasks.items():
        path = f"{m_type}_model.json"
        if not os.path.exists(path):
            logger.info(f"Training {m_type.upper()} model...")
            df = pd.read_sql(query, engine)
            if not df.empty:
                features = ['home_off_eff', 'home_def_eff', 'away_off_eff', 'away_def_eff', 'home_power_rank', 'away_power_rank']
                X = df[features]
                y = df['margin']
                xgb.XGBRegressor(n_estimators=500, learning_rate=0.05).fit(X, y).save_model(path)
                logger.success(f"Built {path}")

    # Special handling for props to avoid crashing
    if not os.path.exists("prop_model.json"):
        try:
            logger.info("Checking for player_stats_table...")
            df = pd.read_sql("SELECT * FROM player_stats_table LIMIT 1", engine)
            # If we get here, table exists. Proceed with full training...
        except Exception:
            logger.warning("player_stats_table not found. Skipping Prop model training.")

def get_predictions() -> dict:
    """Calculates predictions for Feb 26, 2026."""
    query = """
        SELECT DISTINCT ON (team) team, home_off_eff, home_def_eff, home_power_rank 
        FROM (SELECT home_team as team, home_off_eff, home_def_eff, home_power_rank, game_date FROM model_training_data) t 
        ORDER BY team, game_date DESC
    """
    stats_df = pd.read_sql(query, engine)
    stats = stats_df.set_index('team').to_dict('index')

    # TONIGHT'S SLATE (Feb 26, 2026)
    spread_slate = [
        {"h": "jazz", "a": "pelicans", "l": "nba", "v": 4.5},      
        {"h": "phi", "a": "heat", "l": "nba", "v": -1.5},       
        {"h": "magic", "a": "hou", "l": "nba", "v": -2.5},      
        {"h": "purdue", "a": "michigan st", "l": "ncaab", "v": 9.5}, 
        {"h": "pacers", "a": "hornets", "l": "nba", "v": 6.0}     
    ]
    
    nba_res: List[List[Any]] = [["Matchup", "Vegas Line", "Model Pred", "Edge"]]
    ncaab_res: List[List[Any]] = [["Matchup", "Vegas Line", "Model Pred", "Edge"]]
    prop_res: List[List[Any]] = [["Player", "Prop Line", "Model Pred", "Edge"]] # Placeholder

    for g in spread_slate:
        h_s, a_s = stats.get(g['h']), stats.get(g['a'])
        if h_s and a_s:
            model = xgb.XGBRegressor(); model.load_model(f"{g['l']}_model.json")
            feats = pd.DataFrame([[h_s['home_off_eff'], h_s['home_def_eff'], a_s['home_off_eff'], a_s['home_def_eff'], h_s['home_power_rank'], a_s['home_power_rank']]], 
                                 columns=['home_off_eff', 'home_def_eff', 'away_off_eff', 'away_def_eff', 'home_power_rank', 'away_power_rank'])
            pred = float(model.predict(feats)[0])
            row = [f"{g['a'].upper()} @ {g['h'].upper()}", g['v'], round(pred, 2), round(pred - g['v'], 2)]
            
            if g['l'] == 'nba': nba_res.append(row)
            else: ncaab_res.append(row)

    return {"nba": nba_res, "ncaab": ncaab_res, "props": prop_res}

def upload_to_sheets(data_dict: dict):
    """Pushes data to Google Sheets using Enums for type safety."""
    try:
        client = gspread.service_account(filename="service_account.json")
        spreadsheet = client.open(SHEET_NAME)
        
        tab_map = {"nba": "NBA_Spreads", "ncaab": "NCAAB_Spreads", "props": "Player_Props"}
        
        for key, tab_name in tab_map.items():
            sheet = spreadsheet.worksheet(tab_name)
            sheet.clear()
            
            # Use the Enum instead of a string to satisfy Pylance
            sheet.update(
                range_name='A1', 
                values=data_dict[key], 
                value_input_option=ValueInputOption.user_entered 
            )
            logger.info(f"Updated {tab_name}")
            
        logger.success("Dashboard successfully updated for Feb 26!")
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"Spreadsheet '{SHEET_NAME}' not found! Please share it with the service account email.")
    except Exception as e:
        logger.error(f"Upload failed: {repr(e)}")

if __name__ == "__main__":

    train_missing_models()

    predictions = get_predictions()
    upload_to_sheets(predictions)
    
    