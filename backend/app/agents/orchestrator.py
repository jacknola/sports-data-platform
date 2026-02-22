"""
Orchestrator Agent - Coordinates multiple agents
"""
from typing import Dict, Any, List
from loguru import logger

from app.agents.odds_agent import OddsAgent
from app.agents.analysis_agent import AnalysisAgent
from app.agents.twitter_agent import TwitterAgent
from app.agents.expert_agent import ExpertAgent
from app.agents.scraping_agent import ScrapingAgent
from app.agents.dvp_agent import DvPAgent
from app.memory.agent_memory import AgentMemory


class OrchestratorAgent:
    """Orchestrates multiple agents to accomplish complex tasks"""
    
    def __init__(self):
        self.odds_agent = OddsAgent()
        self.analysis_agent = AnalysisAgent()
        self.twitter_agent = TwitterAgent()
        self.expert_agent = ExpertAgent()
        self.scraping_agent = ScrapingAgent()
        self.dvp_agent = DvPAgent()
        self.memory = AgentMemory()
    
    async def execute_full_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute full analysis workflow using multiple agents
        
        Args:
            task: Contains sport, date, teams, etc.
            
        Returns:
            Comprehensive analysis results
        """
        sport = task.get('sport', 'nfl')
        teams = task.get('teams', [])
        
        logger.info(f"Orchestrator: Starting full analysis for {sport}")
        
        results = {
            'sport': sport,
            'agents_used': [],
            'odds': None,
            'sentiment': [],
            'analysis': [],
            'ai_enhanced': False
        }
        
        try:
            # Step 1: Fetch odds
            logger.info("Step 1: Fetching odds...")
            odds_task = {'sport': sport}
            odds_result = await self.odds_agent.execute(odds_task)
            results['odds'] = odds_result
            results['agents_used'].append('OddsAgent')
            
            # Step 2: Scrape news and stats
            logger.info("Step 2: Scraping sports news and stats...")
            scraped_data = []
            for team in teams:
                try:
                    news_task = {
                        'url': f'https://www.espn.com/nfl/team/_/name/{team}',
                        'data_type': 'news',
                        'team': team
                    }
                    news_result = await self.scraping_agent.execute(news_task)
                    scraped_data.append(news_result)
                    results['agents_used'].append('ScrapingAgent')
                except Exception as e:
                    logger.warning(f"Failed to scrape news for {team}: {e}")
            
            results['scraped_data'] = scraped_data
            
            # Step 3: Analyze Twitter sentiment for each team
            logger.info("Step 3: Analyzing Twitter sentiment...")
            for team in teams:
                sentiment_task = {
                    'target': team,
                    'target_type': 'team',
                    'days': 7
                }
                sentiment_result = await self.twitter_agent.execute(sentiment_task)
                results['sentiment'].append(sentiment_result)
                results['agents_used'].append('TwitterAgent')
            
            # Step 4: Run Bayesian analysis on value bets
            logger.info("Step 4: Running Bayesian analysis...")
            value_bets = odds_result.get('value_bets', [])
            
            for bet in value_bets[:5]:  # Analyze top 5 value bets
                analysis_task = {
                    'selection': bet,
                    'sport': sport
                }
                
                # Check if AI should be used
                use_ai = await self.analysis_agent.should_use_ai(analysis_task)
                results['ai_enhanced'] = results['ai_enhanced'] or use_ai
                
                analysis_result = await self.analysis_agent.execute(analysis_task)
                results['analysis'].append(analysis_result)
                results['agents_used'].append('AnalysisAgent')
            
            # Step 5: Get expert recommendation using sequential thinking
            logger.info("Step 5: Getting expert recommendation...")
            if value_bets:
                expert_task = {
                    'bet_analysis': {
                        'market': value_bets[0].get('market'),
                        'teams': teams,
                        'sport': sport,
                        'edge': value_bets[0].get('edge'),
                        'posterior_prob': value_bets[0].get('posterior_p'),
                        'odds': value_bets[0].get('odds'),
                        'sentiment': {team: results['sentiment'][i] for i, team in enumerate(teams)}
                    }
                }
                expert_result = await self.expert_agent.execute(expert_task)
                results['expert_recommendation'] = expert_result
                results['agents_used'].append('ExpertAgent')
            
            # Record execution
            logger.info("Orchestrator: Full analysis complete")
            
            return results
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            raise
    
    async def learn_from_outcome(
        self,
        analysis_id: str,
        actual_outcome: Dict[str, Any],
        predictions: Dict[str, Any]
    ) -> None:
        """
        Learn from actual outcomes to improve future predictions
        
        Args:
            analysis_id: ID of the analysis
            actual_outcome: What actually happened
            predictions: What was predicted
        """
        logger.info(f"Orchestrator: Learning from outcome for analysis {analysis_id}")
        
        # Calculate prediction accuracy
        for prediction in predictions.get('analysis', []):
            was_correct = self._evaluate_prediction(prediction, actual_outcome)
            
            # Update agent memory
            await self.memory.store_decision(
                prediction.get('agent', 'unknown'),
                prediction,
                actual_outcome,
                was_correct
            )
            
            # If wrong, have agents learn from mistake
            if not was_correct:
                mistake = {
                    'type': 'prediction_error',
                    'predicted': prediction,
                    'actual': actual_outcome,
                    'context': {
                        'analysis_id': analysis_id
                    }
                }
                
                # Notify relevant agent
                if 'analysis' in prediction.get('agent', '').lower():
                    await self.analysis_agent.learn_from_mistake(mistake)
    
    def _evaluate_prediction(self, prediction: Dict[str, Any], outcome: Dict[str, Any]) -> bool:
        """Evaluate if a prediction was correct"""
        # Simplified evaluation
        return True  # Would implement actual evaluation logic
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            'orchestrator': 'active',
            'agents': {
                'odds': self.odds_agent.get_agent_status(),
                'scraping': self.scraping_agent.get_agent_status(),
                'analysis': self.analysis_agent.get_agent_status(),
                'twitter': self.twitter_agent.get_agent_status(),
                'expert': self.expert_agent.get_agent_status(),
                'dvp': self.dvp_agent.get_agent_status()
            }
        }

