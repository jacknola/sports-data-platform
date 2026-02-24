import asyncio
import sys
import os

# Add the current directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ncaab_stats_service import NCAABStatsService

async def test_stats():
    service = NCAABStatsService()
    stats = await service.fetch_all_team_stats()
    print(f"Fetched {len(stats)} teams")
    if stats:
        first_team = list(stats.keys())[0]
        print(f"Sample: {first_team} -> {stats[first_team]}")
    else:
        print("No stats fetched!")

if __name__ == "__main__":
    asyncio.run(test_stats())
