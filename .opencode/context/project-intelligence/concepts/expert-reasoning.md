<!-- Context: project-intelligence/concepts/expert-reasoning | Priority: high | Version: 1.0 | Updated: 2026-02-27 -->

# Expert Reasoning — Sequential Thinking MCP

**Purpose**: Multi-step expert decision-making for bet approval via MCP sequential thinking.
**Last Updated**: 2026-02-27

## Core Concept

The ExpertAgent uses a 6-step sequential thinking process to evaluate each bet opportunity. Runs as an MCP Docker container, invoked automatically after analysis completes. Provides structured reasoning with confidence scores and stake recommendations.

## 6-Step Decision Process

1. **Understand** — Parse bet type, odds, market context
2. **Gather** — Pull sharp signals (RLM, steam, CLV), model outputs
3. **Analyze** — Cross-reference signals, identify consensus/conflict
4. **Calculate EV** — True probability × decimal odds - 1
5. **Assess Risk** — Correlation, exposure, bankroll impact
6. **Recommend** — Final verdict with confidence + stake

## Decision Output

```python
{
    "should_bet": bool,
    "confidence": float,       # 0.0 - 1.0
    "rationale": str,
    "recommended_stake": float,
    "thinking_process": [      # Each step logged
        {"step": 1, "thought": "...", "conclusion": "..."}
    ]
}
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/analyze` | POST | Auto-triggers expert review |
| `/agents/expert/explain/{id}` | GET | Retrieve reasoning chain |
| `/agents/learn` | POST | Adjust thresholds from outcomes |

## Learning Loop

POST `/agents/learn` adjusts: confidence thresholds, stake calculations, reasoning weights, and pattern recognition from historical outcomes.

## Infrastructure

- Docker: `mcp/sequentialthinking:latest` on `mcp-network`
- MCP protocol for structured reasoning steps

## 📂 Codebase References

- **Agent**: `backend/app/agents/expert_agent.py`
- **Service**: `backend/app/services/sequential_thinking_service.py`
- **MCP config**: `mcp-config.json` (root)
- **Full docs**: `SEQUENTIAL_THINKING.md` (root)
