# API Routers

## Overview
FastAPI endpoints exposing betting intelligence, odds, predictions, and integrations.

## Endpoints
| Router | Path | Key Endpoints |
|--------|------|---------------|
| bets.py | /api/v1/bets | GET /bets, POST /bayesian |
| odds.py | /api/v1/odds | GET /odds/{sport} |
| predictions.py | /api/v1/predictions | GET /predictions, POST /generate |
| agents.py | /api/v1/agents | POST /analyze, GET /status |
| props.py | /api/v1/props | GET /{sport}, GET /{sport}/best |
| live_props.py | /api/v1/props/live | POST /analyze, POST /slate |
| sentiment.py | /api/v1/sentiment | GET /{team}, POST /analyze |
| analyze.py | /api/v1/analyze | POST / |
| notion.py | /api/v1/notion | POST /sync |
| google_sheets.py | /api/v1/sheets | POST /bet-analysis |

## Patterns
- Uses `Dict[str, Any]` for flexible request/response
- All routers use `APIRouter()` with @router decorators
- Mounted under /api/v1 prefix

## Local Conventions
- Keep logic in services; routers only handle validation/response formatting
- Use proper HTTP status codes
- Add docstrings for complex endpoints (Swagger UI)
- Group related functionality in single router files
