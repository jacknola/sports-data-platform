import asyncio
import pandas as pd
import xgboost as xgb
from sqlalchemy import create_engine
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from rapidfuzz import process, utils
from loguru import logger

# 1. Database Connection
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")

async def get_prop_lines():
    """Stealth scrape player props for $0.00"""
    # Using a public props board (Example: BettingPros or similar)
    url = "https://www.bettingpros.com/nba/picks/prop-bets/"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await Stealth().apply_stealth_async(page)
        
        logger.info("Scraping tonight's NBA Player Props...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            props = []
            # Selector for player name and their 'Points' line
            rows = await page.query_selector_all(".prop-bet-row")
            for row in rows:
                name = await row.query_selector(".player-name-link")
                line = await row.query_selector(".line")
                if name and line:
                    props.append({
                        "player_name": await name.inner_text(),
                        "vegas_line": float(await line.inner_text())
                    })
            await browser.close()
            return props
        except Exception as e:
            logger.error(f"Prop scrape failed: {e}")
            await browser.close()
            return []

def predict_props(scraped_props):
    """Predicts tonight's performance and finds edges"""
    try:
        model = xgb.XGBRegressor()
        model.load_model("prop_model.json")
        
        # 1. Pull latest player stats
        # Ensure we name the list 'db_players' consistently
        player_stats = pd.read_sql("SELECT DISTINCT ON (player_name) * FROM player_stats_table ORDER BY player_name, game_date DESC", engine)
        db_players = player_stats['player_name'].tolist()

        print(f"\n--- NBA PLAYER PROP VALUE (Feb 26, 2026) ---")
        for prop in scraped_props:
            # 2. Match using the correctly named 'db_players' list
            match = process.extractOne(prop['player_name'], db_players, processor=utils.default_process)
            
            # 3. Nonetype & Confidence check
            if match and match[1] > 85:
                p_name = match[0]
                stats = player_stats[player_stats['player_name'] == p_name].iloc[0]
                
                # 4. Explicitly name your features to match your training set
                # Example: Adjust these strings to match EXACTLY what was in your X_train columns
                feature_cols = ['pts_avg_10', 'usage_rate', 'opp_def_rating'] 
                features = pd.DataFrame([[stats['pts_avg_10'], stats['usage_rate'], stats['opp_def_rating']]], 
                                        columns=feature_cols)
                
                prediction = model.predict(features)[0]
                edge = prediction - prop['vegas_line']
                
                print(f"{p_name.upper()}")
                print(f"  Vegas: {prop['vegas_line']} | Model: {prediction:.1f} | EDGE: {edge:+.1f}")
                
                # Flag high-value 'Overs' or 'Unders'
                if abs(edge) > 2.5:
                    side = "OVER" if edge > 0 else "UNDER"
                    print(f"  🔥 RECOMMENDED: {side}")
            else:
                logger.warning(f"Could not find a reliable DB match for player: {prop['player_name']}")
                    
    except Exception as e:
        logger.error(f"Prop prediction logic failed: {e}")
        
if __name__ == "__main__":
    props = asyncio.run(get_prop_lines())
    if props:
        predict_props(props)