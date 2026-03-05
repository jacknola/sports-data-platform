"""
Orchestrator Agent - Coordinates multiple agents
"""

from typing import Dict, Any
from loguru import logger

from app.agents.odds_agent import OddsAgent
from app.agents.analysis_agent import AnalysisAgent
from app.agents.expert_agent import ExpertAgent
from app.agents.dvp_agent import DvPAgent
from app.agents.ncaab_dvp_agent import NCAABDvPAgent
from app.memory.agent_memory import AgentMemory


class OrchestratorAgent:
    """Orchestrates multiple agents to accomplish complex tasks"""

    def __init__(self, odds_agent, analysis_agent, expert_agent, dvp_agent, ncaab_dvp_agent, memory, twitter_agent):
        self.odds_agent = odds_agent
        self.analysis_agent = analysis_agent
        self.expert_agent = expert_agent
        self.dvp_agent = dvp_agent
        self.ncaab_dvp_agent = ncaab_dvp_agent
        self.memory = memory
        self.twitter_agent = twitter_agent

    @classmethod
    async def create(cls) -> "OrchestratorAgent":
        """Creates and initializes an OrchestratorAgent instance with all sub-agents."""
        logger.info("Initializing OrchestratorAgent and sub-agents...")
        
        # Initialize async agents
        analysis_agent = await AnalysisAgent.create()
        memory = await AgentMemory.create()

        # Initialize sync agents
        odds_agent = OddsAgent()
        expert_agent = ExpertAgent()
        dvp_agent = DvPAgent()
        ncaab_dvp_agent = NCAABDvPAgent()
        
        twitter_agent = None
        try:
            from app.agents.twitter_agent import TwitterAgent
            twitter_agent = TwitterAgent()
            logger.info("TwitterAgent initialized.")
        except ImportError:
            logger.warning("TwitterAgent not found or could not be initialized.")

        return cls(
            odds_agent=odds_agent,
            analysis_agent=analysis_agent,
            expert_agent=expert_agent,
            dvp_agent=dvp_agent,
            ncaab_dvp_agent=ncaab_dvp_agent,
            memory=memory,
            twitter_agent=twitter_agent,
        )

    async def execute_prop_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute targeted analysis for a specific player prop using multiple agents.

        Args:
            task: Dict containing:
                sport (str)
                player_name (str)
                prop_type (str)

        Returns:
            Combined analysis result from OddsAgent and specialized DvPAgent.
        """
        sport = task.get("sport")
        player_name = task.get("player_name")
        prop_type = task.get("prop_type")

        logger.info(f"Orchestrator: Starting prop analysis for {player_name} ({sport})")

        results = {
            "sport": sport,
            "player": player_name,
            "prop_type": prop_type,
            "agents_used": [],
            "odds": None,
            "dvp_analysis": None,
        }

        try:
            # Step 1: Fetch prop odds/market info
            logger.info(f"Step 1: Fetching prop odds for {player_name}...")
            odds_task = {
                "type": "fetch_props",
                "sport": sport,
                "player_name": player_name,
                "prop_type": prop_type,
            }
            odds_result = await self.odds_agent.execute(odds_task)
            results["odds"] = odds_result
            results["agents_used"].append("OddsAgent")

            # Step 2: Run DvP/Efficiency analysis
            # We need team/opponent info from the odds result to proceed
            props = odds_result.get("props", [])
            if not props:
                logger.warning(f"No props found for {player_name}, skipping analysis.")
                return results

            # Assume first match is the correct game context
            # (In reality we might want to let user pick or aggregate)
            match_context = props[0]
            # Logic to determine player's team vs opponent requires knowing which side player is on.
            # However, `get_all_player_props` returns home_team and away_team.
            # We need to infer or fuzzy match player's team if not explicitly provided.
            # For now, let's pass both and let the specialized agent figure it out
            # OR we rely on what we have.

            # Note: Odds API prop response usually includes "team" field or we infer it.
            # Our `get_all_player_props` implementation returns 'home_team' and 'away_team'.
            # It doesn't strictly say which team the player is on without roster lookup.
            # BUT, for the specialized agents:
            # NBA DvP Agent has `run_analysis` which does roster lookup.
            # NCAAB DvP Agent `_analyze_single_player` takes team/opponent.

            # Let's invoke the appropriate agent with whatever context we have.
            logger.info("Step 2: Running specialized analysis...")

            analysis_task = {
                "type": "single_player",
                "player_name": player_name,
                "prop_type": prop_type,
                # Pass game context if available
                "home_team": match_context.get("home_team"),
                "away_team": match_context.get("away_team"),
                "event_id": match_context.get("event_id"),
            }

            # If we can infer team from Odds API metadata (sometimes unavailable), add it.
            # Otherwise we'll rely on the agent's internal lookup.

            if sport in ("basketball_nba", "nba"):
                # NBA Agent handles player lookup internally via nba_api
                dvp_result = await self.dvp_agent.execute(analysis_task)
                results["dvp_analysis"] = dvp_result
                results["agents_used"].append("DvPAgent")

            elif sport in ("basketball_ncaab", "ncaab"):
                # NCAAB Agent needs team/opponent.
                # Since we don't know which team the player is on easily (no roster API),
                # we might have a limitation here.
                # WORKAROUND: For now, we will try to pass both teams as context
                # and let the agent return efficiency metrics for the GAME.
                # In `_analyze_single_player`, we required team/opponent.
                # Let's update the task to map home/away to team/opponent if we knew.
                # Without roster data, we might just have to return game context.

                # However, for this implementation, we will pass home/away as team/opponent
                # strictly as a placeholder if we can't resolve it,
                # OR better: The user (Orchestrator) simply asks for efficiency stats for the GAME.

                # Let's pass the raw home/away and let NCAABDvPAgent handle "Game Context"
                # if it can't resolve the player's specific team.
                # We updated NCAABDvPAgent to expect `team_name` and `opponent_name`.
                # We will populate these from home/away, noting ambiguity.

                # Limitation: We don't know which is which.
                # Resolution: Pass `home_team` and `away_team` to the agent
                # and let it return efficiency for BOTH.

                analysis_task["team_name"] = match_context.get("home_team")
                analysis_task["opponent_name"] = match_context.get("away_team")

                dvp_result = await self.ncaab_dvp_agent.execute(analysis_task)
                results["dvp_analysis"] = dvp_result
                results["agents_used"].append("NCAABDvPAgent")

            return results

        except Exception as e:
            logger.error(f"Orchestrator prop analysis error: {e}")
            raise

    async def execute_full_analysis(
        self, task: Dict[str, Any], prediction_only: bool = False
    ) -> Dict[str, Any]:
        """
        Execute full analysis workflow using multiple agents

        Args:
            task: Contains sport, date, teams, etc.

        Returns:
            Comprehensive analysis results
        """
        sport = task.get("sport", "nfl")
        teams = task.get("teams", [])

        logger.info(f"Orchestrator: Starting full analysis for {sport}")

        results = {
            "sport": sport,
            "agents_used": [],
            "odds": None,
            "sentiment": [],
            "analysis": [],
            "ai_enhanced": False,
        }

        try:
            if prediction_only:
                odds_result = {"value_bets": []}
                results["odds"] = odds_result
            else:
                logger.info("Step 1: Fetching odds...")
                odds_task = {"sport": sport}
                odds_result = await self.odds_agent.execute(odds_task)
                results["odds"] = odds_result
                results["agents_used"].append("OddsAgent")

                logger.info("Step 3: Analyzing Twitter sentiment...")
                for team in teams:
                    sentiment_task = {"target": team, "target_type": "team", "days": 7}
                    sentiment_result = await self.twitter_agent.execute(sentiment_task)
                    results["sentiment"].append(sentiment_result)
                    results["agents_used"].append("TwitterAgent")

            # Step 4: Run Bayesian analysis on value bets
            value_bets = odds_result.get("value_bets", [])
            if not prediction_only:
                logger.info("Step 4: Running Bayesian analysis...")
                for bet in value_bets[:15]:
                    analysis_task = {"selection": bet, "sport": sport}

                    use_ai = await self.analysis_agent.should_use_ai(analysis_task)
                    results["ai_enhanced"] = results["ai_enhanced"] or use_ai

                    analysis_result = await self.analysis_agent.execute(analysis_task)
                    results["analysis"].append(analysis_result)
                    results["agents_used"].append("AnalysisAgent")

            # Step 5: Get expert recommendation using sequential thinking
            if not prediction_only:
                logger.info("Step 5: Getting expert recommendation...")
            if (not prediction_only) and value_bets:
                expert_task = {
                    "bet_analysis": {
                        "market": value_bets[0].get("market"),
                        "teams": teams,
                        "sport": sport,
                        "edge": value_bets[0].get("edge"),
                        "posterior_prob": value_bets[0].get("posterior_p"),
                        "odds": value_bets[0].get("odds"),
                        "sentiment": {
                            team: results["sentiment"][i]
                            for i, team in enumerate(teams)
                        },
                    }
                }
                expert_result = await self.expert_agent.execute(expert_task)
                results["expert_recommendation"] = expert_result
                results["agents_used"].append("ExpertAgent")

            # Step 6: Run DvP analysis for NBA slates
            if sport in ("basketball_nba", "nba"):
                logger.info("Step 6: Running DvP analysis...")
                try:
                    dvp_result = await self.dvp_agent.execute(
                        {
                            "type": "full_analysis",
                        }
                    )
                    results["dvp"] = dvp_result
                    results["agents_used"].append("DvPAgent")
                    logger.info(
                        f"DvP analysis complete: {dvp_result.get('count', 0)} projections, "
                        f"{dvp_result.get('high_value_count', 0)} HIGH VALUE"
                    )
                except Exception as e:
                    logger.warning(f"DvP analysis failed (non-fatal): {e}")
                    results["dvp"] = None

            # Step 7: Run NCAAB efficiency analysis
            if sport in ("basketball_ncaab", "ncaab"):
                logger.info("Step 7: Running NCAAB efficiency analysis...")
                try:
                    ncaab_dvp_result = await self.ncaab_dvp_agent.execute(
                        {
                            "type": "full_analysis",
                        }
                    )
                    results["ncaab_dvp"] = ncaab_dvp_result
                    results["agents_used"].append("NCAABDvPAgent")
                    logger.info(
                        f"NCAAB DvP analysis complete: "
                        f"{ncaab_dvp_result.get('count', 0)} projections"
                    )
                except Exception as e:
                    logger.warning(f"NCAAB DvP analysis failed (non-fatal): {e}")
                    results["ncaab_dvp"] = None

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
        predictions: Dict[str, Any],
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
        for prediction in predictions.get("analysis", []):
            was_correct = self._evaluate_prediction(prediction, actual_outcome)

            # Update agent memory
            await self.memory.store_decision(
                prediction.get("agent", "unknown"),
                prediction,
                actual_outcome,
                was_correct,
            )

            # If wrong, have agents learn from mistake
            if not was_correct:
                mistake = {
                    "type": "prediction_error",
                    "predicted": prediction,
                    "actual": actual_outcome,
                    "context": {"analysis_id": analysis_id},
                }

                # Notify relevant agent
                if "analysis" in prediction.get("agent", "").lower():
                    await self.analysis_agent.learn_from_mistake(mistake)

    def _evaluate_prediction(
        self, prediction: Dict[str, Any], outcome: Dict[str, Any]
    ) -> bool:
        """Evaluate if a prediction was correct"""
        # Simplified evaluation
        return True  # Would implement actual evaluation logic

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            "orchestrator": "active",
            "agents": {
                "odds": self.odds_agent.get_agent_status(),
                "analysis": self.analysis_agent.get_agent_status(),
                "twitter": self.twitter_agent.get_agent_status(),
                "expert": self.expert_agent.get_agent_status(),
                "dvp": self.dvp_agent.get_agent_status(),
                "ncaab_dvp": self.ncaab_dvp_agent.get_agent_status(),
            },
        }
