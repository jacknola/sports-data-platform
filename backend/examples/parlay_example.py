"""
Example usage of the Parlay system with Twitter integration and RAG pipeline
"""
import asyncio
import httpx
from datetime import datetime, timedelta


BASE_URL = "http://localhost:8000/api/v1"


async def create_example_parlay():
    """Create an example parlay in Dan's AI Sports Picks style"""
    
    # Example parlay data
    parlay_data = {
        "title": "NBA Sunday Special",
        "sport": "NBA",
        "confidence_level": "HIGH",
        "confidence_score": 85,
        "legs": [
            {
                "game": "Lakers vs Warriors",
                "pick": "Lakers ML",
                "odds": -150,
                "reasoning": "LeBron dominates in revenge games, 8-2 record vs GSW last 10",
                "team": "Lakers",
                "opponent": "Warriors",
                "market": "moneyline",
                "supporting_factors": [
                    "Lakers on 3-game win streak",
                    "Warriors missing Draymond Green",
                    "Lakers 12-3 at home this season"
                ],
                "confidence": 0.85,
                "game_time": (datetime.now() + timedelta(hours=5)).isoformat()
            },
            {
                "game": "Celtics vs Heat",
                "pick": "Over 215.5",
                "odds": -110,
                "reasoning": "Both teams rank top 5 in pace, average 230 pts combined",
                "team": "Celtics",
                "opponent": "Heat",
                "market": "total",
                "line": 215.5,
                "supporting_factors": [
                    "Celtics averaging 118 PPG at home",
                    "Heat playing fast pace without Adebayo",
                    "Last 3 H2H games averaged 228 points"
                ],
                "confidence": 0.78,
                "game_time": (datetime.now() + timedelta(hours=5.5)).isoformat()
            },
            {
                "game": "Celtics vs Heat",
                "pick": "Celtics -7.5",
                "odds": -105,
                "reasoning": "Celtics elite at home, 12-2 ATS this season",
                "team": "Celtics",
                "opponent": "Heat",
                "market": "spread",
                "line": -7.5,
                "supporting_factors": [
                    "Celtics 14-1 at home",
                    "Heat on back-to-back road games",
                    "Celtics +12.5 point differential at home"
                ],
                "confidence": 0.82,
                "game_time": (datetime.now() + timedelta(hours=5.5)).isoformat()
            }
        ],
        "analysis": "Strong value on home favorites with rest advantage. Lakers have dominated Warriors recently, and Celtics are virtually unbeatable at home. The pace-up spot makes the over very attractive.",
        "key_factors": [
            "All picks are home teams with rest advantage",
            "Lakers and Celtics both on win streaks",
            "Warriors and Heat both playing on short rest",
            "Historical data strongly supports these picks"
        ],
        "risks": [
            "Warriors could play spoiler role",
            "Heat have playoff experience that could keep it close"
        ],
        "tags": ["revenge-game", "pace-up", "home-favorite", "rest-advantage"],
        "suggested_unit_size": 1.0,
        "event_date": (datetime.now() + timedelta(hours=5)).isoformat()
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Create the parlay
        print("📝 Creating parlay...")
        response = await client.post(f"{BASE_URL}/parlays", json=parlay_data)
        result = response.json()
        parlay_id = result['parlay_id']
        
        print(f"✅ Created parlay: {parlay_id}")
        print(f"   Similar parlays found: {result['insights']['similar_parlays_found']}")
        print(f"   Historical win rate: {result['insights'].get('historical_win_rate', 0):.1%}")
        print(f"   Recommendation: {result['insights'].get('recommendation', 'N/A')}")
        print()
        
        # 2. Preview the tweet format
        print("👀 Previewing tweet format...")
        response = await client.get(f"{BASE_URL}/parlays/{parlay_id}/format")
        preview = response.json()
        
        print("=" * 60)
        print(preview['tweet_text'])
        print("=" * 60)
        print(f"Character count: {preview['character_count']}/280")
        print()
        
        # 3. Get detailed insights
        print("🔍 Getting insights from similar parlays...")
        response = await client.get(f"{BASE_URL}/parlays/{parlay_id}/insights")
        insights = response.json()
        
        if insights.get('similar_parlays'):
            print(f"Found {len(insights['similar_parlays'])} similar parlays:")
            for p in insights['similar_parlays'][:3]:
                print(f"  - {p['title']} (similarity: {p['similarity']:.2f}, status: {p['status']})")
        print()
        
        # 4. Post to Twitter (commented out by default)
        # Uncomment to actually post to Twitter
        """
        print("🐦 Posting to Twitter...")
        response = await client.post(
            f"{BASE_URL}/parlays/{parlay_id}/post-twitter",
            params={"as_thread": False}
        )
        tweet_result = response.json()
        
        print(f"✅ Posted to Twitter!")
        print(f"   Tweet ID: {tweet_result['tweet_id']}")
        print(f"   URL: {tweet_result['url']}")
        print()
        """
        
        # 5. Search for similar parlays
        print("🔎 Searching for similar parlays...")
        response = await client.post(
            f"{BASE_URL}/parlays/search",
            json={
                "query": "high confidence NBA home favorites with strong offense",
                "limit": 5,
                "sport": "NBA"
            }
        )
        search_results = response.json()
        
        print(f"Found {len(search_results)} matching parlays:")
        for p in search_results:
            print(f"  - {p['title']} (similarity: {p['similarity']:.2f})")
        print()
        
        # 6. List recent parlays
        print("📋 Listing recent parlays...")
        response = await client.get(
            f"{BASE_URL}/parlays",
            params={"sport": "NBA", "limit": 5}
        )
        parlays = response.json()
        
        print(f"Recent NBA parlays ({len(parlays)}):")
        for p in parlays:
            print(f"  - {p['title']} ({p['confidence_level']}, odds: {p['total_odds']:+.0f})")
        print()
        
        return parlay_id


async def update_parlay_results(parlay_id: str):
    """Update parlay results after games complete"""
    
    # Example: Parlay won
    update_data = {
        "status": "won",
        "result": {
            "leg_1": "won",
            "leg_2": "won",
            "leg_3": "won"
        },
        "actual_return": 5.25
    }
    
    async with httpx.AsyncClient() as client:
        print(f"📊 Updating results for {parlay_id}...")
        response = await client.post(
            f"{BASE_URL}/parlays/{parlay_id}/update",
            json=update_data
        )
        result = response.json()
        
        print(f"✅ Updated!")
        print(f"   Status: {result['status']}")
        print(f"   ROI: {result['roi']:.2f}%")
        print(f"   Profit/Loss: ${result['profit_loss']:.2f}")


async def get_performance_stats():
    """Get overall performance statistics"""
    
    async with httpx.AsyncClient() as client:
        print("📈 Getting performance statistics...")
        response = await client.get(f"{BASE_URL}/parlays/stats/performance")
        stats = response.json()
        
        if stats.get('total_parlays', 0) > 0:
            print(f"Total Parlays: {stats['total_parlays']}")
            print(f"Win Rate: {stats['win_rate']:.1f}%")
            print(f"Overall ROI: {stats['overall_roi']:.2f}%")
            print(f"Net Profit: ${stats['net_profit']:.2f}")
            print()
            
            print("Performance by Sport:")
            for sport, sport_stats in stats['by_sport'].items():
                print(f"  {sport}: {sport_stats['won']}-{sport_stats['lost']} "
                      f"(ROI: {sport_stats['roi']:.2f}%)")
        else:
            print("No completed parlays yet")


async def main():
    """Run example workflow"""
    
    print("=" * 60)
    print("PARLAY SYSTEM EXAMPLE - Dan's AI Sports Picks Style")
    print("=" * 60)
    print()
    
    try:
        # Create example parlay
        parlay_id = await create_example_parlay()
        
        # Uncomment to update results (after games complete)
        # await update_parlay_results(parlay_id)
        
        # Get performance stats
        await get_performance_stats()
        
        print("=" * 60)
        print("Example completed successfully! 🎉")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
