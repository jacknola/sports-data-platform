# Twitter Parlay Integration - Dan's AI Sports Picks Style

This document describes the Twitter API integration and RAG pipeline for posting and managing parlays in the style of Dan's AI Sports Picks.

## Overview

The system includes:
1. **Parlay Database Models** - Structured storage for parlays and legs
2. **RAG Pipeline** - Retrieval-Augmented Generation with vector embeddings
3. **Twitter Integration** - Automated posting in Dan's style
4. **API Endpoints** - Full CRUD and analytics

## Key Features

### 1. Dan's AI Sports Picks Style Formatting

Parlays are formatted with:
- Sport-specific emojis (🏀 NBA, 🏈 NFL, ⚾ MLB, 🏒 NHL, ⚽ Soccer)
- Confidence levels (HIGH, MEDIUM, LOW)
- Clean leg-by-leg breakdown
- American odds formatting (+150, -110)
- Key factors and reasoning
- Total parlay odds and payout multiplier

Example tweet:
```
🏀 NBA SUNDAY SPECIAL
Confidence: HIGH 🔥

1. Lakers ML (-150)
   └ LeBron dominates in revenge games
2. Over 215.5 (-110)
   └ Both teams rank top 5 in pace
3. Celtics -7.5 (-105)
   └ 12-2 ATS at home this season

💰 Parlay Odds: +425
💵 Payout: 5.25x

📊 Key Factors:
• Lakers on 3-game win streak
• Celtics elite home defense

🎯 BOL! #SportsBetting #Parlay
```

### 2. RAG Pipeline for Data Storage

The RAG pipeline provides:
- **Vector Embeddings**: Semantic search of historical parlays
- **Similarity Search**: Find similar past parlays
- **Performance Insights**: Historical win rates for similar bets
- **Smart Retrieval**: Context-aware parlay recommendations

### 3. Database Schema

#### Parlay Model
- `parlay_id`: Unique identifier
- `title`: Parlay name (e.g., "NBA Sunday Special")
- `sport`: Sport type
- `confidence_level` / `confidence_score`: Confidence metrics
- `legs`: Array of leg objects (JSON)
- `total_odds`: Combined parlay odds
- `potential_payout_multiplier`: Payout ratio
- `analysis`: Overall reasoning
- `key_factors`, `risks`, `tags`: Additional metadata
- `twitter_post_id`, `tweet_text`: Twitter integration
- `embedding_vector`: Vector for semantic search
- `status`: pending, won, lost, partial
- `result`, `actual_return`, `roi`: Performance tracking

#### ParlayLeg Model
- Individual leg tracking
- Game details, pick, odds
- Reasoning and supporting factors
- Result tracking

## API Endpoints

### Create Parlay
```bash
POST /api/v1/parlays
```

Example request:
```json
{
  "title": "NBA Sunday Special",
  "sport": "NBA",
  "confidence_level": "HIGH",
  "confidence_score": 85,
  "legs": [
    {
      "game": "Lakers vs Warriors",
      "pick": "Lakers ML",
      "odds": -150,
      "reasoning": "LeBron dominates in revenge games",
      "team": "Lakers",
      "market": "moneyline"
    },
    {
      "game": "Celtics vs Heat",
      "pick": "Over 215.5",
      "odds": -110,
      "reasoning": "Both teams rank top 5 in pace",
      "market": "total"
    }
  ],
  "analysis": "Strong value on home favorites with rest advantage",
  "key_factors": [
    "Lakers on 3-game win streak",
    "Celtics elite home defense"
  ],
  "tags": ["revenge-game", "pace-up", "home-favorite"]
}
```

### Get Parlay
```bash
GET /api/v1/parlays/{parlay_id}
```

### List Parlays
```bash
GET /api/v1/parlays?sport=NBA&status=pending&limit=20
```

### Post to Twitter
```bash
POST /api/v1/parlays/{parlay_id}/post-twitter?as_thread=false
```

Posts parlay to Twitter in Dan's style. Use `as_thread=true` for detailed thread with leg-by-leg analysis.

### Preview Tweet Format
```bash
GET /api/v1/parlays/{parlay_id}/format
```

Preview how the parlay will look without posting.

### Update Results
```bash
POST /api/v1/parlays/{parlay_id}/update
```

Example:
```json
{
  "status": "won",
  "result": {
    "leg_1": "won",
    "leg_2": "won",
    "leg_3": "won"
  },
  "actual_return": 5.25
}
```

### Get Insights
```bash
GET /api/v1/parlays/{parlay_id}/insights
```

Returns:
- Similar historical parlays
- Historical win rate for similar bets
- Recommendation (STRONG BET, MODERATE BET, CAUTION)

### Search Parlays
```bash
POST /api/v1/parlays/search
```

Natural language search:
```json
{
  "query": "high confidence NBA home favorites with strong defense",
  "limit": 10,
  "sport": "NBA"
}
```

### Performance Stats
```bash
GET /api/v1/parlays/stats/performance
```

Returns overall performance metrics:
- Win rate
- ROI
- Total profit/loss
- Performance by sport

### Twitter Engagement
```bash
GET /api/v1/parlays/{parlay_id}/engagement
```

Get engagement metrics (likes, retweets, impressions) for posted parlays.

## RAG Pipeline Usage

