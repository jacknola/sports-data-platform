"""
Tomorrow's Slate Discovery
Discovers tomorrow's NBA and NCAAB games and attempts to fetch live betting lines.
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime, timedelta, timezone
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.sports_api import SportsAPIService, normalize_team_name

async def scrape_vegas_insider(sport: str):
    """Emergency scraper for VegasInsider odds."""
    logger.info(f"Attempting emergency scrape from VegasInsider for {sport}...")
    import httpx
    from bs4 import BeautifulSoup
    
    path = "nba" if "nba" in sport else "college-basketball"
    url = f"https://www.vegasinsider.com/{path}/odds/las-vegas/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # VegasInsider structure varies, try a few common patterns
        print("\n  [EMERGENCY SCRAPE - VEGASINSIDER]")
        count = 0
        
        # Pattern 1: Table-based
        rows = soup.find_all(class_='odds-table-row')
        for row in rows:
            try:
                teams = row.find_all(class_='team-name')
                if len(teams) >= 2:
                    away, home = teams[0].text.strip(), teams[1].text.strip()
                    line = row.find(class_='odds-cell').text.strip() if row.find(class_='odds-cell') else "N/A"
                    print(f"  - {away} @ {home} | Line: {line}")
                    count += 1
            except: continue
            
        # Pattern 2: Flex-based (modern)
        if count == 0:
            games = soup.find_all(class_='game-odds-row')
            for g in games:
                try:
                    teams = g.find_all(class_='team-name')
                    if len(teams) >= 2:
                        away, home = teams[0].text.strip(), teams[1].text.strip()
                        line = g.find(class_='odds-label').text.strip() if g.find(class_='odds-label') else "N/A"
                        print(f"  - {away} @ {home} | Line: {line}")
                        count += 1
                except: continue
        
        if count == 0:
            print("  No games could be extracted via direct scrape (site might be protected).")
            
    except Exception as e:
        logger.error(f"Emergency scrape failed: {e}")

async def fetch_tomorrow_slate(sport: str = "basketball_nba"):
    logger.info(f"Discovering tomorrow's slate for {sport}...")
    
    api = SportsAPIService()
    
    # 1. Discover events
    discovery = await api.discover_games(sport)
    all_events = discovery.data
    
    if not all_events:
        logger.warning(f"No upcoming events found for {sport}")
        await scrape_vegas_insider(sport)
        return
        
    now = datetime.now(timezone.utc)
    tomorrow_date = (now + timedelta(days=1)).date()
    
    tomorrow_events = []
    for ev in all_events:
        ct = ev.get("commence_time") or ev.get("date")
        if ct:
            try:
                dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                if dt.date() == tomorrow_date:
                    tomorrow_events.append(ev)
            except:
                continue
                
    if not tomorrow_events:
        logger.info("No exact matches for 'tomorrow' date in Discovery. Checking next 48 hours...")
        for ev in all_events:
            ct = ev.get("commence_time") or ev.get("date")
            if ct:
                try:
                    dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                    diff = (dt - now).total_seconds() / 3600
                    if 0 < diff <= 48:
                        tomorrow_events.append(ev)
                except:
                    continue

    # 3. Try to get odds
    odds_data = await api.get_odds(sport)
    
    print("\n" + "=" * 60)
    print(f"  UPCOMING SLATE & LINES: {sport.upper()}")
    print(f"  Discovery Source: {discovery.source_label}")
    print("=" * 60)
    
    if not odds_data:
        print("\n  [!] NO LIVE ODDS FOUND IN APIs (Quota exhausted)")
        print("      Discovered games for next 48h:")
        for ev in tomorrow_events[:15]:
            home = ev.get("home_team") or ev.get("home")
            away = ev.get("away_team") or ev.get("away")
            print(f"      - {away} @ {home}")
        
        # Trigger emergency scrape
        await scrape_vegas_insider(sport)
    else:
        found_any = False
        for g in odds_data:
            home = g.get("home_team")
            away = g.get("away_team")
            
            ct = g.get("commence_time")
            if ct:
                dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                # Only show games starting at least 12h from now
                if (dt - now).total_seconds() / 3600 > 12:
                    found_any = True
                    print(f"\n  {away} @ {home}")
                    print(f"  Time: {ct}")
                    
                    spread, total = "N/A", "N/A"
                    for book in g.get("bookmakers", []):
                        for market in book.get("markets", []):
                            if market["key"] == "spreads":
                                for out in market["outcomes"]:
                                    if out["name"] == home: spread = f"{out.get('point'):+g}"
                            if market["key"] == "totals":
                                for out in market["outcomes"]:
                                    if out["name"] == "Over": total = f"{out.get('point')}"
                    
                    print(f"  Line: {spread} | O/U: {total}")
        
        if not found_any:
            print("\n  No 'tomorrow' lines in APIs yet. Running emergency scrape...")
            await scrape_vegas_insider(sport)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", default="basketball_nba")
    args = parser.parse_args()
    asyncio.run(fetch_tomorrow_slate(args.sport))
