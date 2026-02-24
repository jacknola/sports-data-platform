"""
Twitter data collection, analysis, and posting
Implements Dan's AI Sports Picks style parlay posting
"""
import tweepy
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from app.config import settings
from app.services.ml_service import MLService


class TwitterAnalyzer:
    """Twitter data collection, sentiment analysis, and parlay posting"""
    
    def __init__(self):
        self._ml_service = MLService()
        self._client = None
        self._api = None  # For v1.1 API (posting)
        self._init_client()
    
    def _init_client(self):
        """Initialize Twitter API client (v2 and v1.1)"""
        try:
            if not settings.TWITTER_BEARER_TOKEN:
                logger.warning("Twitter Bearer Token not configured")
                return
            
            # V2 API client (for reading tweets)
            self._client = tweepy.Client(
                bearer_token=settings.TWITTER_BEARER_TOKEN,
                consumer_key=settings.TWITTER_CONSUMER_KEY,
                consumer_secret=settings.TWITTER_CONSUMER_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                wait_on_rate_limit=True
            )
            
            # V1.1 API for posting tweets with better formatting
            auth = tweepy.OAuth1UserHandler(
                settings.TWITTER_CONSUMER_KEY,
                settings.TWITTER_CONSUMER_SECRET,
                settings.TWITTER_ACCESS_TOKEN,
                settings.TWITTER_ACCESS_TOKEN_SECRET
            )
            self._api = tweepy.API(auth, wait_on_rate_limit=True)
            
            logger.info("Twitter client initialized (v2 and v1.1)")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            self._client = None
            self._api = None
    
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
    
    def format_dan_style_parlay(self, parlay_data: Dict[str, Any]) -> str:
        """
        Format parlay in Dan's AI Sports Picks style
        
        Args:
            parlay_data: Parlay data with legs, odds, analysis
            
        Returns:
            Formatted tweet text
        """
        lines = []
        
        # Title with emoji
        sport_emoji = {
            'NBA': '🏀',
            'NFL': '🏈',
            'MLB': '⚾',
            'NHL': '🏒',
            'Soccer': '⚽'
        }.get(parlay_data.get('sport', ''), '🎯')
        
        title = parlay_data.get('title', 'Daily Parlay')
        confidence = parlay_data.get('confidence_level', 'MEDIUM')
        
        # Header
        lines.append(f"{sport_emoji} {title.upper()}")
        lines.append(f"Confidence: {confidence} 🔥")
        lines.append("")
        
        # Parlay legs
        legs = parlay_data.get('legs', [])
        for i, leg in enumerate(legs, 1):
            game = leg.get('game', '')
            pick = leg.get('pick', '')
            odds = leg.get('odds', 0)
            
            # Format odds
            odds_str = self._format_odds(odds)
            
            lines.append(f"{i}. {pick} ({odds_str})")
            
            # Add reasoning if available and space permits
            reasoning = leg.get('reasoning', '')
            if reasoning and len(reasoning) < 60:
                lines.append(f"   └ {reasoning}")
        
        lines.append("")
        
        # Total odds and payout
        total_odds = parlay_data.get('total_odds', 0)
        payout_mult = parlay_data.get('potential_payout_multiplier', 0)
        
        lines.append(f"💰 Parlay Odds: {self._format_odds(total_odds)}")
        lines.append(f"💵 Payout: {payout_mult:.2f}x")
        lines.append("")
        
        # Key factors (if space permits)
        key_factors = parlay_data.get('key_factors', [])
        if key_factors:
            lines.append("📊 Key Factors:")
            for factor in key_factors[:2]:  # Limit to 2 for space
                lines.append(f"• {factor}")
            lines.append("")
        
        # Call to action
        lines.append("🎯 BOL! #SportsBetting #Parlay")
        
        tweet = '\n'.join(lines)
        
        # Ensure under 280 characters
        if len(tweet) > 280:
            # Trim and add ellipsis
            tweet = tweet[:277] + "..."
        
        return tweet
    
    def _format_odds(self, odds: float) -> str:
        """Format odds as American odds string"""
        if odds >= 0:
            return f"+{int(odds)}"
        return str(int(odds))
    
    def post_parlay_tweet(self, parlay_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Post a parlay to Twitter in Dan's style
        
        Args:
            parlay_data: Parlay data
            
        Returns:
            Tweet data including tweet ID
        """
        if not self._client:
            logger.warning("Twitter client not initialized")
            return None
        
        try:
            # Format the tweet
            tweet_text = self.format_dan_style_parlay(parlay_data)
            
            # Post tweet
            response = self._client.create_tweet(text=tweet_text)
            
            tweet_id = response.data['id']
            
            logger.info(f"Posted parlay tweet: {tweet_id}")
            
            return {
                'tweet_id': tweet_id,
                'tweet_text': tweet_text,
                'posted_at': datetime.now().isoformat(),
                'url': f"https://twitter.com/i/web/status/{tweet_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to post parlay tweet: {e}")
            return None
    
    def post_parlay_thread(
        self,
        parlay_data: Dict[str, Any],
        include_detailed_analysis: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Post a parlay as a Twitter thread with detailed analysis
        
        Args:
            parlay_data: Parlay data
            include_detailed_analysis: Include detailed leg-by-leg analysis
            
        Returns:
            List of tweet data for the thread
        """
        if not self._client:
            logger.warning("Twitter client not initialized")
            return None
        
        try:
            tweets = []
            
            # First tweet: Main parlay summary
            main_tweet_text = self.format_dan_style_parlay(parlay_data)
            main_response = self._client.create_tweet(text=main_tweet_text)
            main_tweet_id = main_response.data['id']
            
            tweets.append({
                'tweet_id': main_tweet_id,
                'text': main_tweet_text,
                'type': 'main'
            })
            
            # Follow-up tweets with detailed analysis
            if include_detailed_analysis:
                legs = parlay_data.get('legs', [])
                
                for i, leg in enumerate(legs, 1):
                    analysis_text = self._format_leg_analysis(leg, i)
                    
                    reply_response = self._client.create_tweet(
                        text=analysis_text,
                        in_reply_to_tweet_id=main_tweet_id
                    )
                    
                    tweets.append({
                        'tweet_id': reply_response.data['id'],
                        'text': analysis_text,
                        'type': 'leg_analysis',
                        'leg_number': i
                    })
            
            # Final tweet with overall analysis
            if parlay_data.get('analysis'):
                final_text = f"📈 Overall Analysis:\n\n{parlay_data['analysis'][:240]}\n\n#SportsBetting"
                
                final_response = self._client.create_tweet(
                    text=final_text,
                    in_reply_to_tweet_id=main_tweet_id
                )
                
                tweets.append({
                    'tweet_id': final_response.data['id'],
                    'text': final_text,
                    'type': 'overall_analysis'
                })
            
            logger.info(f"Posted parlay thread with {len(tweets)} tweets")
            return tweets
            
        except Exception as e:
            logger.error(f"Failed to post parlay thread: {e}")
            return None
    
    def _format_leg_analysis(self, leg: Dict[str, Any], leg_number: int) -> str:
        """Format detailed analysis for a single leg"""
        lines = [f"Leg {leg_number} Analysis: {leg.get('pick', '')}"]
        lines.append("")
        lines.append(f"🎯 Game: {leg.get('game', '')}")
        lines.append(f"📊 Reasoning: {leg.get('reasoning', '')}")
        
        supporting_factors = leg.get('supporting_factors', [])
        if supporting_factors:
            lines.append("")
            lines.append("✅ Supporting Factors:")
            for factor in supporting_factors[:3]:
                lines.append(f"• {factor}")
        
        tweet = '\n'.join(lines)
        
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        
        return tweet
    
    def get_parlay_engagement(self, tweet_id: str) -> Dict[str, Any]:
        """
        Get engagement metrics for a parlay tweet
        
        Args:
            tweet_id: Tweet ID
            
        Returns:
            Engagement metrics
        """
        if not self._client:
            return {}
        
        try:
            tweet = self._client.get_tweet(
                tweet_id,
                tweet_fields=['public_metrics', 'created_at']
            )
            
            if tweet.data:
                metrics = tweet.data.public_metrics
                return {
                    'tweet_id': tweet_id,
                    'likes': metrics.get('like_count', 0),
                    'retweets': metrics.get('retweet_count', 0),
                    'replies': metrics.get('reply_count', 0),
                    'impressions': metrics.get('impression_count', 0),
                    'created_at': tweet.data.created_at.isoformat()
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get tweet engagement: {e}")
            return {}

