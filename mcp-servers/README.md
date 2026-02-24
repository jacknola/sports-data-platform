# Sports Data Platform MCP Servers

Model Context Protocol (MCP) servers that expose sports betting analysis and reporting functionality as callable tools/skills.

## Available MCP Servers

### 1. **Betting Analysis** (`betting-analysis`)
Quantitative sports betting analysis tools:
- Calculate expected value (EV) of bets
- Devig two-way markets to find true probabilities
- Calculate optimal stake sizes using Fractional Kelly Criterion
- Detect sharp money signals (RLM, steam moves)
- Convert between American and decimal odds

**Skills:** `/Users/bb.jr/.claude/skills/betting-analysis-mcp/`

### 2. **Google Sheets Reporting** (`sheets-reporting`)
Export betting data and track performance in Google Sheets:
- Export daily betting slates
- Log bet results and outcomes
- Generate performance reports
- Create new betting tracker spreadsheets
- Update bankroll snapshots

**Skills:** `/Users/bb.jr/.claude/skills/sheets-reporting-mcp/`

## Quick Start

### 1. Build and Start MCP Servers

```bash
# Build all MCP servers
docker-compose -f docker-compose.mcp.yml build

# Start all MCP servers
docker-compose -f docker-compose.mcp.yml up -d

# Start specific server
docker-compose -f docker-compose.mcp.yml up -d betting-analysis

# View logs
docker-compose -f docker-compose.mcp.yml logs -f betting-analysis
```

### 2. Configuration

#### Global Configuration (All Projects)
MCP servers are configured in Warp's settings. The servers run in Docker containers and communicate via stdio.

1. **Warp MCP Configuration** (`~/.warp/mcp-settings.json`):
```json
{
  "mcpServers": {
    "sports-betting-analysis": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "mcp-betting-analysis",
        "python",
        "server.py"
      ]
    },
    "sports-sheets-reporting": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "mcp-sheets-reporting",
        "python",
        "server.py"
      ]
    }
  }
}
```

2. **Or use `npx` for local development:**
```json
{
  "mcpServers": {
    "sports-betting-analysis": {
      "command": "python3",
      "args": [
        "/Users/bb.jr/sports-data-platform/mcp-servers/betting-analysis/server.py"
      ]
    }
  }
}
```

#### Project-Specific Configuration
Configuration is already set in `docker-compose.mcp.yml` for this project.

### 3. Google Sheets Credentials Setup

For the `sheets-reporting` server:

1. **Verify credentials exist:**
```bash
ls -la backend/credentials/google-sa.json
```

2. **Get service account email:**
```bash
cat backend/credentials/google-sa.json | grep client_email
```

3. **Share spreadsheets** with the service account email
   - Or use the `create_betting_tracker` tool to create new spreadsheets

4. **Required APIs:**
   - Google Sheets API
   - Google Drive API

## Usage Examples

### Using Betting Analysis Server

**Via Warp Skills:**
```
User: "I found Celtics -5.5 at +105 on FanDuel. Pinnacle has -110/-110. Should I bet?"

Warp will:
1. Devig Pinnacle odds to find true probability
2. Calculate EV at +105
3. Recommend stake size using Quarter Kelly
```

**Direct MCP Tool Call:**
```python
# Devig two-way market
result = call_mcp_tool("sports-betting-analysis", "devig_two_way_market", {
    "side_a_odds": 1.91,  # -110 in decimal
    "side_b_odds": 1.91   # -110 in decimal
})
# Returns: {"side_a_true_probability": 0.5, "side_b_true_probability": 0.5}

# Calculate Kelly stake
result = call_mcp_tool("sports-betting-analysis", "calculate_kelly_stake", {
    "bankroll": 10000,
    "true_probability": 0.52,
    "decimal_odds": 2.05,  # +105
    "kelly_fraction": 0.25
})
# Returns: {"stake_amount": 250, "stake_pct": 2.5, "ev_percent": 6.6, "recommendation": "BET"}
```

### Using Sheets Reporting Server

**Via Warp Skills:**
```
User: "Export today's slate to my betting tracker"

Warp will:
1. Format betting recommendations
2. Export to Google Sheets with proper formatting
3. Return spreadsheet URL
```

