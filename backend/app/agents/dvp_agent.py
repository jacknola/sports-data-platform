"""
DvP (Defense vs. Position) Agent

Specialized agent that runs the NBADvPAnalyzer to identify +EV
player prop bets. Extends BaseAgent to plug into the multi-agent system
and support the platform's adaptive learning loop.
"""
from typing import Dict, Any, List
from loguru import logger

from app.agents.base_agent import BaseAgent
from app.services.nba_dvp_analyzer import NBADvPAnalyzer


class DvPAgent(BaseAgent):
    """Agent wrapper around the NBADvPAnalyzer service."""

    def __init__(self):
        super().__init__(name="dvp_agent")
        self.analyzer = NBADvPAnalyzer()
        logger.info("DvPAgent initialized")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a DvP analysis task.

        Supported task types:
            - "full_analysis"    : run complete DvP pipeline
            - "high_value_only"  : return only HIGH VALUE flagged plays
            - "single_player"    : project a specific player's line
            - "implied_totals"   : compute implied team totals only

        Args:
            task: Dict with keys:
                type          – one of the above task types
                slate_data    – optional slate override (dict)
                num_recent    – games window for rolling averages (default 15)
                export_csv    – optional CSV export path
                player_name   – required for "single_player" type
                stat_category – required for "single_player" type

        Returns:
            Analysis results as a serializable dict.
        """
        task_type = task.get("type", "full_analysis")
        logger.info("DvPAgent executing task: {}", task_type)

        try:
            result = await self._dispatch(task_type, task)
            self.record_execution(task, result)
            return result
        except Exception as e:
            error_info = {
                "type": "dvp_analysis_error",
                "task_type": task_type,
                "error": str(e),
            }
            self.record_mistake(error_info)
            logger.error("DvPAgent error: {}", e)
            return {"error": str(e), "task_type": task_type}

    async def _dispatch(self, task_type: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the correct analysis method."""
        slate_data = task.get("slate_data")
        num_recent = task.get("num_recent", 15)
        export_csv = task.get("export_csv")

        if task_type == "implied_totals":
            self.analyzer.load_slate(slate_data)
            totals = self.analyzer.compute_all_implied_totals()
            return {"implied_totals": totals}

        if task_type == "single_player":
            return self._analyze_single_player(task, slate_data, num_recent)

        # full_analysis or high_value_only
        df = self.analyzer.run_analysis(
            slate_data=slate_data,
            num_recent_games=num_recent,
            export_csv=export_csv,
        )

        if task_type == "high_value_only":
            df = self.analyzer.get_high_value_plays(df)

        records = df.to_dict(orient="records") if not df.empty else []
        return {
            "task_type": task_type,
            "count": len(records),
            "high_value_count": len(
                [r for r in records if "HIGH VALUE" in r.get("Recommendation", "")]
            ),
            "projections": records,
        }

    def _analyze_single_player(
        self,
        task: Dict[str, Any],
        slate_data: Any,
        num_recent: int,
    ) -> Dict[str, Any]:
        """Project a single player's line for a specific stat."""
        player_name = task.get("player_name", "")
        stat = task.get("stat_category", "PTS")

        # Run the full pipeline to populate internal state
        df = self.analyzer.run_analysis(
            slate_data=slate_data, num_recent_games=num_recent
        )

        if df.empty:
            return {"error": "No projections generated", "player": player_name}

        mask = (df["Player"] == player_name) & (df["Stat_Category"] == stat)
        match = df[mask]

        if match.empty:
            return {
                "error": f"Player '{player_name}' not found for stat '{stat}'",
                "available_players": df["Player"].unique().tolist(),
            }

        return match.iloc[0].to_dict()

    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """
        Adapt from past mistakes.

        For DvP analysis, the main failure modes are:
            - stale DvP data  → trigger data refresh
            - bad position mapping → log for manual review
            - missing players → expand baseline roster
        """
        mistake_type = mistake.get("type", "unknown")
        logger.info("DvPAgent learning from mistake: {}", mistake_type)

        if mistake_type == "stale_data":
            logger.info("Refreshing DvP data cache")
            self.analyzer.team_dvp = self.analyzer.fetch_team_dvp()
            self.analyzer.team_pace = self.analyzer.fetch_team_pace()

        if mistake_type == "position_mapping":
            logger.warning(
                "Position mapping issue noted for player: {}",
                mistake.get("player", "unknown"),
            )

        self.record_mistake(mistake)
