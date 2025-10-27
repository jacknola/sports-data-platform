"""
Example usage of the data cleaning and storage system
"""
import requests
import json

BASE_URL = "http://localhost:8000"


def example_1_get_best_bets_with_storage():
    """
    Example 1: Get best bets and automatically store in database
    """
    print("\n=== Example 1: Get Best Bets with Auto Storage ===")
    
    response = requests.get(
        f"{BASE_URL}/bets",
        params={
            "sport": "nba",
            "min_edge": 0.05,
            "limit": 10,
            "store_data": True  # Automatically store in database
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Found {data['total_bets']} best bets")
        
        if data.get('storage'):
            storage = data['storage']
            print(f"✓ Storage: {storage['saved']} saved, {storage['updated']} updated, {storage['failed']} failed")
        
        # Display first bet
        if data['bets']:
            bet = data['bets'][0]
            print(f"\nTop Bet:")
            print(f"  Team: {bet['team']}")
            print(f"  Market: {bet['market']}")
            print(f"  Edge: {bet['edge']:.2%}")
            print(f"  Odds: {bet['current_odds']}")
    else:
        print(f"✗ Error: {response.status_code}")


def example_2_manual_storage():
    """
    Example 2: Manually store bets from external platform
    """
    print("\n=== Example 2: Manual Storage ===")
    
    # Raw data from sports platform (will be cleaned automatically)
    raw_bets = [
        {
            "sport": "basketball",  # Will be normalized to "NBA"
            "team": "Los Angeles Lakers  ",  # Extra spaces will be cleaned
            "market": "h2h",  # Will be normalized to "moneyline"
            "current_odds": "-150",  # Will be converted to float
            "edge": "8%",  # Will be converted to 0.08
            "probability": "60",  # Will be converted to 0.60
            "game": {
                "home_team": "Lakers",
                "away_team": "Warriors",
                "game_date": "2025-10-27T19:00:00Z"
            }
        },
        {
            "sport": "NBA",
            "team": "Warriors",
            "market": "spread",
            "current_odds": -110,
            "edge": 0.06,
            "probability": 0.55,
            "game": {
                "home_team": "Lakers",
                "away_team": "Warriors",
                "game_date": "2025-10-27T19:00:00Z"
            }
        }
    ]
    
    response = requests.post(
        f"{BASE_URL}/bets/store",
        json=raw_bets
    )
    
    if response.status_code == 200:
        data = response.json()
        results = data['results']
        print(f"✓ {data['message']}")
        print(f"✓ Saved: {results['saved']}, Updated: {results['updated']}, Failed: {results['failed']}")
        
        if results['errors']:
            print(f"✗ Errors: {results['errors']}")
    else:
        print(f"✗ Error: {response.status_code}")


def example_3_store_odds_api_data():
    """
    Example 3: Store odds data from Odds API format
    """
    print("\n=== Example 3: Store Odds API Data ===")
    
    # Example Odds API format data
    odds_data = [
        {
            "id": "game123",
            "sport_key": "basketball_nba",
            "commence_time": "2025-10-27T19:00:00Z",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Lakers", "price": -150},
                                {"name": "Warriors", "price": 130}
                            ]
                        },
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Lakers", "price": -110, "point": -5.5},
                                {"name": "Warriors", "price": -110, "point": 5.5}
                            ]
                        }
                    ]
                }
            ]
        }
    ]
    
    response = requests.post(
        f"{BASE_URL}/odds/store",
        json=odds_data
    )
    
    if response.status_code == 200:
        data = response.json()
        results = data['results']
        print(f"✓ {data['message']}")
        print(f"✓ Games: {results['games_saved']}")
        print(f"✓ Bets saved: {results['bets_saved']}, updated: {results['bets_updated']}")
    else:
        print(f"✗ Error: {response.status_code}")


def example_4_retrieve_stored_bets():
    """
    Example 4: Retrieve stored bets from database
    """
    print("\n=== Example 4: Retrieve Stored Bets ===")
    
    response = requests.get(
        f"{BASE_URL}/bets/stored",
        params={
            "sport": "NBA",
            "min_edge": 0.05,
            "limit": 5
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Found {data['total']} stored bets")
        
        for i, bet in enumerate(data['bets'][:3], 1):
            print(f"\nBet {i}:")
            print(f"  Team: {bet['team']}")
            print(f"  Market: {bet['market']}")
            print(f"  Edge: {bet['edge']:.2%}" if bet['edge'] else "  Edge: N/A")
            print(f"  Odds: {bet['current_odds']}")
            
            if bet.get('game'):
                game = bet['game']
                print(f"  Game: {game['away_team']} @ {game['home_team']}")
    else:
        print(f"✗ Error: {response.status_code}")


def example_5_fetch_and_store_odds():
    """
    Example 5: Fetch odds from external API and store
    """
    print("\n=== Example 5: Fetch and Store Odds ===")
    
    response = requests.get(
        f"{BASE_URL}/odds/nba",
        params={
            "store_data": True
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Fetched odds for {data['total_games']} games")
        
        if data.get('storage'):
            storage = data['storage']
            print(f"✓ Stored {storage['games_saved']} games")
            print(f"✓ Bets: {storage['bets_saved']} saved, {storage['bets_updated']} updated")
    else:
        print(f"✗ Error: {response.status_code}")


if __name__ == "__main__":
    print("=" * 60)
    print("Data Cleaning and Storage System Examples")
    print("=" * 60)
    
    try:
        # Run all examples
        example_1_get_best_bets_with_storage()
        example_2_manual_storage()
        example_3_store_odds_api_data()
        example_4_retrieve_stored_bets()
        example_5_fetch_and_store_odds()
        
        print("\n" + "=" * 60)
        print("All examples completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server")
        print("Make sure the backend server is running:")
        print("  cd backend && python main.py")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
