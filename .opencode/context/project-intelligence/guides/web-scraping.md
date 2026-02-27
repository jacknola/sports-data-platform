<!-- Context: project-intelligence/guides/web-scraping | Priority: medium | Version: 1.0 | Updated: 2026-02-27 -->

# Web Scraping — Crawl4AI Integration

**Purpose**: AI-enhanced web scraping for sports data extraction.
**Last Updated**: 2026-02-27

## Core Concept

Crawl4AI provides AI-powered extraction with LLM-based schema enforcement. The ScrapingAgent orchestrates crawls as part of the multi-agent analysis pipeline, extracting structured sports data (scores, odds, injuries) from ESPN, NBA, CBS, and The Athletic.

## Architecture

```
ScrapingAgent → WebScrapingService → Crawl4AI → Structured Data
                                         ↓
                              LLM Schema Enforcement
```

## Key Extraction Schemas

| Schema | Fields | Use Case |
|--------|--------|----------|
| Scoreboard | team_name, score, quarter, time_remaining | Live game data |
| Odds | team, spread, total, moneyline, book | Line shopping |
| News | headline, summary, teams_mentioned, injury_status | Sentiment/injury |

## Performance

- AI extraction: 2-5s per page
- Basic fallback: 0.5-1s per page
- Batch: 10+ concurrent crawls
- Redis cache for dedup

## Config

```bash
OPENAI_API_KEY=       # LLM extraction
HUGGINGFACE_API_KEY=  # Fallback models
CRAWL4AI_MODE=ai      # ai | basic
CRAWL4AI_TIMEOUT=30
```

## Error Handling

Anti-scraping bypass built in. Falls back to basic (non-AI) extraction on LLM failure. Schema validation retries with refined prompts.

## 📂 Codebase References

- **Agent**: `backend/app/agents/scraping_agent.py`
- **Service**: `backend/app/services/web_scraping_service.py`
- **Pipeline**: ScrapingAgent → AnalysisAgent → ExpertAgent (5-agent flow)
- **Full docs**: `WEB_SCRAPING.md` (root)
