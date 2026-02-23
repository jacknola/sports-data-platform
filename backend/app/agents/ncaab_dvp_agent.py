"""
NCAAB DvP (Efficiency) Agent

Specialized agent that runs the NCAABDvPAnalyzer to identify +EV
game total and team total opportunities in college basketball.
Extends BaseAgent to plug into the multi-agent orchestrator.
"""
from typing import Dict, Any
from loguru import logger

from app.agents.base_agent import BaseAgent
from app.services.ncaab_dvp_analyzer import NCAABDvPAnalyzer


class NCAABDvPAgent(BaseAgent):
    """Agent wrapper around the NCAABDvPAnalyzer service."""

    def __init__(self):
        super().__init__(name="ncaab_dvp_agent")
        self.analyzer = NCAABDvPAnalyzer()
        logger.info("NCAABDvPAgent initialized")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a NCAAB efficiency analysis task.

        Supported task types:
            - "full_analysis"    : run complete efficiency pipeline
            - "high_value_only"  : return only HIGH VALUE flagged plays
            - "implied_totals"   : compute implied team totals only

        Args:
            task: Dict with keys:
                type       – one of the above task types
                slate_data – optional slate override (dict)

        Returns:
            Analysis results as a serializable dict.
        """
        task_type = task.get("type", "full_analysis")
        logger.info("NCAABDvPAgent executing task: {}", task_type)

        try:
            result = await self._dispatch(task_type, task)
            self.record_execution(task, result)
            return result
        except Exception as e:
            error_info = {
                "type": "ncaab_dvp_analysis_error",
                "task_type": task_type,
                "error": str(e),
            }
            self.record_mistake(error_info)
            logger.error("NCAABDvPAgent error: {}", e)
            return {"error": str(e), "task_type": task_type}

    async def _dispatch(self, task_type: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the correct analysis method."""
        slate_data = task.get("slate_data")

        if task_type == "implied_totals":
            self.analyzer.load_slate(slate_data)
            totals = self.analyzer.compute_all_implied_totals()
            return {"implied_totals": totals}

        # Auto-populate slate from Odds API when no explicit slate is provided
        if not slate_data:
            try:
                await self.analyzer.load_slate_from_odds_api()
            except Exception as e:
                logger.warning("Odds API slate failed for NCAAB, using file slate: {}", e)
                self.analyzer.load_slate()

        result = self.analyzer.run_analysis(slate_data=slate_data)

        if task_type == "high_value_only":
            hv_plays = self.analyzer.get_high_value_plays(result)
            result["projections"] = hv_plays
            result["count"] = len(hv_plays)

        return result

    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """Adapt from past mistakes."""
        mistake_type = mistake.get("type", "unknown")
        logger.info("NCAABDvPAgent learning from mistake: {}", mistake_type)
        self.record_mistake(mistake)
