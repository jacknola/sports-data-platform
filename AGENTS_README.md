# Multi-Agent System Architecture

This sports data platform uses a multi-agent system where different AI agents handle specialized tasks, learn from mistakes, and use AI strategically.

## Agent Architecture

```
┌─────────────────────────────────┐
│   Orchestrator Agent            │
│   - Coordinates workflows       │
│   - Routes tasks                │
│   - Manages learning            │
└────────────┬────────────────────┘
             │
     ┌───────┼───────┐
     │       │       │
┌────▼──┐ ┌──▼──┐ ┌──▼────┐
│Odds  │ │Anls │ │Twit │
│Agent │ │Agent│ │Agent│
└──────┘ └─────┘ └─────┘
     │       │       │
     └───────┼───────┘
             │
     ┌───────▼───────┐
     │  Memory Sys   │
     │  - Mistakes   │
     │  - Learning   │
     └───────────────┘
```

## Agents

### 1. OddsAgent
**Purpose**: Fetch and analyze betting odds  
**Responsibilities**:
- Fetch odds from multiple sportsbooks
- Identify value bets (positive expected value)
- Track edge calculations

**Uses AI When**:
- High-value bets (>$1000)
- Complex markets (props, parlays)
- Previous mistakes on similar tasks

**Learns From**:
- API failures → increases retries
- Data quality issues → better validation

### 2. AnalysisAgent
**Purpose**: Run Bayesian and ML analysis  
**Responsibilities**:
- Compute posterior probabilities
- Run Monte Carlo simulations
- Apply ML predictions
- Use AI for enhanced analysis

**Uses AI When**:
- Similar past mistakes exist
- Complex probability calculations
- High confidence required

**Learns From**:
- Probability estimation errors → adjust priors
- Feature weighting issues → re-evaluate weights

### 3. TwitterAgent
**Purpose**: Monitor Twitter sentiment  
**Responsibilities**:
- Collect tweets about teams/players
- Analyze sentiment
- Track engagement metrics

**Uses AI When**:
- Important events
- Controversial topics
- Previous sentiment errors

**Learns From**:
- Low confidence → adjust thresholds
- Rate limiting → better backoff strategies

### 4. OrchestratorAgent
**Purpose**: Coordinate all agents  
**Responsibilities**:
- Route tasks to appropriate agents
- Manage workflows
- Learn from outcomes
- Report agent status

## How Learning Works

### 1. Decision Storage
Every agent decision is stored with:
- What was decided
- What actually happened
- Whether it was correct

### 2. Mistake Recording
Mistakes are logged with:
- Task type
- Context
- Outcome
- Frequency

### 3. Pattern Learning
Agents identify patterns:
- Common errors
- Successful strategies
- Confidence calibration

### 4. Adaptive Behavior
Agents adjust their behavior:
- Threshold updates
- Retry strategies
- Feature re-weighting

## Usage

### Run Full Agent Analysis
```python
POST /api/v1/agents/analyze
{
  "sport": "nfl",
  "teams": ["Bills", "Chiefs"],
  "date": "2024-01-15"
}
```

### Submit Learning Data
```python
POST /api/v1/agents/learn
{
  "analysis_id": "abc123",
  "actual_outcome": {...},
  "predictions": {...}
}
```

### Get Agent Status
```python
GET /api/v1/agents/status
```

## Example Workflow

1. **OddsAgent** fetches current odds
2. **TwitterAgent** analyzes sentiment for each team
3. **AnalysisAgent** runs Bayesian analysis on value bets
4. **OrchestratorAgent** combines results
5. User submits outcome data
6. All agents learn from results
7. Future predictions improve

## AI Usage Strategy

Agents use AI strategically, not always:
- ✅ Use AI: High-value decisions, complex tasks, past mistakes
- ❌ Skip AI: Simple tasks, high confidence, proven patterns

This reduces costs and improves efficiency.

