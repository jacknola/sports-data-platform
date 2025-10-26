"""
Odds Agent - Specialized in fetching and analyzing betting odds
"""
from typing import Dict, Any
from loguru import logger

from app.agents.base_agent import BaseAgent
from app.services.sports_api import SportsAPIService


class OddsAgent(BaseAgent):
    """Agent responsible for odds data collection and analysis"""
    
    def __init__(self):
        super().__init__("OddsAgent")
        self.sports_api = SportsAPIService()
        self.threshold = 0.05  # Minimum edge to consider
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch and analyze odds for a sport"""
        sport = task.get('sport', 'nfl')
        
        logger.info(f"OddsAgent: Fetching odds for {sport}")
        
        try:
            # Fetch odds from APIs
            odds_data = await self.sports_api.get_odds(sport)
            
            # Analyze for value
            value_bets = self._identify_value_bets(odds_data)
            
            result = {
                'status': 'success',
                'sport': sport,
                'total_markets': len(odds_data),
                'value_bets': value_bets,
                'agent': self.name
            }
            
            self.record_execution(task, result)
            return result
            
        except Exception as e:
            logger.error(f"OddsAgent error: {e}")
            self.record_mistake({
                'task_type': 'fetch_odds',
                'sport': sport,
                'error': str(e)
            })
            raise
    
    def _identify_value_bets(self, odds_data: list) -> list:
        """Identify betting opportunities with positive expected value"""
        value_bets = []
        
        for market in odds_data:
            # Calculate if there's value
            for selection in market.get('selections', []):
                # Simplified value calculation
                edge = selection.get('edge', 0)
                if edge >= self.threshold:
                    value_bets.append(selection)
        
        return value_bets
    
    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """Learn from past mistakes"""
        mistake_type = mistake.get('type')
        
        if mistake_type == 'api_failure':
            # Increase retry attempts
            logger.info("Learning: Will increase retry attempts for API failures")
        
        elif mistake_type == 'data_quality':
            # Improve data validation
            logger.info("Learning: Will add more data validation checks")
        
        self.record_mistake(mistake)
    
    async def should_use_ai(self, task: Dict[str, Any]) -> bool:
        """Decide if AI should assist with odds analysis"""
        # Check if we've made similar mistakes before
        similar_mistakes = self._find_similar_mistakes(task)
        
        # Use AI if:
        # - High-value bet
        # - Complex market (props, parlays)
        # - Previous mistakes on similar tasks
        
        is_high_value = task.get('stake', 0) > 1000
        is_complex = task.get('market_type') in ['prop', 'parlay']
        
        return is_high_value or is_complex or len(similar_mistakes) > 0

