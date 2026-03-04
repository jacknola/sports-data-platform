import asyncio
from backend.app.routers.props import run_prop_analysis

async def main():
    res = await run_prop_analysis("nba")
    props = res.get("props", [])
    print(f"Total props: {len(props)}")
    fd_props = [p for p in props if p.get("fanduel_over_odds") is not None or p.get("fanduel_under_odds") is not None]
    print(f"Props with FD odds: {len(fd_props)}")
    if fd_props:
        print("Sample FD prop:")
        print(fd_props[0])

if __name__ == "__main__":
    asyncio.run(main())
