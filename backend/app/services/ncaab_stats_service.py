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
        Fetch team efficiency stats from BartTorvik using cloudscraper 
        to bypass anti-bot protection.
        """
        import re
        import asyncio
        
        if self.team_stats_cache and self._last_fetch:
            if (datetime.now() - self._last_fetch).days < 1:
                return self.team_stats_cache

        url = "https://barttorvik.com/trank.php"
        logger.info(f"Fetching NCAAB stats from {url}")
        
        try:
            # We use cloudscraper in a thread to handle the JS challenge 
            # without blocking the async event loop
            def fetch_page():
                import cloudscraper
                # Mimic a standard desktop Chrome browser
                scraper = cloudscraper.create_scraper(browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                })
                return scraper.get(url, timeout=30)
                
            response = await asyncio.to_thread(fetch_page)
            response.raise_for_status()
            
            stats = {}
            soup = BeautifulSoup(response.text, 'lxml')
            
            table = soup.find('table')
            if not table:
                logger.warning("Could not find the stats table on BartTorvik. Cloudscraper may have been blocked.")
                return {}
                
            rows = table.find_all('tr')[1:] # Skip the header row
            
            for row in rows:
                try:
                    cells = row.find_all('td')
                    if len(cells) < 5: 
                        continue
                        
                    # Team name is in the 2nd column (index 1), inside an <a> tag
                    name_cell = cells[1].find('a')
                    if not name_cell:
                        continue
                        
                    # Clean up the name (removes tournament seeds like "Houston 1")
                    raw_name = name_cell.get_text().strip()
                    team_name = re.sub(r'\s*\d+$', '', raw_name).strip()
                    
                    # BartTorvik columns: Barthag (2), AdjOE (3), AdjDE (4)
                    # Barthag represents overall win probability, serving the same role as BPI
                    bpi = float(cells[2].get_text().strip()) 
                    off_eff = float(cells[3].get_text().strip())
                    def_eff = float(cells[4].get_text().strip())
                    
                    stats[team_name] = {
                        "AdjOE": off_eff,
                        "AdjDE": def_eff,
                        "BPI": bpi * 100, # Scale Barthag (0 to 1) so it looks more like BPI
                    }
                except (ValueError, IndexError, AttributeError):
                    continue
            
            if stats:
                self.team_stats_cache = stats
                self._last_fetch = datetime.now()
                logger.info(f"Successfully fetched stats for {len(stats)} NCAAB teams from BartTorvik")
            
            return stats
            
        except ImportError:
            logger.error("The 'cloudscraper' package is missing. Run: pip install cloudscraper")
            return {}
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
