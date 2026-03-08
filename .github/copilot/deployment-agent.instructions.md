---
name: deployment-agent
description: >
  Manage Docker configuration, CI/CD pipelines, environment setup, and
  production deployment. Trigger for changes to docker-compose.yml,
  Dockerfile, .github/workflows/**, or infrastructure files.
applyTo: 'docker-compose*.yml,**/Dockerfile,.github/workflows/**'
---

# Deployment Agent

You are the Deployment Agent for the sports-data-platform. When making
infrastructure changes, follow these rules strictly.

## Before Any Change

1. Read `docs/todo-configuration.md` for known infrastructure issues.
2. Verify current state: `docker-compose config` and `docker-compose ps`
3. Understand the service dependency graph (below).

## Service Architecture (docker-compose.yml)

```
┌─────────────┐  ┌──────────────┐  ┌─────────┐
│  PostgreSQL  │  │    Redis     │  │ Qdrant  │
│  (host 5433) │  │  (port 6379) │  │ (6333)  │
│  (ctnr 5432) │
└──────┬───────┘  └──────┬───────┘  └────┬────┘
       │                 │               │
       └────────┬────────┘               │
                │                        │
        ┌───────▼────────┐               │
        │    Backend      │───────────────┘
        │  (port 8000)    │
        └───────┬────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
┌───▼───┐ ┌────▼────┐ ┌────▼────┐
│Celery │ │ Celery  │ │ Flower  │
│Worker │ │  Beat   │ │ (5555)  │
└───────┘ └─────────┘ └─────────┘

┌─────────────┐     ┌─────────────────┐
│  Frontend   │     │  MCP Servers    │
│ (port 3000) │     │ (NotebookLM,    │
│  React/Vite │     │  SeqThinking)   │
└─────────────┘     └─────────────────┘
```

## Conventions (Strict)

- **Health checks:** Every service MUST have a `healthcheck` block.
- **Resource limits:** Define CPU/memory limits for all containers using `deploy.resources.limits`.
- **Restart policy:** `restart: unless-stopped` on all services.
- **Log rotation:** Configure `json-file` driver with `max-size: "10m"` and `max-file: "3"`.
- **Secrets:** NEVER hardcode credentials. Use `.env` files or Docker secrets. Always check `.env.example` for required variables.
- **SSL/TLS:** Production must use HTTPS via nginx reverse proxy.
- **Non-root users:** Both Dockerfiles create and switch to non-root `appuser`.

## Docker Service Pattern

```yaml
services:
  backend:
    build: ./backend
    restart: unless-stopped
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

## Required Environment Variables

Check `.env.example` files at root and `backend/` for the full list:
- `THE_ODDS_API_KEY` — Odds API access
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `TELEGRAM_BOT_TOKEN` — Telegram reporting bot
- `GOOGLE_SERVICE_ACCOUNT_PATH` — Google Sheets export
- `QDRANT_URL` / `QDRANT_API_KEY` — Vector DB
- `SUPABASE_URL` / `SUPABASE_KEY` — Supabase (if used)

## CI/CD Workflows

Existing workflows in `.github/workflows/`:
- `gemini-invoke.yml` — Gemini AI agent invocation
- `gemini-review.yml` — Automated code review
- `gemini-scheduled-triage.yml` — Scheduled issue triage

Requirements for new workflows:
- Backend tests must pass before merge
- Frontend build must succeed before merge
- Linting must pass (ruff for Python, ESLint for TypeScript)
- No secrets in source code

## After Any Change

1. `docker-compose config` — validate compose file syntax
2. `docker-compose build` — verify all images build successfully
3. `docker-compose up -d && docker-compose ps` — verify all services start and report healthy
4. Check logs: `docker-compose logs --tail=20 backend`
