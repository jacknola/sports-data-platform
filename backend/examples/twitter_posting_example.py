"""
Example of Twitter posting with different formats
"""
from app.services.twitter_analyzer import TwitterAnalyzer


def example_parlay_data():
    """Create example parlay data"""
    return {
        "title": "NBA Monday Night Special",
        "sport": "NBA",
        "confidence_level": "HIGH",
        "confidence_score": 88,
        "legs": [
            {
                "game": "Bucks vs Nets",
                "pick": "Bucks -5.5",
                "odds": -110,
                "reasoning": "Giannis dominates in big games",
                "team": "Bucks",
                "market": "spread"
            },
            {
                "game": "Suns vs Mavs",
                "pick": "Over 228.5",
                "odds": -105,
                "reasoning": "Both teams top 3 in pace",
                "team": "Suns",
                "market": "total"
            },
            {
                "game": "Nuggets vs Jazz",
                "pick": "Nuggets ML",
                "odds": -180,
                "reasoning": "Jokic unstoppable at altitude",
                "team": "Nuggets",
                "market": "moneyline"
            }
        ],
        "total_odds": 387,
        "potential_payout_multiplier": 4.87,
        "key_factors": [
            "All picks backed by advanced metrics",
            "Home court advantage on all selections",
            "Star players in prime spots"
        ],
        "analysis": "Elite value play targeting home favorites with elite star power"
    }


def main():
    """Demonstrate Twitter formatting"""
    
    twitter_analyzer = TwitterAnalyzer()
    parlay_data = example_parlay_data()
    
    print("=" * 60)
    print("TWITTER FORMATTING EXAMPLES")
    print("=" * 60)
    print()
    
    # 1. Format single tweet
    print("1. Single Tweet Format:")
    print("=" * 60)
    tweet_text = twitter_analyzer.format_dan_style_parlay(parlay_data)
    print(tweet_text)
    print("=" * 60)
    print(f"Length: {len(tweet_text)}/280 characters")
    print()
    
    # 2. Example with different sports
    print("\n2. Different Sports Examples:")
    print("=" * 60)
    
    sports_examples = {
        "NFL": {
            **parlay_data,
            "sport": "NFL",
            "title": "NFL Sunday Slate",
            "legs": [
                {
                    "game": "Chiefs vs Bills",
                    "pick": "Chiefs -3",
                    "odds": -110,
                    "reasoning": "Mahomes elite in big games",
                    "market": "spread"
                },
                {
                    "game": "49ers vs Eagles",
                    "pick": "Under 47.5",
                    "odds": -105,
                    "reasoning": "Elite defenses dominate",
                    "market": "total"
                }
            ],
            "total_odds": 264,
            "potential_payout_multiplier": 3.64
        },
        "MLB": {
            **parlay_data,
            "sport": "MLB",
            "title": "MLB Afternoon Special",
            "legs": [
                {
                    "game": "Yankees vs Red Sox",
                    "pick": "Yankees ML",
                    "odds": -140,
                    "reasoning": "Cole on the mound",
                    "market": "moneyline"
                }
            ],
            "total_odds": -140,
            "potential_payout_multiplier": 1.71
        }
    }
    
    for sport, data in sports_examples.items():
        print(f"\n{sport}:")
        print("-" * 60)
        formatted = twitter_analyzer.format_dan_style_parlay(data)
        print(formatted)
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print("✅ All examples formatted successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
