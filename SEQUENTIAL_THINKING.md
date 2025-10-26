# Sequential Thinking Integration

## Overview

The platform now includes **Sequential Thinking via MCP** for expert-level sports betting decisions. This enables the system to reason step-by-step like a professional sports bettor would.

## What is Sequential Thinking?

Sequential thinking breaks down complex decisions into structured steps:
1. **Understand the Problem** - What are we trying to determine?
2. **Gather Relevant Data** - Collect odds, stats, sentiment
3. **Analyze Historical Patterns** - Look at similar situations
4. **Calculate Expected Value** - Compute EV using probability
5. **Assess Risk Factors** - Identify potential risks
6. **Make Recommendation** - Synthesize into expert decision

## Architecture

```
Expert Agent
    ↓
Sequential Thinking Service
    ↓
MCP Sequential Thinking Container
    ↓
Docker: mcp/sequentialthinking
```

## Components

### 1. Expert Agent (`expert_agent.py`)
Specialized agent that uses sequential thinking for all decisions.

### 2. Sequential Thinking Service (`sequential_thinking.py`)
- Formats problems for step-by-step analysis
- Executes thinking processes
- Returns expert recommendations

### 3. MCP Integration (`docker-compose.yml`)
```yaml
sequentialthinking:
  image: mcp/sequentialthinking:latest
  container_name: mcp-sequentialthinking
  networks:
    - mcp-network
    - default
```

## Usage

### Through API
```bash
POST /api/v1/agents/analyze
{
  "sport": "nfl",
  "teams": ["Bills", "Chiefs"],
  "date": "2024-01-15"
}
```

The orchestrator will automatically:
1. Fetch odds
2. Analyze sentiment
3. Run Bayesian analysis
4. **Use expert agent with sequential thinking** ← NEW!
5. Return expert recommendation

### Get Expert Explanation
```bash
GET /api/v1/agents/expert/explain/{decision_id}
```

Returns detailed step-by-step reasoning.

## Expert Decision Process

```
Problem: "Should I bet on Bills -3.5?"
    ↓
Step 1: Understand - Analyzing spread bet
Step 2: Gather - Collect odds, stats, sentiment
Step 3: Analyze - Historical patterns, recent form
Step 4: Calculate - EV = (prob × payout) - cost
Step 5: Assess Risk - Injuries, weather, motivation
Step 6: Recommend - Final decision with confidence
    ↓
Expert Recommendation: BET
Confidence: 75%
Stake: 5% of bankroll (Kelly Criterion)
Rationale: "Positive edge identified..."
```

## How It Works

1. **Problem Formatting**
   - Structures betting question
   - Includes all relevant context
   - Sets clear goal

2. **Sequential Reasoning**
   - 6-step structured process
   - Each step builds on previous
   - Records reasoning at each step

3. **Expert Decision**
   - Considers all factors
   - Calculates edge
   - Assesses risk
   - Makes recommendation

4. **Stake Sizing**
   - Uses Kelly Criterion
   - Accounts for confidence level
   - Caps at 25% of bankroll

## Learning from Outcomes

The expert agent learns from every decision:

```python
# When outcome is known:
POST /api/v1/agents/learn
{
  "analysis_id": "abc123",
  "actual_outcome": {"winning_team": "Bills"},
  "predictions": {"predicted_team": "Chiefs"}
}
```

This helps the agent:
- Adjust decision thresholds
- Refine stake calculations
- Improve reasoning patterns
- Calibrate confidence levels

## Example Output

```json
{
  "decision": {
    "should_bet": true,
    "confidence": 0.75,
    "rationale": "Expert Analysis: Edge: 8.5%, Posterior: 75%, Market: Positive",
    "recommended_stake": 0.05
  },
  "thinking_process": {
    "steps": [
      {"step": 1, "title": "Understand Problem", "reasoning": "..."},
      {"step": 2, "title": "Gather Data", "reasoning": "..."},
      ...
    ]
  }
}
```

## Benefits

✅ **Expert-Level Decisions** - Professional betting methodology  
✅ **Transparent Reasoning** - See why the decision was made  
✅ **Risk Management** - Proper stake sizing  
✅ **Continuous Learning** - Improves from mistakes  
✅ **Structured Approach** - No random decisions  

## Configuration

The sequential thinking MCP server is automatically started with:
```bash
docker-compose up -d
```

It's available to all agents but primarily used by the ExpertAgent.

## Next Steps

To enhance sequential thinking:
1. Add more reasoning steps for complex markets
2. Integrate with actual MCP sequentialthinking API
3. Add reasoning templates for different bet types
4. Implement feedback loops for continuous improvement

