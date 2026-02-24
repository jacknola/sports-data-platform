# MCP Servers Quick Setup

## Prerequisites
- Docker Desktop installed and running
- Python 3.11+ (for local development)
- Google Service Account credentials at `backend/credentials/google-sa.json`

## 1. Start Docker Desktop
Ensure Docker Desktop is running before proceeding.

## 2. Build and Start MCP Servers

```bash
cd /Users/bb.jr/sports-data-platform

# Build all MCP servers
docker compose -f docker-compose.mcp.yml build

# Start all MCP servers in background
docker compose -f docker-compose.mcp.yml up -d

# Check status
docker compose -f docker-compose.mcp.yml ps

# View logs
docker compose -f docker-compose.mcp.yml logs -f
```

## 3. Install MCP Dependencies Locally (Optional)

For local development without Docker:

```bash
# Betting Analysis
cd mcp-servers/betting-analysis
pip install -r requirements.txt

# Sheets Reporting
cd ../sheets-reporting
pip install -r requirements.txt
```

## 4. Configure Warp to Use MCP Servers

### Option A: Using Docker Containers (Recommended)

Create or edit `~/.warp/mcp-settings.json`:

```json
{
  "mcpServers": {
    "sports-betting-analysis": {
      "command": "docker",
      "args": ["exec", "-i", "mcp-betting-analysis", "python", "server.py"]
    },
    "sports-sheets-reporting": {
      "command": "docker",
      "args": ["exec", "-i", "mcp-sheets-reporting", "python", "server.py"]
    }
  }
}
```

### Option B: Direct Python (Local Development)

```json
{
  "mcpServers": {
    "sports-betting-analysis": {
      "command": "python3",
      "args": ["/Users/bb.jr/sports-data-platform/mcp-servers/betting-analysis/server.py"]
    },
    "sports-sheets-reporting": {
      "command": "python3",
      "args": ["/Users/bb.jr/sports-data-platform/mcp-servers/sheets-reporting/server.py"],
      "env": {
        "GOOGLE_CREDENTIALS_PATH": "/Users/bb.jr/sports-data-platform/backend/credentials/google-sa.json"
      }
    }
  }
}
```

## 5. Verify Skills Are Available

Warp skills are located at:
- `~/.claude/skills/betting-analysis-mcp/SKILL.md`
- `~/.claude/skills/sheets-reporting-mcp/SKILL.md`

These skills will automatically trigger the MCP servers when you use relevant keywords.

## 6. Test the Servers

### Test Betting Analysis

In Warp, try:
```
"Calculate EV for Celtics -5.5 at +105 if true probability is 52%"
```

Or use the MCP tool directly:
```python
# In Python or Warp
call_mcp_tool("sports-betting-analysis", "calculate_ev", {
    "true_probability": 0.52,
    "decimal_odds": 2.05
})
```

### Test Sheets Reporting

In Warp, try:
```
"Create a new betting tracker spreadsheet called 'Test Tracker'"
```

Or use the MCP tool directly:
```python
call_mcp_tool("sports-sheets-reporting", "create_betting_tracker", {
    "spreadsheet_name": "Test Betting Tracker",
    "share_with_emails": ["your-email@example.com"]
})
```

## 7. Google Sheets Setup

For the sheets-reporting server to work:

1. **Verify credentials:**
```bash
cat backend/credentials/google-sa.json | jq .client_email
```

2. **Share your spreadsheets** with the service account email

3. **Or create new spreadsheets** using the `create_betting_tracker` tool

## Troubleshooting

### Docker not running
```bash
# Start Docker Desktop app first, then:
docker compose -f docker-compose.mcp.yml up -d
```

### MCP server not responding
```bash
# Restart the specific server
docker compose -f docker-compose.mcp.yml restart betting-analysis

# View logs
docker compose -f docker-compose.mcp.yml logs betting-analysis
```

### Python dependencies missing (local mode)
```bash
cd mcp-servers/betting-analysis
pip install -r requirements.txt
```

### Google Sheets authentication error
```bash
# Check if credentials file exists
ls -la backend/credentials/google-sa.json

# Verify service account email
cat backend/credentials/google-sa.json | jq .client_email

# Make sure you've shared spreadsheets with this email
```

## Usage Examples

### Calculate Kelly Sizing
```
User: "I have a $10,000 bankroll. Lakers +5.5 is at +105, true probability is 52%. How much should I bet?"

Warp uses betting-analysis MCP to:
1. Calculate EV: (0.52 × 2.05) - 1 = 6.6%
2. Calculate Quarter Kelly stake: ~$250
3. Return recommendation
```

### Export Daily Slate
```
User: "Export today's NBA picks to my betting tracker"

Warp uses sheets-reporting MCP to:
1. Format betting recommendations
2. Export to Google Sheets with headers and formatting
3. Return spreadsheet URL
```

### Detect Sharp Money
```
User: "Lakers getting 75% of public bets but line moved from -3 to -2.5. Is this RLM?"

Warp uses betting-analysis MCP to:
1. Analyze reverse line movement
2. Calculate signal strength
3. Return recommendation (FADE PUBLIC)
```

### Research Betting Strategies (NEW with NotebookLM)
```
User: "Research how closing line value indicates long-term betting success"

Warp uses NotebookLM MCP to:
1. Provide comprehensive research on CLV
2. Explain statistical significance
3. Share academic studies and sharp bettor data
4. Give practical examples and benchmarks
```

## Next Steps

- Read full documentation in `mcp-servers/README.md`
- Check Warp skills in `~/.claude/skills/`
- Integrate with backend services for full pipeline
- Add custom tools to MCP servers as needed

## Architecture

```
Warp AI → Skills → MCP Servers → Tools
                       ↓
                  Google Sheets (for reporting)
```

The MCP servers run independently and can be called by:
- Warp AI agent (via skills)
- Backend services (via API)
- Direct tool calls (via MCP SDK)
- Command line (stdio interface)
