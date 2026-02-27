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
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = await client.get(self.BASE_URL, headers=headers)
                response.raise_for_status()
                
            # Try to find JSON in script tag first (modern ESPN pages)
            import re
            import json
            
            # Use a more specific but flexible pattern
            # Search for the assignment to window["__espnfitt__"]
            pattern = re.compile(r'window\["__espnfitt__"\]\s*=\s*({.*?});', re.DOTALL)
            match = pattern.search(response.text)
            
            stats = {}
            
            if not match:
                # Try single quotes
                pattern = re.compile(r"window\['__espnfitt__'\]\s*=\s*({.*?});", re.DOTALL)
                match = pattern.search(response.text)
            
            if not match:
                # Try just the variable name
                pattern = re.compile(r'__espnfitt__\s*=\s*({.*?});', re.DOTALL)
                match = pattern.search(response.text)
            # Search for the assignment to window["__espnfitt__"]
            pattern = re.compile(r'window\["__espnfitt__"\]\s*=\s*({.*?});')
            match = pattern.search(response.text)
            
            stats = {}
            
            if not match:
                # Try single quotes
                pattern = re.compile(r"window\['__espnfitt__'\]\s*=\s*({.*?});")
                match = pattern.search(response.text)
            
            if not match:
                # Try just the variable name
                pattern = re.compile(r'__espnfitt__\s*=\s*({.*?});')
                match = pattern.search(response.text)

            if match:
                try:
                    json_str = match.group(1)
                    # Simple validation - should start with { and end with }
                    if not (json_str.startswith('{') and json_str.endswith('}')):
                        # Try to find the last closing brace before the semicolon
                        last_brace = json_str.rfind('}')
                        if last_brace != -1:
                            json_str = json_str[:last_brace+1]
                    
                    data = json.loads(json_str)
                    
                    # Target path: page -> content -> teams
                    content = data.get("page", {}).get("content", {})
                    teams_data = content.get("teams", [])
                    
                    if not teams_data:
                        # LOG ALL KEYS AT VARIOUS LEVELS
                        logger.info(f"JSON Keys: {list(data.keys())}")
                        if "page" in data: logger.info(f"Page Keys: {list(data['page'].keys())}")
                        if "content" in data.get("page", {}): logger.info(f"Content Keys: {list(data['page']['content'].keys())}")
                        
                        # Try to find 'teams' anywhere that looks right
                        def find_teams_list(d):
                            if isinstance(d, dict):
                                if "teams" in d and isinstance(d["teams"], list) and len(d["teams"]) > 0:
                                    # Check if elements have 'team' and 'stats'
                                    first = d["teams"][0]
                                    if isinstance(first, dict) and "team" in first and "stats" in first:
                                        return d["teams"]
                                for v in d.values():
                                    res = find_teams_list(v)
                                    if res: return res
                            elif isinstance(d, list):
                                for item in d:
                                    res = find_teams_list(item)
                                    if res: return res
                            return None
                        teams_data = find_teams_list(data) or []

                    logger.info(f"Found {len(teams_data)} teams in ESPN JSON")
                    if teams_data:
                        first_team = teams_data[0].get("team", {}).get("displayName")
                        logger.info(f"First team in JSON: {first_team}")

                    for t_entry in teams_data:
                        team_obj = t_entry.get("team", {})
                        team_name = team_obj.get("displayName") or team_obj.get("nickname")
                        if not team_name:
                            continue
                        
                        t_stats = t_entry.get("stats", [])
                        # stats is a list of {"name": "...", "value": "..."}
                        stat_dict = {}
                        for s in t_stats:
                            name = s.get("name")
                            val = s.get("value")
                            if name and val is not None:
                                stat_dict[name] = val
                        
                        try:
                            # Stats in BPI page are: bpi, bpirank, bpioffense, bpidefense
                            stats[team_name] = {
                                "AdjOE": float(stat_dict.get("bpioffense", 0)),
                                "AdjDE": float(stat_dict.get("bpidefense", 0)),
                                "BPI": float(stat_dict.get("bpi", 0)),
                            }
                        except (ValueError, TypeError):
                            continue
                            
                    if stats:
                        logger.info(f"Successfully extracted stats for {len(stats)} teams from JSON")
                except Exception as e:
                    logger.error(f"Failed to parse ESPN JSON: {e}")

            # Fallback to table scraping if JSON path failed or returned nothing
            if not stats:
                soup = BeautifulSoup(response.text, 'lxml')
                tables = soup.find_all('table')
                if len(tables) >= 2:
                    name_rows = tables[0].find_all('tr')[2:]  # Skip header rows
                    stat_rows = tables[1].find_all('tr')[2:]  # Skip header rows
                    
                    for name_row, stat_row in zip(name_rows, stat_rows):
                        try:
                            name_cell = name_row.find('span', class_='TeamLink__Name') or name_row.find('a')
                            if not name_cell: continue
                            team_name = name_cell.get_text().strip()
                            
                            cells = stat_row.find_all('td')
                            bpi = float(cells[1].get_text())  # BPI column
                            off_eff = float(cells[4].get_text())  # OFF column
                            def_eff = float(cells[5].get_text())  # DEF column
                            
                            stats[team_name] = {
                                "AdjOE": off_eff,
                                "AdjDE": def_eff,
                                "BPI": bpi,
                            }
                        except (ValueError, IndexError, TypeError, AttributeError):
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
