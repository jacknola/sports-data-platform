"""
Twitter Agent - Monitors and analyzes Twitter sentiment
"""
from typing import Dict, Any
from loguru import logger

from app.agents.base_agent import BaseAgent
from app.services.twitter_analyzer import TwitterAnalyzer


class TwitterAgent(BaseAgent):
    """Agent responsible for Twitter data collection and sentiment analysis"""
    
    def __init__(self):
        super().__init__("TwitterAgent")
        self.twitter_analyzer = TwitterAnalyzer()
        self.confidence_threshold = 0.7
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze Twitter sentiment for a team or player"""
        target = task.get('target')
        target_type = task.get('target_type', 'team')
        n_days = task.get('days', 7)
        
        logger.info(f"TwitterAgent: Analyzing {target_type} {target}")
        
        try:
            # Get sentiment analysis
            sentiment_data = await self.twitter_analyzer.analyze_team_sentiment(target, n_days)
            
            # Check confidence
            confidence = sentiment_data.get('sentiment_confidence', 0)
            
            # Record if low confidence for learning
            if confidence < self.confidence_threshold:
                self.record_mistake({
                    'task_type': 'sentiment_analysis',
                    'target': target,
                    'confidence': confidence,
                    'reason': 'low_confidence'
                })
            
            result = {
                'status': 'success',
                'target': target,
                'target_type': target_type,
                'sentiment': sentiment_data,
                'agent': self.name
            }
            
            self.record_execution(task, result)
            return result
            
        except Exception as e:
            logger.error(f"TwitterAgent error: {e}")
            self.record_mistake({
                'task_type': 'twitter_fetch',
                'target': target,
                'error': str(e)
            })
            raise
    
    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """Learn from Twitter sentiment mistakes"""
        mistake_type = mistake.get('type')
        
        if mistake_type == 'low_confidence':
            # Adjust sentiment thresholds
            logger.info("Learning: Lowering confidence threshold")
            self.confidence_threshold *= 0.95
        
        elif mistake_type == 'api_rate_limit':
            # Implement better rate limiting
            logger.info("Learning: Adding exponential backoff")
        
        self.record_mistake(mistake)
    
    async def should_use_ai(self, task: Dict[str, Any]) -> bool:
        """Decide if AI should be used for sentiment analysis"""
        # Use AI for important events or controversial topics
        is_important = task.get('importance', 0) > 7
        has_controversy = task.get('controversy_detected', False)
        
        similar_mistakes = self._find_similar_mistakes(task)
        
        return is_important or has_controversy or len(similar_mistakes) > 1

