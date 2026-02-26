"""
Tomorrow's Slate Scraper (Emergency)
Bypasses API quotas by scraping Action Network for tomorrow's betting lines.
"""

import httpx
import re
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from loguru import logger

def find_key(obj, target):
    if isinstance(obj, dict):
        if target in obj: return obj[target]
        for v in obj.values():
            res = find_key(v, target)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_key(item, target)
            if res: return res
    return None

async def scrape_action_network(sport: str = "nba"):
    path = "nba" if "nba" in sport else "college-basketball"
    url = f"https://www.actionnetwork.com/{path}/odds"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200: return []
        pattern = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')
        match = pattern.search(resp.text)
        if not match: return []
        data = json.loads(match.group(1))
        games_list = find_key(data, 'games') or []
        now = datetime.now(timezone.utc)
        tomorrow_date = (now + timedelta(days=1)).date()
        results = []
        for g in games_list:
            st = g.get("start_time")
            if not st: continue
            start_time = datetime.fromisoformat(st.replace("Z", "+00:00"))
            if start_time.date() == tomorrow_date:
                teams = g.get("teams", [])
                if len(teams) < 2: continue
                home_team = next((t["full_name"] for t in teams if t["id"] == g["home_team_id"]), "Home")
                away_team = next((t["full_name"] for t in teams if t["id"] == g["away_team_id"]), "Away")
                # Search for odds in the game object
                odds_list = g.get("odds", [])
                spread, total = "N/A", "N/A"
                if odds_list:
                    # Filter for DK or first available
                    o = odds_list[0]
                    spread = o.get("spread", "N/A")
                    total = o.get("total", "N/A")
                results.append({"home": home_team, "away": away_team, "time": st, "spread": spread, "total": total})
        return results

async def main():
    print("EMERGENCY SLATE DISCOVERY: TOMORROW'S LINES")
    print("Source: Action Network (Live Scrape)")
    for sport in ["nba", "college-basketball"]:
        games = await scrape_action_network(sport)
        print(f"--- {sport.upper()} ---")
        if not games: print("  No games found for tomorrow yet.")
        for g in games:
            print(f"  {g['away']} @ {g['home']} | Line: {g['spread']} | O/U: {g['total']} | Time: {g['time']}")

if __name__ == "__main__":
    asyncio.run(main())
