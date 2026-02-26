import pandas as pd
from sqlalchemy import create_engine
from loguru import logger

# 1. Connection
DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)

def calculate_efficiency_sql_fixed():
    try:
        logger.info("Calculating Efficiency (Excluding JSON columns to fix 'dict' error)...")
        
        # We only select the numeric and text columns needed for the model
        sql = """
        WITH game_flat AS (
            SELECT game_date, home_team as team, home_score as pts_scored, away_score as pts_allowed, 'home' as side, id 
            FROM historical_game_lines
            UNION ALL
            SELECT game_date, away_team as team, away_score as pts_scored, home_score as pts_allowed, 'away' as side, id 
            FROM historical_game_lines
        ),
        rolling_stats AS (
            SELECT *,
                AVG(pts_scored) OVER (PARTITION BY team ORDER BY game_date ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING) as off_eff_10,
                AVG(pts_allowed) OVER (PARTITION BY team ORDER BY game_date ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING) as def_eff_10
            FROM game_flat
        )
        SELECT 
            hgl.id, hgl.game_date, hgl.home_team, hgl.away_team, 
            hgl.home_score, hgl.away_score, hgl.home_spread, hgl.league, hgl.season,
            rs_h.off_eff_10 as home_off_eff,
            rs_h.def_eff_10 as home_def_eff,
            rs_a.off_eff_10 as away_off_eff,
            rs_a.def_eff_10 as away_def_eff
        FROM historical_game_lines hgl
        LEFT JOIN rolling_stats rs_h ON hgl.id = rs_h.id AND rs_h.side = 'home'
        LEFT JOIN rolling_stats rs_a ON hgl.id = rs_a.id AND rs_a.side = 'away'
        """
        
        # Using chunksize to keep RAM low on your Air
        chunks = pd.read_sql(sql, engine, chunksize=25000)
        
        first_chunk = True
        for chunk in chunks:
            # Drop any games that don't have scores (just in case)
            chunk = chunk.dropna(subset=['home_score', 'away_score'])
            
            # Calculate the Margin (The target for our model)
            chunk['margin'] = chunk['home_score'] - chunk['away_score']
            
            # Calculate Power Ranks
            chunk['home_power_rank'] = chunk['home_off_eff'] - chunk['home_def_eff']
            chunk['away_power_rank'] = chunk['away_off_eff'] - chunk['away_def_eff']
            
            mode = 'replace' if first_chunk else 'append'
            chunk.to_sql('model_training_data', engine, if_exists=mode, index=False)
            logger.info(f"Saved chunk to model_training_data...")
            first_chunk = False

        logger.success("Success! Features generated and saved to 'model_training_data'.")

    except Exception as e:
        logger.error(f"Feature generation failed: {e}")

if __name__ == "__main__":
    calculate_efficiency_sql_fixed()