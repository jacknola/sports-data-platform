import asyncio
import pandas as pd
import xgboost as xgb
from sqlalchemy import create_engine
from playwright.async_api import async_playwright 
from playwright_stealth import Stealth
from rapidfuzz import process, utils
from loguru import logger

# 1. Connection to your Postgres
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")

async def get_live_board(league='nba'):
    url = f"https://www.covers.com/sport/basketball/{league}/odds"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        logger.info(f"Stealth scraping {league.upper()} board from Covers...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(3) 
            
            games = []
            rows = await page.query_selector_all(".cmg_matchup_row, .odds-list-row") 
            
            for row in rows:
                text = await row.inner_text()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                if len(lines) >= 3:
                    games.append({
                        "away_name": lines[0],
                        "home_name": lines[1],
                        "vegas_spread": lines[2].split(' ')[0]
                    })
            
            await browser.close()
            return games
        except Exception as e:
            logger.error(f"Scrape failed: {e}")
            await browser.close()
            return []

def match_and_predict(scraped_games, league='nba'):
    try:
        model = xgb.XGBRegressor()
        model.load_model(f"{league}_model.json")
        
        # Pull latest stats
        query = "SELECT DISTINCT ON (team) team, home_off_eff, home_def_eff, home_power_rank FROM (SELECT home_team as team, home_off_eff, home_def_eff, home_power_rank, game_date FROM model_training_data) t ORDER BY team, game_date DESC"
        eff_df = pd.read_sql(query, engine)
        db_teams = eff_df['team'].tolist()
        
        print(f"\n--- {league.upper()} VALUE REPORT (Feb 26, 2026) ---")
        for game in scraped_games:
            h_match = process.extractOne(game['home_name'].lower(), db_teams, processor=utils.default_process, score_cutoff=60)
            a_match = process.extractOne(game['away_name'].lower(), db_teams, processor=utils.default_process, score_cutoff=60)
            
            if h_match and a_match:
                h_team, a_team = h_match[0], a_match[0]
                h_stats = eff_df[eff_df['team'] == h_team].iloc[0]
                a_stats = eff_df[eff_df['team'] == a_team].iloc[0]
                
                # Features matching your training set
                features = pd.DataFrame([[
                    h_stats['home_off_eff'], h_stats['home_def_eff'], 
                    a_stats['home_off_eff'], a_stats['home_def_eff'], 
                    h_stats['home_power_rank'], a_stats['home_power_rank']
                ]], columns=['home_off_eff', 'home_def_eff', 'away_off_eff', 'away_def_eff', 'home_power_rank', 'away_power_rank'])
                
                prediction = model.predict(features)[0]
                
                # Clean up Vegas spread for comparison
                try:
                    v_line = float(game['vegas_spread'].replace('pk', '0').replace('+', ''))
                    edge = abs(prediction - v_line)
                    print(f"{a_team.upper()} @ {h_team.upper()} | Model: {prediction:+.1f} | Vegas: {v_line:+.1f} | EDGE: {edge:.1f}")
                    if edge > 3.0: print("  🔥 VALUE ALERT")
                except:
                    print(f"{a_team.upper()} @ {h_team.upper()} | Model: {prediction:+.1f} | Vegas: {game['vegas_spread']}")

    except Exception as e:
        logger.error(f"Logic failed: {e}")

if __name__ == "__main__":
    nba_board = asyncio.run(get_live_board('nba'))
    if nba_board: 
        match_and_predict(nba_board, 'nba')
    else:
        print("No live games found. Site might be blocking or layout changed.")