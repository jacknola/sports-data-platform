"""
Twitter data collection and analysis
"""
import tweepy
from typing import List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from app.config import settings
from app.services.ml_service import MLService


class TwitterAnalyzer:
    """Twitter data collection and sentiment analysis"""
    
    def __init__(self):
        self._ml_service = MLService()
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Twitter API client"""
        try:
            if not settings.TWITTER_BEARER_TOKEN:
                logger.warning("Twitter Bearer Token not configured")
                return
            
            self._client = tweepy.Client(
                bearer_token=settings.TWITTER_BEARER_TOKEN,
                consumer_key=settings.TWITTER_CONSUMER_KEY,
                consumer_secret=settings.TWITTER_CONSUMER_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                wait_on_rate_limit=True
            )
            
            logger.info("Twitter client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            self._client = None
    
    def search_tweets(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search for tweets
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of tweet dictionaries
        """
        if not self._client:
            return []
        
        try:
            tweets = self._client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics', 'author_id'],
                user_fields=['username', 'verified']
            )
            
            if not tweets.data:
                return []
            
            results = []
            for tweet in tweets.data:
                results.append({
                    'id': tweet.id,
                    'text': tweet.text,
                    'created_at': tweet.created_at.isoformat(),
                    'public_metrics': tweet.public_metrics,
                    'author_id': tweet.author_id
                })
            
            logger.info(f"Retrieved {len(results)} tweets for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Twitter search error: {e}")
            return []
    
    def analyze_team_sentiment(self, team_name: str, n_days: int = 7) -> Dict[str, Any]:
        """
        Analyze sentiment around a team
        
        Args:
            team_name: Name of the team
            n_days: Number of days to look back
            
        Returns:
            Dictionary with sentiment analysis
        """
        # Construct search query
        query = f"{team_name} -is:retweet lang:en"
        
        # Search for recent tweets
        tweets = self.search_tweets(query, max_results=100)
        
        if not tweets:
            return {
                'team': team_name,
                'total_tweets': 0,
                'sentiment': 'unknown',
                'error': 'No tweets found'
            }
        
        # Extract tweet texts
        tweet_texts = [tweet['text'] for tweet in tweets]
        
        # Analyze sentiment using ML service
        sentiment_result = self._ml_service.analyze_sentiment(tweet_texts)
        
        # Aggregate metrics
        total_likes = sum(tweet.get('public_metrics', {}).get('like_count', 0) for tweet in tweets)
        total_retweets = sum(tweet.get('public_metrics', {}).get('retweet_count', 0) for tweet in tweets)
        
        return {
            'team': team_name,
            'total_tweets': len(tweets),
            'date_range_days': n_days,
            'sentiment': sentiment_result.get('overall_sentiment', 'unknown'),
            'sentiment_confidence': sentiment_result.get('average_confidence', 0),
            'label_distribution': sentiment_result.get('label_distribution', {}),
            'engagement': {
                'total_likes': total_likes,
                'total_retweets': total_retweets,
                'avg_likes_per_tweet': total_likes / len(tweets) if tweets else 0,
                'avg_retweets_per_tweet': total_retweets / len(tweets) if tweets else 0
            },
            'sample_tweets': tweets[:5]  # Include first 5 tweets
        }

