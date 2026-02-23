# MCP Servers Reference

13 servers configured in `sports-data-platform.code-workspace` under `settings.mcp.servers`.

## GitHub — Repo/Issue/PR
- **Command:** `npx @modelcontextprotocol/server-github`
- **Env:** `GITHUB_PERSONAL_ACCESS_TOKEN`
- **Use when:** Creating issues, managing PRs, querying repo data

## Playwright — Browser Automation
- **Command:** `npx @playwright/mcp@latest`
- **No secrets required**
- **Use when:** Scraping odds pages, interacting with sportsbook UIs

## Filesystem — File Operations
- **Command:** `npx @modelcontextprotocol/server-filesystem ${workspaceFolder}`
- **Use when:** Reading/writing project files programmatically

## Fetch — URL Fetching
- **Command:** `npx @modelcontextprotocol/server-fetch`
- **Use when:** Fetching odds API responses, external data sources

## Postgres — Database Queries
- **Command:** `npx @modelcontextprotocol/server-postgres ${DATABASE_URL}`
- **Env:** `DATABASE_URL`
- **Use when:** Querying game data, bet history, performance metrics from Supabase/Postgres

## Brave Search — Web Search
- **Command:** `npx @modelcontextprotocol/server-brave-search`
- **Env:** `BRAVE_API_KEY`
- **Use when:** Searching for injury reports, weather conditions, breaking news

## Memory — Knowledge Graph
- **Command:** `npx @modelcontextprotocol/server-memory`
- **Use when:** Storing persistent facts (team trends, model parameters, market regimes)

## Sequential Thinking — Structured Reasoning
- **Command:** `npx @modelcontextprotocol/server-sequential-thinking`
- **Use when:** Complex multi-step analysis, breaking down betting decisions

## Everything — Testing/Debug
- **Command:** `npx @modelcontextprotocol/server-everything`
- **Use when:** Testing MCP integrations

## Puppeteer — Browser Automation (Headless)
- **Command:** `npx @modelcontextprotocol/server-puppeteer`
- **Use when:** Headless scraping, screenshot capture of odds boards

## Google Maps
- **Command:** `npx @modelcontextprotocol/server-google-maps`
- **Env:** `GOOGLE_MAPS_API_KEY`
- **Use when:** Travel distance calculations for NCAAB (travel adjustment factor)

## Slack — Notifications
- **Command:** `npx @modelcontextprotocol/server-slack`
- **Env:** `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID`
- **Use when:** Sending alerts to team channels

## Google Sheets — Spreadsheet Integration
- **Command:** `npx @modelcontextprotocol/server-google-sheets`
- **Use when:** Reading/writing betting logs, slate data from Google Sheets

## Docker MCP (Additional)
Sequential Thinking also available via Docker: `docker-compose.mcp.yml` (container: `mcp-sequentialthinking`)
