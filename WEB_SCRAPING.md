# AI-Powered Web Scraping Infrastructure

## Overview

The platform includes advanced AI-powered web scraping using [Crawl4AI](https://github.com/unclecode/crawl4ai) for intelligent content extraction from sports websites.

## Capabilities

### 1. AI-Enhanced Extraction
- **Crawl4AI Integration**: Uses LLM-based extraction for structured data
- **Schema-Based Extraction**: Automatically extracts data based on schemas
- **Markdown Conversion**: Converts HTML to clean markdown for analysis
- **Anti-Scraping Bypass**: Handles dynamic JavaScript content

### 2. Sports-Specific Features
- Extract team names, scores, dates from text
- Parse betting odds and lines
- Identify injury reports
- Scrape game statistics
- Collect news articles

### 3. Scraping Agent
The `ScrapingAgent` is integrated into the multi-agent system:
- Scrapes news and stats for teams
- Used in full analysis workflows
- Learns from scraping mistakes
- Handles anti-scraping measures

## Architecture

```
ScrapingAgent
    ↓
WebScrapingService
    ↓
Crawl4AI (AI-Enhanced)
    ↓
Structured Data Extraction
```

## Usage

### Through Agent System
The ScrapingAgent is automatically used in full analysis:

```bash
POST /api/v1/agents/analyze
{
  "sport": "nfl",
  "teams": ["Bills", "Chiefs"]
}
```

### Direct Scraping
Scrape any sports page:

```python
from app.services.web_scraper import WebScrapingService

scraper = WebScrapingService()

# AI-enhanced scraping with schema
schema = scraper.create_extraction_schema('scoreboard')
result = await scraper.scrape_sports_page(
    url="https://www.espn.com/nfl/game",
    extraction_schema=schema,
    use_ai=True
)
```

## Extraction Schemas

### Scoreboard Schema
Extracts game information:
```python
{
    'games': [
        {
            'home_team': 'string',
            'away_team': 'string',
            'home_score': 'number',
            'away_score': 'number',
            'status': 'string',
            'date': 'string'
        }
    ]
}
```

### Odds Schema
Extracts betting markets:
```python
{
    'markets': [
        {
            'game': 'string',
            'market_type': 'string',
            'selection': 'string',
            'odds': 'number'
        }
    ]
}
```

### News Schema
Extracts articles:
```python
{
    'articles': [
        {
            'title': 'string',
            'content': 'string',
            'date': 'string',
            'author': 'string'
        }
    ]
}
```

## Data Extraction

The service automatically extracts:

### 1. Teams
Patterns like "Bills vs Chiefs" or "Lakers at Warriors"

### 2. Scores
Formats like "28-24" or "Lakers 102-98 Warriors"

### 3. Dates
"January 15, 2024" format

### 4. Odds
American odds like +150, -110

### 5. Injuries
Keywords: injury, out, questionable, doubtful

## Scraping Agent

### Features
- Automatic web scraping for teams
- News article collection
- Game statistics scraping
- Structured data extraction
- AI-enhanced when needed

### Methods
```python
# Scrape team news
news = await scraping_agent.scrape_sports_news(team="Bills", limit=5)

# Scrape game stats
stats = await scraping_agent.scrape_game_stats(game_id="401547823")

# Batch scraping
results = await scraping_agent.batch_scrape(tasks)
```

## Integration with Workflow

### Full Analysis Workflow
1. **OddsAgent** - Fetches odds from APIs
2. **ScrapingAgent** - Scrapes news and stats ← NEW!
3. **TwitterAgent** - Analyzes sentiment
4. **AnalysisAgent** - Runs Bayesian analysis
5. **ExpertAgent** - Makes expert recommendation

### Data Flow
```
Scraped Data
    ↓
Agent Memory
    ↓
Bayesian Models
    ↓
Expert Decision
```

## Supported Sites

Target sports websites:
- ESPN.com
- NFL.com
- NBA.com
- CBS Sports
- The Athletic

Automatically handles:
- Dynamic JavaScript content
- Anti-scraping measures
- Mobile vs desktop versions
- Paywalled content (basic bypass)

## Error Handling

The agent learns from mistakes:

### Anti-Scraping Detected
- Increases delay between requests
- Rotates user agents
- Uses proxy if available

### Extraction Errors
- Refines extraction schemas
- Improves prompts for LLM
- Falls back to basic scraping

## Configuration

### Environment Variables
```bash
# OpenAI API (for LLM extraction)
OPENAI_API_KEY=your_key

# Crawl4AI
CRAWL4AI_MODE=async
CRAWL4AI_TIMEOUT=30
```

### Docker
The backend Dockerfile includes:
```dockerfile
RUN pip install crawl4ai playwright
RUN playwright install chromium
```

## Advanced Features

### 1. AI-Powered Extraction
Uses GPT-4 for intelligent data extraction based on natural language schemas.

### 2. Markdown Conversion
Converts HTML to clean markdown for LLM analysis.

### 3. Batch Processing
Scrapes multiple pages concurrently with rate limiting.

### 4. Caching
Redis cache for scraped content to avoid re-scraping.

## Example Usage

```python
from app.agents.scraping_agent import ScrapingAgent

agent = ScrapingAgent()

# Scrape a page
result = await agent.execute({
    'url': 'https://www.espn.com/nfl/game/_/gameId/401547823',
    'data_type': 'scoreboard',
    'use_ai': True
})

print(result['data']['sports_info'])
# Output:
# {
#   'teams': ['Bills', 'Chiefs'],
#   'scores': [{'home': 27, 'away': 17}],
#   'injuries': ['Josh Allen - Probable']
# }
```

## Performance

- **AI Extraction**: 2-5 seconds per page
- **Basic Scraping**: 0.5-1 seconds per page
- **Batch Processing**: 10+ pages concurrently
- **Caching**: Instant retrieval for cached content

## Next Steps

Potential enhancements:
1. Add more sports sites
2. Implement proxy rotation
3. Add RAG pipeline for scraped content
4. Create scheduled scraping tasks
5. Build scraped data database

## Related Tools

Based on popular AI scraping tools:
- [Crawl4AI](https://github.com/unclecode/crawl4ai) - AI web crawler
- [ScrapegraphAI](https://github.com/VinciGit00/ScrapegraphAI) - AI scraping graphs
- [Firecrawl](https://github.com/mendableai/firecrawl) - Web data API
- [Scrapling](https://github.com/D4Vinci/Scrapling) - Undetectable scraping

