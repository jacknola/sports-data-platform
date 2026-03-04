import asyncio
from backend.app.services.sports_api import SportsAPIService

async def main():
    api = SportsAPIService()
    props = await api.get_all_player_props("basketball_nba", max_events=1)
    if not props:
        print("No props")
        return
    
    books = set()
    for prop in props:
        for off in prop.get("offerings", []):
            books.add(off.get("book_key"))
    
    print(f"Available books: {books}")

if __name__ == "__main__":
    asyncio.run(main())
