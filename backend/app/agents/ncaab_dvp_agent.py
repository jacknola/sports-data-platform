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

        if task_type == "single_player":
            # For single player, we don't necessarily need the full slate load
            # if the team/opponent are provided in the task.
            # But we do need efficiency stats.
            await self.analyzer.fetch_team_efficiency()
            return await self._analyze_single_player(task)

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

        result = await self.analyzer.run_analysis(slate_data=slate_data)

        if task_type == "high_value_only":
            hv_plays = await self.analyzer.get_high_value_plays(result)
            result["projections"] = hv_plays
            result["count"] = len(hv_plays)

        return result

    async def _analyze_single_player(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze context for a single NCAAB player prop.
        
        Since we don't know if the player is on the Home or Away team,
        we return efficiency context for BOTH possibilities.
        """
        home = task.get("team_name")     # Orchestrator passes home as 'team_name'
        away = task.get("opponent_name") # Orchestrator passes away as 'opponent_name'
        player = task.get("player_name", "Unknown")
        prop_type = task.get("prop_type", "")
        
        if not home or not away:
            return {
                "error": "Missing team or opponent for single_player analysis",
                "task": task
            }

        # Ensure efficiency data is loaded
        if not self.analyzer.team_efficiency:
            await self.analyzer.fetch_team_efficiency()
            
        home_eff = self.analyzer.team_efficiency.get(home, {})
        away_eff = self.analyzer.team_efficiency.get(away, {})
        
        home_pace = home_eff.get("PACE", self.analyzer.league_avg_pace)
        away_pace = away_eff.get("PACE", self.analyzer.league_avg_pace)
        game_pace = (home_pace + away_pace) / 2.0
        pace_diff = ((game_pace - self.analyzer.league_avg_pace) / self.analyzer.league_avg_pace)
        pace_label = "FAST" if pace_diff > 0.05 else "SLOW" if pace_diff < -0.05 else "AVERAGE"

        # Scenario A: Player is on Home Team (faces Away Defense)
        away_drtg = away_eff.get("DRtg", self.analyzer.league_avg_drtg)
        drtg_diff_a = ((away_drtg - self.analyzer.league_avg_drtg) / self.analyzer.league_avg_drtg)
        matchup_a = "SOFT" if drtg_diff_a > 0.05 else "TOUGH" if drtg_diff_a < -0.05 else "AVERAGE"
        
        home_ortg = home_eff.get("ORtg", self.analyzer.league_avg_ortg)
        
        # Scenario B: Player is on Away Team (faces Home Defense)
        home_drtg = home_eff.get("DRtg", self.analyzer.league_avg_drtg)
        drtg_diff_b = ((home_drtg - self.analyzer.league_avg_drtg) / self.analyzer.league_avg_drtg)
        matchup_b = "SOFT" if drtg_diff_b > 0.05 else "TOUGH" if drtg_diff_b < -0.05 else "AVERAGE"
        
        away_ortg = away_eff.get("ORtg", self.analyzer.league_avg_ortg)

        return {
            "player": player,
            "prop_type": prop_type,
            "game_context": {
                "home_team": home,
                "away_team": away,
                "game_pace": round(game_pace, 1),
                "pace_label": pace_label,
            },
            "scenarios": {
                "if_player_on_home": {
                    "team": home,
                    "opponent": away,
                    "team_ortg": home_ortg,
                    "opp_drtg": away_drtg,
                    "matchup_difficulty": matchup_a
                },
                "if_player_on_away": {
                    "team": away,
                    "opponent": home,
                    "team_ortg": away_ortg,
                    "opp_drtg": home_drtg,
                    "matchup_difficulty": matchup_b
                }
            },
            "analysis_text": (
                f"{player} Prop Analysis ({home} vs {away})\n"
                f"Game Pace: {pace_label} ({game_pace:.1f})\n"
                f"If on {home}: Faces {matchup_a} defense (Opp DRtg {away_drtg})\n"
                f"If on {away}: Faces {matchup_b} defense (Opp DRtg {home_drtg})"
            )
        }

    async def learn_from_mistake(self, mistake: Dict[str, Any]) -> None:
        """Adapt from past mistakes."""
        mistake_type = mistake.get("type", "unknown")
        logger.info("NCAABDvPAgent learning from mistake: {}", mistake_type)
        self.record_mistake(mistake)
