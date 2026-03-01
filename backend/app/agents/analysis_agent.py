"""
Analysis Agent - Orchestrates Bayesian and ML analysis
"""
from typing import Dict, Any
from loguru import logger

from app.agents.base_agent import BaseAgent
from app.services.bayesian import BayesianAnalyzer
from app.services.ml_service import MLService
from app.memory.agent_memory import AgentMemory


class AnalysisAgent(BaseAgent):
    """Agent responsible for running comprehensive analysis"""
    
    def __init__(self, memory: AgentMemory):
        super().__init__("AnalysisAgent")
        self.bayesian = BayesianAnalyzer()
        self.ml_service = MLService()
        self.memory = memory

    @classmethod
    async def create(cls) -> 'AnalysisAgent':
        """Creates and initializes an AnalysisAgent instance."""
        memory = await AgentMemory.create()
        return cls(memory)
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive analysis on a betting selection"""
        selection = task.get('selection')
        
        logger.info(f"AnalysisAgent: Analyzing selection {selection.get('id')}")
        
        try:
            # Check if we should use AI for this analysis
            use_ai = await self.should_use_ai(task)
            
            if use_ai:
                logger.info("Using AI for enhanced analysis")
                result = await self._run_ai_analysis(selection)
            else:
                result = await self._run_standard_analysis(selection)
            
            # Store decision for learning
            outcome_placeholder = {'timestamp': 'pending'}
            await self.memory.store_decision(
                self.name,
                task,
                outcome_placeholder,
                was_correct=True  # Will be updated later
            )
            
            self.record_execution(task, result)
            return result
            
        except Exception as e:
            logger.error(f"AnalysisAgent error: {e}")
            self.record_mistake({
                'task_type': 'analysis',
                'selection_id': selection.get('id'),
                'error': str(e)
            })
            raise
    
    async def _run_standard_analysis(self, selection: Dict[str, Any]) -> Dict[str, Any]:
        """Run standard analysis without AI"""
        # Bayesian analysis
        bayesian_result = self.bayesian.compute_posterior({
            'selection_id': selection.get('id'),
            'devig_prob': selection.get('devig_prob'),
            'implied_prob': selection.get('implied_prob'),
            'features': selection.get('features', {})
        })
        
        return {
            'method': 'standard',
            'bayesian': bayesian_result,
            'ai_assisted': False
        }
    
    async def _run_ai_analysis(self, selection: Dict[str, Any]) -> Dict[str, Any]:
        """Run AI-enhanced analysis"""
        # Get context from memory
        context = await self.memory.retrieve_similar_decisions(
            self.name,
            {'sport': selection.get('sport')}
        )
        
        # Run standard analysis
        bayesian_result = self.bayesian.compute_posterior({
            'selection_id': selection.get('id'),
            'devig_prob': selection.get('devig_prob'),
            'implied_prob': selection.get('implied_prob'),
            'features': selection.get('features', {})
        })
        
        # Add AI insights based on similar past decisions
        ai_confidence = await self.memory.get_confidence_estimate(
            self.name,
            {'selection_type': selection.get('market_type')}
        )
        
        return {
            'method': 'ai_enhanced',
            'bayesian': bayesian_result,
            'ai_confidence': ai_confidence,
            'context_used': len(context),
            'ai_assisted': True
        }
    
    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """Learn from analysis mistakes"""
        mistake_type = mistake.get('type')
        
        if mistake_type == 'probabilty_estimation':
            # Adjust Bayesian priors
            logger.info("Learning: Adjusting Bayesian priors")
        
        elif mistake_type == 'feature_weighting':
            # Re-weight features
            logger.info("Learning: Re-evaluating feature weights")
        
        # Update memory
        await self.memory.log_mistake(self.name, mistake)

