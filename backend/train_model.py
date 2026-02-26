import pandas as pd
import xgboost as xgb
from sqlalchemy import create_engine
from loguru import logger

# Postgres Connection
DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)

def train_market(market_type='nba'):
    """Trains a specific model: 'nba', 'ncaab', or 'prop'"""
    try:
        logger.info(f"Training {market_type.upper()} model...")
        
        # Pull features from your model_training_data table
        if market_type == 'prop':
            # Assuming you have a player_game_logs table with rolling stats
            query = "SELECT * FROM player_model_data WHERE pts_avg_10 IS NOT NULL"
            target = 'actual_points'
        else:
            query = f"SELECT * FROM model_training_data WHERE league = '{market_type.upper()}'"
            target = 'margin'

        df = pd.read_sql(query, engine)
        if df.empty:
            logger.error(f"No data for {market_type}. Skip.")
            return

        # Define your feature set
        features = ['home_off_eff', 'home_def_eff', 'away_off_eff', 'away_def_eff', 'home_power_rank', 'away_power_rank']
        
        X = df[features]
        y = df[target]

        model = xgb.XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=5)
        model.fit(X, y)
        
        model_name = f"{market_type}_model.json"
        model.save_model(model_name)
        logger.success(f"Saved {model_name}")

    except Exception as e:
        logger.error(f"Failed {market_type}: {e}")

if __name__ == "__main__":
    for market in ['nba', 'ncaab', 'prop']:
        train_market(market)