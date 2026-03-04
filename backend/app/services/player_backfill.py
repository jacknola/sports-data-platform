"""
NBA player historical game log backfill service.
"""
from typing import List, Dict, Any
from datetime import datetime
import time
from sqlalchemy.orm import Session
from sqlalchemy import select
try:
    from nba_api.stats.endpoints import playergamelog
    _NBA_API_AVAILABLE = True
except ImportError:
    playergamelog = None  # type: ignore[assignment]
    _NBA_API_AVAILABLE = False
from app.models.player import Player
from app.models.player_game_log import PlayerGameLog
from loguru import logger

class NBAPlayerBackfillService:
    """
    Service for backfilling historical NBA player game logs using nba_api.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def backfill_player(self, player_id: int, season_year: str) -> int:
        """
        Fetch and save historical game logs for a specific player and season.
        Format: '2023-24'
        """
        stmt = select(Player).where(Player.id == player_id)
        player = self.db.execute(stmt).scalars().first()
        
        if not player or not player.external_player_id:
            logger.warning(f"Player {player_id} not found or missing external ID")
            return 0
            
        logger.info(f"Backfilling logs for {player.name} ({season_year})")
        
        try:
            time.sleep(0.6) # Rate limit
            log_api = playergamelog.PlayerGameLog(
                player_id=player.external_player_id,
                season=season_year
            )
            df = log_api.get_data_frames()[0]
            count = 0
            
            for _, row in df.iterrows():
                ext_gid = str(row["Game_ID"])
                ext_log_id = f"NBA_LOG_{ext_gid}_{player.external_player_id}"
                
                # Check if exists
                chk_stmt = select(PlayerGameLog).where(PlayerGameLog.external_log_id == ext_log_id)
                existing = self.db.execute(chk_stmt).scalars().first()
                if existing:
                    continue
                    
                _pts = int(row.get("PTS", 0) or 0)
                _reb = int(row.get("REB", 0) or 0)
                _ast = int(row.get("AST", 0) or 0)
                
                new_log = PlayerGameLog(
                    player_id=player.id,
                    external_log_id=ext_log_id,
                    game_date=datetime.strptime(row["GAME_DATE"], "%b %d, %Y"),
                    min=float(str(row.get("MIN", "0")).split(":")[0]),
                    pts=_pts,
                    reb=_reb,
                    ast=_ast,
                    stl=int(row.get("STL", 0) or 0),
                    blk=int(row.get("BLK", 0) or 0),
                    tov=int(row.get("TOV", 0) or 0),
                    fg3m=int(row.get("FG3M", 0) or 0),
                    pra=_pts + _reb + _ast
                )
                self.db.add(new_log)
                count += 1
                
            self.db.commit()
            logger.info(f"Successfully backfilled {count} logs for {player.name}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to backfill player {player.name}: {e}")
            return 0