**Direct MCP Tool Call:**
```python
# Export betting slate
result = call_mcp_tool("sports-sheets-reporting", "export_betting_slate", {
    "spreadsheet_id": "1abc...xyz",
    "bets": [
        {
            "game": "Lakers @ Celtics",
            "sport": "NBA",
            "market": "Spread",
            "pick": "Lakers +5.5",
            "odds": "+105",
            "stake": "$250",
            "ev_percent": "6.6%",
            "kelly_percent": "2.5%",
            "confidence": "High",
            "sharp_signals": "RLM",
            "notes": "Strong reverse line movement"
        }
    ]
})
```

## Integration with Backend

MCP servers complement the backend services:

### Backend Services (Full Pipeline)
Located in `backend/app/services/`:
- `bayesian.py` - Posterior probability, Monte Carlo simulation
- `sharp_money_detector.py` - RLM, steam, CLV analysis
- `multivariate_kelly.py` - Correlated portfolio optimization
- `nba_ml_predictor.py` - XGBoost predictions
- `bet_tracker.py` - Wager lifecycle management

### MCP Servers (Standalone Tools)
Located in `mcp-servers/`:
- Provide quick calculations and analysis
- Can be called independently without full backend
- Useful for ad-hoc analysis and reporting
- Integrate with Warp as skills

**When to use MCP vs Backend:**
- **MCP:** Quick calculations, single-bet analysis, reporting/export
- **Backend:** Full pipeline, portfolio optimization, ML predictions, production betting

## Development

### Adding New Tools to Existing Server

Edit `mcp-servers/{server-name}/server.py`:

1. **Add tool to `list_tools()`:**
```python
Tool(
    name="my_new_tool",
    description="What this tool does",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {"type": "number", "description": "Description"}
        },
        "required": ["param1"]
    }
)
```

2. **Add handler to `call_tool()`:**
```python
elif name == "my_new_tool":
    result = my_function(arguments["param1"])
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
```

3. **Rebuild container:**
```bash
docker-compose -f docker-compose.mcp.yml up -d --build betting-analysis
```

### Creating New MCP Server

1. **Create directory:** `mcp-servers/my-server/`
2. **Create `server.py`** with MCP SDK structure
3. **Create `requirements.txt`** and `Dockerfile`
4. **Add to `docker-compose.mcp.yml`**
5. **Create Warp skill** in `~/.claude/skills/my-server-mcp/`

## Troubleshooting

### Server Not Starting
```bash
# Check logs
docker-compose -f docker-compose.mcp.yml logs betting-analysis

# Rebuild
docker-compose -f docker-compose.mcp.yml up -d --build
```

### Google Sheets Authentication Error
```bash
# Verify credentials file
cat backend/credentials/google-sa.json | jq .client_email

# Check volume mount
docker exec mcp-sheets-reporting ls -la /app/credentials/
```

### MCP SDK Not Found
```bash
# Install dependencies
cd mcp-servers/betting-analysis
pip install -r requirements.txt
```

## Architecture

```
┌─────────────────────────────────────────┐
│ Warp AI Agent                            │
│ - Uses skills to trigger MCP servers    │
└──────────────┬──────────────────────────┘
               │
               ├──────────┬─────────────┬──────────────┐
               │          │             │              │
               ▼          ▼             ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│   Betting    │ │  Sheets  │ │NotebookLM│ │ Sequential   │
│   Analysis   │ │ Reporting│ │ Research │ │  Thinking    │
│ MCP Server   │ │   MCP    │ │   MCP    │ │ MCP Server   │
│              │ │          │ │          │ │              │
│ • EV Calc    │ │ • Export │ │ • Deep   │ │ • Reasoning  │
│ • Devigging  │ │ • Track  │ │ Research │ │ • Planning   │
│ • Kelly Size │ │ • Report │ │ • Market │ │              │
│ • Sharp $$$  │ │          │ │ Analysis │ │              │
└──────────────┘ └────┬─────┘ └────┬─────┘ └──────────────┘
                      │            │
                      ▼            ▼
              ┌──────────┐  ┌─────────────┐
              │  Google  │  │   Google    │
              │  Sheets  │  │ Knowledge   │
              │ (via API)│  │    Base     │
              └──────────┘  └─────────────┘
```

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [MCP SDK (Python)](https://github.com/modelcontextprotocol/python-sdk)
- [Warp MCP Integration](https://docs.warp.dev/features/ai/mcp)
- [Google Sheets API](https://developers.google.com/sheets/api)

## License

Part of the sports-data-platform project. See main repository LICENSE.
