"""
NCAAB historical data backfill service.
"""
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.game import Game
from loguru import logger

class NCAABBackfillService:
    """
    Service for backfilling historical NCAAB game data using web scraping.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def scrape_from_url(self, url: str) -> int:
        """
        Scrape historical games from a given URL.
        Note: This is a template implementation for the demo/test.
        In a real scenario, this would handle specific site logic.
        """
        logger.info(f"Scraping NCAAB data from {url}")
        
        try:
            resp = httpx.get(url)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            count = 0
            
            # Simple card-based scraping logic
            cards = soup.find_all(class_="game-card")
            for card in cards:
                home_team = card.find(class_="home-team").text.strip()
                home_score = int(card.find(class_="home-score").text.strip())
                away_team = card.find(class_="away-team").text.strip()
                away_score = int(card.find(class_="away-score").text.strip())
                game_date_str = card.find(class_="game-date").text.strip()
                
                # Generate unique ID
                ext_id = f"NCAAB_SCRAPE_{home_team}_{away_team}_{game_date_str}".replace(" ", "")
                
                # Check if exists
                stmt = select(Game).where(Game.external_game_id == ext_id)
                existing = self.db.execute(stmt).scalars().first()
                if existing:
                    continue
                    
                new_game = Game(
                    external_game_id=ext_id,
                    sport="ncaab",
                    home_team=home_team,
                    away_team=away_team,
                    game_date=datetime.strptime(game_date_str, "%Y-%m-%d"),
                    home_score=home_score,
                    away_score=away_score
                )
                self.db.add(new_game)
                count += 1
                
            self.db.commit()
            logger.info(f"Successfully scraped {count} NCAAB games")
            return count
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return 0
