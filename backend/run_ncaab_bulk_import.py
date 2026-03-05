"""
NCAAB Bulk Importer
Bulk-loads NCAAB player statistics and team ratings from SportsDataverse (hoopR) and NCAA_Hoops.
"""

import os
import sys
import pandas as pd
from loguru import logger
from sqlalchemy import select

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.game import Game
from app.models.team import Team
from app.models.player import Player
from app.models.player_game_log import PlayerGameLog

# SportsDataverse Parquet URLs (Player Box Scores)
BASE_PARQUET_URL = "https://github.com/sportsdataverse/hoopR-mbb-data/raw/main/mbb/player_box/parquet/player_box_{year}.parquet"

# NCAA_Hoops Team Ratings (History)
RATINGS_URL = "https://raw.githubusercontent.com/lbenz730/NCAA_Hoops/master/3.0_Files/History/history.csv"

def parse_minutes(min_str: Any) -> float:
    """Convert string minutes to float."""
    if pd.isna(min_str) or min_str == "":
        return 0.0
    try:
        return float(min_str)
    except:
        return 0.0

async def import_ncaab_data(years: List[int]):
    db = SessionLocal()
    
    try:
        # 1. Import Team Ratings first (to have team metadata)
        logger.info(f"Downloading team ratings from {RATINGS_URL}...")
        try:
            ratings_df = pd.read_csv(RATINGS_URL)
            # Latest ratings per team
            latest_ratings = ratings_df.sort_values("date").groupby("team").tail(1)
            logger.info(f"Loaded ratings for {len(latest_ratings)} teams.")
        except Exception as e:
            logger.warning(f"Could not load team ratings: {e}")
            latest_ratings = pd.DataFrame()

        # Pre-fetch existing data
        logger.info("Pre-fetching teams, players, and games...")
        teams_cache = {t.external_team_id: t for t in db.execute(select(Team).where(Team.sport == "ncaab")).scalars().all()}
        players_cache = {p.external_player_id: p for p in db.execute(select(Player).where(Player.sport == "ncaab")).scalars().all()}
        games_cache = {g.external_game_id: g for g in db.execute(select(Game).where(Game.sport == "ncaab")).scalars().all()}
        existing_logs = set(db.execute(select(PlayerGameLog.external_log_id)).scalars().all())

        for year in years:
            url = BASE_PARQUET_URL.format(year=year)
            logger.info(f"Downloading and processing {url}...")
            try:
                df = pd.read_parquet(url)
                logger.info(f"Loaded {len(df)} rows for {year}.")
            except Exception as e:
                logger.error(f"Failed to load parquet for {year}: {e}")
                continue

            # Sort by game_id
            df = df.sort_values("game_id")
            
            logs_to_add = []
            
            for i, row in df.iterrows():
                # NCAAB hoopR athlete_id can be null for some bench players/unknowns
                if pd.isna(row["athlete_id"]):
                    continue
                    
                ext_game_id = f"NCAAB_{row['game_id']}"
                ext_player_id = f"NCAAB_P_{int(row['athlete_id'])}"
                ext_team_id = f"NCAAB_T_{int(row['team_id'])}"
                ext_opp_id = f"NCAAB_T_{int(row['opponent_team_id'])}" if not pd.isna(row["opponent_team_id"]) else None
                
                # 1. Ensure Team exists
                if ext_team_id not in teams_cache:
                    team_name = row["team_display_name"] or row["team_name"]
                    
                    # Try to find ratings for this team
                    team_stats = {}
                    if not latest_ratings.empty:
                        # Fuzzy match team name in ratings
                        match = latest_ratings[latest_ratings["team"].str.contains(team_name, case=False, na=False)]
                        if not match.empty:
                            m = match.iloc[0]
                            team_stats = {
                                "yusag_coeff": float(m["yusag_coeff"]),
                                "off_coeff": float(m["off_coeff"]),
                                "def_coeff": float(m["def_coeff"]),
                                "rank": int(m["rank"])
                            }
                    
                    new_team = Team(
                        external_team_id=ext_team_id,
                        name=team_name,
                        sport="ncaab",
                        stats=team_stats
                    )
                    db.add(new_team)
                    db.flush()
                    teams_cache[ext_team_id] = new_team
                
                team = teams_cache[ext_team_id]

                # 2. Ensure Opponent Team exists
                opponent = None
                if ext_opp_id:
                    if ext_opp_id not in teams_cache:
                        opp_name = row["opponent_team_display_name"] or row["opponent_team_name"]
                        new_opp = Team(
                            external_team_id=ext_opp_id,
                            name=opp_name,
                            sport="ncaab"
                        )
                        db.add(new_opp)
                        db.flush()
                        teams_cache[ext_opp_id] = new_opp
                    opponent = teams_cache[ext_opp_id]
                
                # 3. Ensure Player exists
                if ext_player_id not in players_cache:
                    new_player = Player(
                        external_player_id=ext_player_id,
                        name=row["athlete_display_name"],
                        team_id=team.id,
                        sport="ncaab"
                    )
                    db.add(new_player)
                    db.flush()
                    players_cache[ext_player_id] = new_player
                
                player = players_cache[ext_player_id]
                
                # 4. Ensure Game exists
                if ext_game_id not in games_cache:
                    is_home = row["home_away"] == "home"
                    home_team = row["team_name"] if is_home else row["opponent_team_name"]
                    away_team = row["opponent_team_name"] if is_home else row["team_name"]
                    
                    # hoopR often doesn't have score in player_box, but this dataset seems to have team_score
                    h_score = int(row["team_score"]) if is_home else int(row["opponent_team_score"])
                    a_score = int(row["opponent_team_score"]) if is_home else int(row["team_score"])
                    
                    new_game = Game(
                        external_game_id=ext_game_id,
                        sport="ncaab",
                        home_team=home_team,
                        away_team=away_team,
                        game_date=pd.to_datetime(row["game_date"]),
                        home_score=h_score if not pd.isna(h_score) else None,
                        away_score=a_score if not pd.isna(a_score) else None
                    )
                    db.add(new_game)
                    db.flush()
                    games_cache[ext_game_id] = new_game
                
                game = games_cache[ext_game_id]
                
                # 5. Create PlayerGameLog
                ext_log_id = f"NCAAB_{row['game_id']}_{int(row['athlete_id'])}"
                
                if ext_log_id in existing_logs:
                    continue
                    
                log_data = {
                    "player_id": player.id,
                    "game_id": game.id,
                    "external_log_id": ext_log_id,
                    "team_id": team.id,
                    "opponent_id": opponent.id if opponent else None,
                    "game_date": pd.to_datetime(row["game_date"]),
                    "min": parse_minutes(row["minutes"]),
                    "pts": int(row["points"]) if not pd.isna(row["points"]) else 0,
                    "reb": int(row["rebounds"]) if not pd.isna(row["rebounds"]) else 0,
                    "ast": int(row["assists"]) if not pd.isna(row["assists"]) else 0,
                    "stl": int(row["steals"]) if not pd.isna(row["steals"]) else 0,
                    "blk": int(row["blocks"]) if not pd.isna(row["blocks"]) else 0,
                    "tov": int(row["turnovers"]) if not pd.isna(row["turnovers"]) else 0,
                    "fg3m": int(row["three_point_field_goals_made"]) if not pd.isna(row["three_point_field_goals_made"]) else 0,
                    "pra": (int(row["points"]) if not pd.isna(row["points"]) else 0) + 
                           (int(row["rebounds"]) if not pd.isna(row["rebounds"]) else 0) + 
                           (int(row["assists"]) if not pd.isna(row["assists"]) else 0)
                }
                
                logs_to_add.append(log_data)
                
                if len(logs_to_add) >= 1000:
                    db.bulk_insert_mappings(PlayerGameLog, logs_to_add)
                    db.commit()
                    logs_to_add = []
                    logger.info(f"Imported {i} logs from {year}...")
            
            if logs_to_add:
                db.bulk_insert_mappings(PlayerGameLog, logs_to_add)
                db.commit()
                
        logger.info("✅ Bulk NCAAB import complete!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    # Import last 3 seasons by default
    import asyncio
    asyncio.run(import_ncaab_data([2023, 2024, 2025]))
