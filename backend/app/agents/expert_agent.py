"""
Expert Agent - Uses sequential thinking for expert-level betting decisions
"""
from typing import Dict, Any
from loguru import logger

from app.agents.base_agent import BaseAgent
from app.services.sequential_thinking import SequentialThinkingService
from app.services.similarity_search import SimilaritySearchService


class ExpertAgent(BaseAgent):
    """
    Agent that uses sequential thinking to make expert-level sports betting decisions
    """
    
    def __init__(self):
        super().__init__("ExpertAgent")
        self.thinking_service = SequentialThinkingService()
        self.similarity_service = SimilaritySearchService()
        self.expertise_level = "Professional"
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute expert analysis using sequential thinking
        
        Args:
            task: Betting decision task
            
        Returns:
            Expert recommendation
        """
        bet_analysis = task.get('bet_analysis', {})
        
        logger.info(f"ExpertAgent: Analyzing bet for {bet_analysis.get('market')}")
        
        try:
            # Step 1: Research the market context using NotebookLM
            market = bet_analysis.get('market', 'unknown')
            sport = bet_analysis.get('sport', 'unknown')
            teams = bet_analysis.get('teams', [])
            
            research_query = f"{sport} {market} for {' vs '.join(teams)}"
            logger.info(f"ExpertAgent: Researching topic: {research_query}")
            
            research_findings = await self.thinking_service.research_topic(research_query)
            
            # Step 2: Retrieve similar historical situational context (RAG)
            logger.info("ExpertAgent: Performing situational similarity search")
            historical_analogs = self.similarity_service.find_similar_games(bet_analysis, limit=3)
            
            # Step 3: Use sequential thinking to make expert decision
            # Add research and historical findings to context
            bet_analysis['research_findings'] = research_findings
            bet_analysis['historical_analogs'] = historical_analogs
            
            expert_decision = await self.thinking_service.decide_if_bet(bet_analysis)
            
            # Record execution
            result = {
                'status': 'success',
                'agent': self.name,
                'expertise_level': self.expertise_level,
                'decision': expert_decision,
                'thinking_process': expert_decision.get('thinking_process'),
                'research': research_findings
            }
            
            self.record_execution(task, result)
            return result
            
        except Exception as e:
            logger.error(f"ExpertAgent error: {e}")
            self.record_mistake({
                'task_type': 'expert_analysis',
                'market': bet_analysis.get('market'),
                'error': str(e)
            })
            raise
    
    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """Learn from expert mistakes"""
        mistake_type = mistake.get('type')
        
        if mistake_type == 'decision_error':
            logger.info("Learning: Adjusting decision thresholds")
            # Update thresholds based on mistake
        
        elif mistake_type == 'stake_sizing':
            logger.info("Learning: Refining stake calculation")
            # Adjust Kelly Criterion parameters
        
        self.record_mistake(mistake)
    
    async def should_use_ai(self, task: Dict[str, Any]) -> bool:
        """Expert agent always uses sequential thinking (AI)"""
        return True
    
    async def explain_reasoning(self, decision: Dict[str, Any]) -> str:
        """
        Provide detailed explanation of expert reasoning
        
        Args:
            decision: Expert decision result
            
        Returns:
            Human-readable explanation
        """
        thinking = decision.get('thinking_process', {})
        
        explanation = f"""
Expert Betting Analysis by {self.expertise_level} Sports Betting Professional

Decision: {decision.get('decision', {}).get('should_bet', False)}

Reasoning Process:
{self._format_thinking_steps(thinking.get('steps', []))}

Final Recommendation:
{decision.get('decision', {}).get('rationale', 'N/A')}

Confidence Level: {decision.get('decision', {}).get('confidence', 0):.0%}
"""
        return explanation.strip()
    
    def _format_thinking_steps(self, steps: list) -> str:
        """Format thinking steps for human reading"""
        formatted = ""
        for step in steps:
            formatted += f"\n{step.get('step')}. {step.get('title')}\n"
            formatted += f"   {step.get('detailed_reasoning')}\n"
        return formatted