### Semantic Search Example

The RAG pipeline automatically:
1. Generates embeddings when parlays are created
2. Finds similar historical parlays
3. Provides performance insights

```python
from app.services.rag_pipeline import RAGPipeline

rag = RAGPipeline()

# Store parlay with automatic embedding
await rag.store_parlay(parlay_id, parlay_data)

# Search by natural language
results = await rag.search_parlays_by_text(
    "high confidence NBA parlays with pace-up games"
)

# Get insights
insights = await rag.get_parlay_insights(parlay_id)
```

## Twitter Service Usage

### Format and Post

```python
from app.services.twitter_analyzer import TwitterAnalyzer

twitter = TwitterAnalyzer()

# Format tweet (doesn't post)
tweet_text = twitter.format_dan_style_parlay(parlay_data)

# Post single tweet
result = twitter.post_parlay_tweet(parlay_data)

# Post as thread with detailed analysis
thread = twitter.post_parlay_thread(
    parlay_data,
    include_detailed_analysis=True
)

# Get engagement metrics
engagement = twitter.get_parlay_engagement(tweet_id)
```

## Configuration

### Environment Variables

Add to your `.env`:

```bash
# Twitter API Credentials
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_CONSUMER_KEY=your_consumer_key
TWITTER_CONSUMER_SECRET=your_consumer_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# ML Models
HUGGINGFACE_MODEL=cardiffnlp/twitter-roberta-base-sentiment-latest
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
```

## Database Migration

Run migrations to create parlay tables:

```bash
cd backend
alembic revision --autogenerate -m "Add parlay tables"
alembic upgrade head
```

## Example Workflow

### Complete Parlay Workflow

```python
# 1. Create parlay
response = await create_parlay(parlay_data)
parlay_id = response['parlay_id']

# 2. Get insights from similar parlays
insights = await get_parlay_insights(parlay_id)
print(f"Similar parlays: {insights['similar_parlays_found']}")
print(f"Historical win rate: {insights['historical_win_rate']:.1%}")
print(f"Recommendation: {insights['recommendation']}")

# 3. Preview tweet format
preview = await preview_parlay_tweet(parlay_id)
print(f"Tweet: {preview['tweet_text']}")
print(f"Length: {preview['character_count']}/280")

# 4. Post to Twitter
tweet_result = await post_parlay_to_twitter(parlay_id)
print(f"Posted: {tweet_result['url']}")

# 5. After games complete, update results
await update_parlay_result(parlay_id, {
    "status": "won",
    "actual_return": 5.25
})

# 6. Check Twitter engagement
engagement = await get_parlay_twitter_engagement(parlay_id)
print(f"Likes: {engagement['likes']}")
print(f"Retweets: {engagement['retweets']}")
```

## Best Practices

### Parlay Construction
1. **3-5 Legs**: Optimal for Dan's style
2. **Clear Reasoning**: Each leg needs compelling reasoning
3. **Confidence Levels**: Honest assessment of confidence
4. **Key Factors**: 2-4 key factors that support the parlay
5. **Risk Awareness**: Acknowledge potential risks

### Twitter Posting
1. **Timing**: Post 2-4 hours before first game
2. **Engagement**: Use hashtags and emojis strategically
3. **Thread Format**: Use threads for complex parlays (4+ legs)
4. **Follow-up**: Post results after games complete

### RAG Pipeline
1. **Tag Consistently**: Use consistent tags for better retrieval
2. **Rich Analysis**: More detailed analysis = better embeddings
3. **Update Results**: Always update results for learning
4. **Monitor Similar**: Check similar parlays before posting

## Architecture

```
┌─────────────────┐
│   API Request   │
└────────┬────────┘
         │
         v
┌─────────────────┐     ┌──────────────┐
│ Parlay Router   │────>│  PostgreSQL  │
└────────┬────────┘     └──────────────┘
         │
         ├──────> ┌──────────────────┐
         │        │  RAG Pipeline    │
         │        │  - Embeddings    │
         │        │  - Similarity    │
         │        └──────────────────┘
         │
         └──────> ┌──────────────────┐
                  │ Twitter Service  │
                  │  - Format        │
                  │  - Post          │
                  │  - Engagement    │
                  └──────────────────┘
```

## Testing

Test the integration:

```bash
# Start server
cd backend
python run_server.py

# Create test parlay
curl -X POST http://localhost:8000/api/v1/parlays \
  -H "Content-Type: application/json" \
  -d @test_parlay.json

# Preview tweet
curl http://localhost:8000/api/v1/parlays/{parlay_id}/format

# Get insights
curl http://localhost:8000/api/v1/parlays/{parlay_id}/insights
```

## Future Enhancements

1. **Auto-posting**: Scheduled parlay posts based on game times
2. **Performance Analytics**: Advanced tracking and visualization
3. **Community Engagement**: Reply handling and follower analysis
4. **Multi-platform**: Extend to Instagram, Facebook, etc.
5. **AI Generation**: Auto-generate parlays from game data
6. **Odds Integration**: Real-time odds from multiple sportsbooks
7. **Bankroll Management**: Kelly criterion integration

## Support

For issues or questions:
- Check API documentation at `/docs`
- Review logs for error details
- Ensure Twitter API credentials are valid
- Verify database migrations are current
