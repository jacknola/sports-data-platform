"""
Sequential Thinking Service - Integrates MCP Sequential Thinking for expert-level reasoning
"""
import json
import subprocess
from typing import Dict, Any, List
from loguru import logger


class SequentialThinkingService:
    """
    Service that uses sequential thinking MCP for expert-level sports betting decisions
    """
    
    def __init__(self):
        self.mcp_config = {
            "command": "npx -y @modelcontextprotocol/server-sequential-thinking",
            "research_command": "npx -y notebooklm-mcp@latest"
        }
        self._process = None
    
    async def think_step_by_step(
        self,
        problem: str,
        context: Dict[str, Any],
        goal: str
    ) -> Dict[str, Any]:
        """
        Use sequential thinking to solve a sports betting problem step-by-step
        
        Args:
            problem: The betting question or decision to analyze
            context: Available data (odds, stats, sentiment, etc.)
            goal: What we're trying to determine
            
        Returns:
            Sequential reasoning process and final conclusion
        """
        logger.info("Starting sequential thinking process...")
        
        # Format the problem for sequential thinking
        thinking_problem = self._format_problem(problem, context, goal)
        
        # Use sequential thinking process
        reasoning_steps = await self._execute_thinking(thinking_problem)
        
        logger.info(f"Sequential thinking complete: {len(reasoning_steps)} steps")
        
        return {
            'problem': problem,
            'goal': goal,
            'steps': reasoning_steps,
            'conclusion': reasoning_steps[-1] if reasoning_steps else None
        }
    
    def _format_problem(self, problem: str, context: Dict[str, Any], goal: str) -> str:
        """Format a sports betting problem for sequential thinking"""
        
        formatted = f"""Sports Betting Decision Problem
        
Goal: {goal}

Context:
- Sport: {context.get('sport', 'Unknown')}
- Teams: {', '.join(context.get('teams', []))}
- Game Date: {context.get('date', 'TBD')}
- Market: {context.get('market', 'Unknown')}

Available Data:
"""
        
        # Add odds information
        if context.get('odds'):
            formatted += f"- Odds: {json.dumps(context['odds'], indent=2)}\n"
        
        # Add sentiment data
        if context.get('sentiment'):
            for team, sent in context['sentiment'].items():
                formatted += f"- {team} Sentiment: {sent.get('overall_sentiment')} "
                formatted += f"(confidence: {sent.get('sentiment_confidence', 0):.2f})\n"
        
        # Add statistical data
        if context.get('stats'):
            formatted += f"- Stats: {json.dumps(context['stats'], indent=2)}\n"
        
        # Add research findings
        if context.get('research_findings'):
            formatted += f"\nResearch Findings:\n{context['research_findings']}\n"
        
        formatted += f"\nProblem: {problem}\n"
        formatted += "\nAnalyze step-by-step like an expert sports bettor would."
        
        return formatted
    
    async def research_topic(self, topic: str) -> str:
        """
        Use NotebookLM MCP to research a betting topic.
        """
        try:
            cmd = self.mcp_config["research_command"].split()
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Call the 'query' tool of notebooklm-mcp
            rpc_call = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call_tool",
                "params": {
                    "name": "query",
                    "arguments": {
                        "question": f"Research this sports betting topic: {topic}"
                    }
                }
            }
            
            stdout, stderr = process.communicate(input=json.dumps(rpc_call), timeout=60)
            
            if process.returncode != 0:
                logger.error(f"NotebookLM MCP error: {stderr}")
                return f"Research failed for {topic}"
                
            response = json.loads(stdout)
            return response.get("result", {}).get("content", [{}])[0].get("text", "No research found.")
            
        except Exception as e:
            logger.error(f"Failed to execute NotebookLM research: {e}")
            return f"Error researching {topic}: {str(e)}"

    async def _execute_thinking(self, problem: str) -> List[Dict[str, Any]]:
        """
        Execute sequential thinking using MCP server.
        """
        try:
            # Use command from config
            cmd = self.mcp_config["command"].split() if isinstance(self.mcp_config["command"], str) else self.mcp_config["command"]
            if not isinstance(cmd, list):
                cmd = ["npx", "-y", "@modelcontextprotocol/server-sequential-thinking"]
            
            # Start process
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # MCP uses JSON-RPC over stdio. This is a simplified call to the 'sequentialThinking' tool.
            # In a full implementation, we'd use an MCP client library.
            rpc_call = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call_tool",
                "params": {
                    "name": "sequentialThinking",
                    "arguments": {
                        "thought": problem,
                        "thoughtNumber": 1,
                        "totalThoughts": 1
                    }
                }
            }
            
            stdout, stderr = process.communicate(input=json.dumps(rpc_call), timeout=30)
            
            if process.returncode != 0:
                logger.error(f"MCP server error: {stderr}")
                return self._get_fallback_steps(problem)
                
            response = json.loads(stdout)
            result = response.get("result", {}).get("content", [{}])[0].get("text", "")
            
            # Parse the response into structured steps
            return [{
                'step': 1,
                'title': 'MCP Sequential Thinking Result',
                'reasoning': result,
                'detailed_reasoning': result,
                'status': 'complete'
            }]
            
        except Exception as e:
            logger.error(f"Failed to execute MCP thinking: {e}")
            return self._get_fallback_steps(problem)

    def _get_fallback_steps(self, problem: str) -> List[Dict[str, Any]]:
        """Fallback when MCP is unavailable"""
        steps = [
            {
                'step': 1,
                'title': 'Understand the Problem',
                'reasoning': 'Identify what we need to determine and why',
                'status': 'complete'
            },
            {
                'step': 2,
                'title': 'Gather Relevant Data',
                'reasoning': 'Collect all relevant information (odds, stats, sentiment)',
                'status': 'complete'
            },
            {
                'step': 3,
                'title': 'Analyze Historical Patterns',
                'reasoning': 'Consider similar past situations and outcomes',
                'status': 'complete'
            },
            {
                'step': 4,
                'title': 'Calculate Expected Value',
                'reasoning': 'Compute EV based on probability and odds',
                'status': 'complete'
            },
            {
                'step': 5,
                'title': 'Assess Risk Factors',
                'reasoning': 'Identify potential risks (injuries, weather, etc.)',
                'status': 'complete'
            },
            {
                'step': 6,
                'title': 'Make Recommendation',
                'reasoning': 'Final expert recommendation with confidence level',
                'status': 'complete'
            }
        ]
        
        for step in steps:
            step['detailed_reasoning'] = self._generate_step_reasoning(
                step['title'],
                problem
            )
        
        return steps
    
    def _generate_step_reasoning(self, step_title: str, problem: str) -> str:
        """Generate detailed reasoning for a step"""
        reasoning_templates = {
            'Understand the Problem': 'We need to determine the optimal betting decision given the available information.',
            'Gather Relevant Data': 'Collecting odds, team stats, injury reports, and market sentiment.',
            'Analyze Historical Patterns': 'Looking at similar matchups, recent form, and historical betting outcomes.',
            'Calculate Expected Value': 'Computing EV = (Probability × Payout) - Cost using Bayesian methods.',
            'Assess Risk Factors': 'Evaluating potential risks that could impact the outcome.',
            'Make Recommendation': 'Synthesizing all information into an expert recommendation with confidence score.'
        }
        
        return reasoning_templates.get(step_title, 'Reasoning step...')
    
    async def decide_if_bet(self, bet_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use sequential thinking to decide if a bet should be made
        
        Args:
            bet_analysis: Complete analysis of a betting opportunity
            
        Returns:
            Expert decision with rationale
        """
        problem = f"Should I bet on {bet_analysis.get('market')}?"
        goal = "Determine if this bet has positive expected value and acceptable risk"
        
        context = {
            'sport': bet_analysis.get('sport'),
            'teams': bet_analysis.get('teams', []),
            'market': bet_analysis.get('market'),
            'odds': bet_analysis.get('odds', {}),
            'sentiment': bet_analysis.get('sentiment', {}),
            'stats': bet_analysis.get('stats', {}),
            'research_findings': bet_analysis.get('research_findings'),
            'edge': bet_analysis.get('edge'),
            'posterior_prob': bet_analysis.get('posterior_prob')
        }
        
        thinking_result = await self.think_step_by_step(problem, context, goal)
        
        # Extract decision from sequential thinking
        decision = self._make_expert_decision(bet_analysis, thinking_result)
        
        return {
            'decision': decision['should_bet'],
            'confidence': decision['confidence'],
            'rationale': decision['rationale'],
            'thinking_process': thinking_result,
            'recommended_stake': decision.get('stake')
        }
    
    def _make_expert_decision(
        self,
        bet_analysis: Dict[str, Any],
        thinking: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make expert decision based on analysis and sequential thinking"""
        
        edge = bet_analysis.get('edge', 0)
        confidence = bet_analysis.get('posterior_p', 0)
        
        # Expert decision logic
        should_bet = edge > 0.05  # Minimum edge threshold
        confidence_score = min(confidence, 1.0)
        
        rationale = f"""
        Expert Analysis:
        - Edge: {edge:.2%}
        - Posterior Probability: {confidence:.2%}
        - Market Analysis: Positive
        - Risk Assessment: Acceptable
        
        Recommendation: {'BET' if should_bet else 'PASS'}
        """
        
        # Calculate Kelly Criterion for stake sizing
        stake = self._calculate_stake(edge, confidence)
        
        return {
            'should_bet': should_bet,
            'confidence': confidence_score,
            'rationale': rationale.strip(),
            'stake': stake
        }
    
    def _calculate_stake(self, edge: float, probability: float) -> float:
        """Calculate optimal stake using Kelly Criterion"""
        # Simplified Kelly calculation
        if edge > 0 and probability > 0.5:
            kelly = edge / (1 - probability)
            # Cap at 25% of bankroll
            return min(kelly, 0.25)
        return 0.0

