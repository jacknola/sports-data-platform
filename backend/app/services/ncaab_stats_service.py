"""
NCAAB Stats Service
Scrapes and provides real team efficiency statistics from BartTorvik.
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
from loguru import logger
import httpx
from bs4 import BeautifulSoup

class NCAABStatsService:
    """
    Provides real NCAAB team stats by scraping ESPN BPI.
    """
    
    BASE_URL = "https://www.espn.com/mens-college-basketball/bpi"
    
    # League-average baselines
    LEAGUE_AVG_ORTG = 106.0
    LEAGUE_AVG_DRTG = 106.0
    LEAGUE_AVG_PACE = 68.0
    
    def __init__(self, season: Optional[int] = None):
        self.team_stats_cache: Dict[str, Dict[str, float]] = {}
        self._last_fetch = None

    async def fetch_all_team_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch team efficiency stats from ESPN BPI.
        """
        if self.team_stats_cache and self._last_fetch:
            if (datetime.now() - self._last_fetch).days < 1:
                return self.team_stats_cache

        logger.info(f"Fetching NCAAB stats from {self.BASE_URL}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL)
                response.raise_for_status()
                
            soup = BeautifulSoup(response.text, 'lxml')
            
            # ESPN BPI page has two tables: one for names, one for stats
            # They are often within a div with class 'ResponsiveTable'
            tables = soup.find_all('table')
            if len(tables) < 2:
                logger.error(f"Could not find both tables on ESPN BPI (found {len(tables)})")
                return {}
                
            # Table 0: Team names
            # Table 1: Stats (BPI, Off, Def)
            name_rows = tables[0].find_all('tr')[1:] # Skip header
            stat_rows = tables[1].find_all('tr')[1:] # Skip header
            
            stats = {}
            for name_row, stat_row in zip(name_rows, stat_rows):
                try:
                    # Extract team name
                    name_cell = name_row.find('span', class_='TeamLink__Name')
                    if not name_cell:
                        name_cell = name_row.find('a')
                    if not name_cell:
                        continue
                    team_name = name_cell.get_text().strip()
                    
                    # Extract stats
                    # Row structure: BPI, RK, OFF, RK, DEF, RK...
                    cells = stat_row.find_all('td')
                    off_eff = float(cells[2].get_text())
                    def_eff = float(cells[4].get_text())
                    bpi = float(cells[0].get_text())
                    
                    stats[team_name] = {
                        "AdjOE": off_eff,
                        "AdjDE": def_eff,
                        "BPI": bpi,
                    }
                except (ValueError, IndexError, TypeError, AttributeError) as e:
                    continue
                    
            if stats:
                self.team_stats_cache = stats
                self._last_fetch = datetime.now()
                logger.info(f"Successfully fetched stats for {len(stats)} NCAAB teams from ESPN BPI")
                
            return stats
            
        except Exception as e:
            logger.error(f"Error fetching NCAAB stats: {e}")
            return {}

    def get_team_stats(self, team_name: str) -> Optional[Dict[str, float]]:
        """Get stats for a specific team with fuzzy matching."""
        if not self.team_stats_cache:
            return None
            
        # Try exact match
        if team_name in self.team_stats_cache:
            return self.team_stats_cache[team_name]
            
        # Try normalization/substring matching
        # Odds API names: "Connecticut Huskies", BartTorvik: "Connecticut"
        for name, data in self.team_stats_cache.items():
            if name.lower() in team_name.lower() or team_name.lower() in name.lower():
                return data
                
        return None
