# Services Layer

## Overview
Core business logic for sports data ingestion, Bayesian modeling, ML predictions, and external integrations.

## Key Services
| File | Purpose |
|------|---------|
| bayesian.py | Bayesian probability modeling and posterior calculations |
| multivariate_kelly.py | Portfolio optimization using convex risk management |
| sharp_money_detector.py | RLM, Steam, and Freeze signal detection |
| prop_analyzer.py | Player prop analysis and sharp signal identification |
| nba_ml_predictor.py | XGBoost-based NBA game outcome predictions |
| ml_service.py | General ML utilities and Hugging Face model interfaces |
| live_prop_engine.py | Real-time player prop tracking and evaluation |
| prop_probability.py | Probability distribution modeling for player stats |
| bet_tracker.py | Lifecycle management for active and historical wagers |
| bet_settlement.py | Automated grading and bankroll reconciliation |
| sports_api.py | Unified interface for external odds and data providers |
| telegram_service.py | Bot messaging and automated reporting alerts |
| twitter_analyzer.py | Sentiment analysis of social media betting signals |
| web_scraper.py | Playwright/Crawl4AI data extraction from retail books |
| supabase_service.py | Primary database operations and state persistence |
| google_sheets.py | Data export and secondary reporting integration |
| notion_integration.py | Automated sync to Notion betting journals |
| report_formatter.py | Text and markdown generation for betting reports |
| cache.py | Redis-backed performance optimization for hot data |
| sequential_thinking.py | Logic for multi-step agent reasoning processes |

## Dependency Flow
Data enters via `sports_api.py` or `web_scraper.py`, is processed by `bayesian.py` and `ml_service.py`, optimized through `multivariate_kelly.py`, and finally distributed via `telegram_service.py` or `notion_integration.py`.

## Local Conventions
- **Statelessness:** Services should not maintain internal state; use `cache.py` or `supabase_service.py` for persistence.
- **Async First:** Use `async/await` for all I/O bound operations (API calls, DB queries).
- **Atomic Logic:** Keep domain logic (e.g., devigging) separate from integration logic (e.g., API parsing).
