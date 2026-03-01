import asyncio
import httpx

async def get_team_roster(team_id: str):
    url = f"https://stats.nba.com/stats/teamplayerdashboard?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=00&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=0&PaceAdjust=N&PerMode=PerGame&Period=0&PlusMinus=N&Rank=N&Season=2024-25&SeasonSegment=&SeasonType=Regular+Season&TeamID={team_id}&VsConference=&VsDivision="
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.nba.com/',
        'x-nba-stats-origin': 'stats',
        'x-nba-stats-token': 'true'
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10.0)
            data = resp.json()
            
            # Index 1 is usually the player stats
            headers = data['resultSets'][1]['headers']
            rows = data['resultSets'][1]['rowSet']
            
            # Map column names to indices
            col_idx = {h: i for i, h in enumerate(headers)}
            
            players = []
            for row in rows:
                players.append({
                    'name': row[col_idx['PLAYER_NAME']],
                    'gp': row[col_idx['GP']],
                    'min': row[col_idx['MIN']],
                })
                
            # Sort by minutes played to get the hierarchy
            players.sort(key=lambda x: x['min'], reverse=True)
            return players
            
    except Exception as e:
        print(f"Error: {e}")
        return []

import asyncio
if __name__ == "__main__":
    players = asyncio.run(get_team_roster("1610612747")) # Lakers
    print("Top 10 players by minutes:")
    for i, p in enumerate(players[:10]):
        print(f"{i+1}. {p['name']} - {p['min']} min/game")
