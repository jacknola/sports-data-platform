<!-- Context: project-intelligence/navigation | Priority: high | Version: 1.1 | Updated: 2026-02-27 -->

# Project Intelligence

**Purpose**: Quick navigation to all project context files.

## Quick Routes

| File | Description | Priority |
|------|-------------|----------|
| [technical-domain.md](technical-domain.md) | Tech stack, AI model config, code patterns, naming, standards, security | critical |
| [concepts/expert-reasoning.md](concepts/expert-reasoning.md) | Sequential thinking MCP, 6-step decision process | high |
| [concepts/nba-ml-predictions.md](concepts/nba-ml-predictions.md) | XGBoost pipeline, training, EV/Kelly formulas | high |
| [guides/web-scraping.md](guides/web-scraping.md) | Crawl4AI architecture, extraction schemas | medium |
| [guides/deployment.md](guides/deployment.md) | Docker, systemd, monitoring, troubleshooting | medium |
| [guides/google-sheets.md](guides/google-sheets.md) | Sheets API, sheet schemas, service account setup | medium |

## Deep Dives

| Topic | File | Key Sections |
|-------|------|-------------|
| AI Agent Models | technical-domain.md § AI Agent Model Configuration | Provider restrictions, per-agent model mapping, cost tiers |
| Code Patterns | technical-domain.md § Code Patterns | FastAPI endpoints, React components |
| Expert Decisions | concepts/expert-reasoning.md | 6-step process, decision output, learning loop |
| NBA ML | concepts/nba-ml-predictions.md | XGBoost features, EV formula, training commands |
| Web Scraping | guides/web-scraping.md | Crawl4AI schemas, performance, error handling |
| Deployment | guides/deployment.md | Docker Compose, agents, scheduling, troubleshooting |
| Google Sheets | guides/google-sheets.md | API endpoints, sheet structures, setup |
| Naming | technical-domain.md § Naming Conventions | Python/TS/DB conventions |
| Standards | technical-domain.md § Code Standards | Type safety, logging, HTTP, degradation |

## Config Locations
- **Agent models**: `.opencode/opencode.json` → `agent.{name}.model`
- **Providers**: `.opencode/opencode.json` → `enabled_providers: ["gemini", "opencode"]`
- **Project metadata**: `.opencode/.opencode.yaml`
- **Agent definitions**: `.opencode/agent/core/` and `.opencode/agent/subagents/`
