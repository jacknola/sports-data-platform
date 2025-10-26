"""
Base agent class for all agents in the system
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger


class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system"""
    
    def __init__(self, name: str):
        self.name = name
        self.agent_id = f"{name}_{datetime.now().timestamp()}"
        self.history: List[Dict[str, Any]] = []
        self.mistakes: List[Dict[str, Any]] = []
        logger.info(f"Initialized agent: {self.name}")
    
    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent task
        
        Args:
            task: Task to execute
            
        Returns:
            Execution result
        """
        pass
    
    @abstractmethod
    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """
        Learn from past mistakes
        
        Args:
            mistake: Mistake information with context and correction
        """
        pass
    
    def record_execution(self, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Record execution in history"""
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'task': task,
            'result': result,
            'agent': self.name
        })
        logger.info(f"Agent {self.name} recorded execution")
    
    def record_mistake(self, mistake: Dict[str, Any]) -> None:
        """Record a mistake for future learning"""
        self.mistakes.append({
            'timestamp': datetime.now().isoformat(),
            'agent': self.name,
            **mistake
        })
        logger.warning(f"Agent {self.name} recorded mistake: {mistake.get('type', 'unknown')}")
    
    async def should_use_ai(self, task: Dict[str, Any]) -> bool:
        """
        Determine if AI should be used for this task
        
        Args:
            task: Task to evaluate
            
        Returns:
            True if AI should be used
        """
        # Check if similar mistakes have been made
        similar_mistakes = self._find_similar_mistakes(task)
        
        # Use AI if:
        # 1. Task is complex
        # 2. Similar mistakes exist
        # 3. Confidence threshold is low
        
        if task.get('complexity', 0) > 7:
            return True
        
        if similar_mistakes and len(similar_mistakes) > 2:
            return True
        
        if task.get('confidence_required', 0) > 0.8:
            return True
        
        return False
    
    def _find_similar_mistakes(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar past mistakes"""
        # Simple similarity check based on task type
        task_type = task.get('type', '')
        return [m for m in self.mistakes if m.get('task_type') == task_type]
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get agent status and statistics"""
        return {
            'name': self.name,
            'id': self.agent_id,
            'total_executions': len(self.history),
            'total_mistakes': len(self.mistakes),
            'mistake_rate': len(self.mistakes) / max(len(self.history), 1),
            'recent_mistakes': self.mistakes[-5:] if len(self.mistakes) > 5 else self.mistakes
        }

