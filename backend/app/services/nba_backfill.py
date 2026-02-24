"""
NBA historical data backfill service.
"""
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from nba_api.stats.endpoints import leaguegamefinder
from app.models.game import Game
from loguru import logger

class NBABackfillService:
    """
    Service for backfilling historical NBA game data using nba_api.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def backfill_season(self, season_year: str) -> int:
        """
        Fetch and save historical games for a specific season.
        Format: '2023-24'
        """
        logger.info(f"Backfilling NBA season {season_year}")
        
        # Query nba_api for games in that season
        game_finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season_year,
            league_id_nullable="00"  # NBA
        )
        games_df = game_finder.get_data_frames()[0]
        games_list = games_df.to_dict(orient="records")
        
        # Group by game ID to get both home and away
        game_groups = {}
        for row in games_list:
            gid = row["GAME_ID"]
            if gid not in game_groups:
                game_groups[gid] = []
            game_groups[gid].append(row)
            
        count = 0
        for gid, rows in game_groups.items():
            if len(rows) < 2:
                continue
                
            # Determine home and away
            # In MATCHUP, 'vs' means home, '@' means away
            home_row = next((r for r in rows if "vs" in r["MATCHUP"]), None)
            away_row = next((r for r in rows if "@" in r["MATCHUP"]), None)
            
            if not home_row or not away_row:
                continue
                
            ext_id = f"NBA_{gid}"
            
            # Check if exists
            stmt = select(Game).where(Game.external_game_id == ext_id)
            existing = self.db.execute(stmt).scalars().first()
            if existing:
                continue
                
            new_game = Game(
                external_game_id=ext_id,
                sport="nba",
                home_team=home_row["TEAM_ABBREVIATION"],
                away_team=away_row["TEAM_ABBREVIATION"],
                game_date=datetime.strptime(home_row["GAME_DATE"], "%Y-%m-%d"),
                home_score=home_row["PTS"],
                away_score=away_row["PTS"]
            )
            self.db.add(new_game)
            count += 1
            
        self.db.commit()
        logger.info(f"Successfully backfilled {count} NBA games for {season_year}")
        return count
