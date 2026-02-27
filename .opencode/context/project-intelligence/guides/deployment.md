<!-- Context: project-intelligence/guides/deployment | Priority: medium | Version: 1.0 | Updated: 2026-02-27 -->

# Deployment Guide

**Purpose**: Deployment options and monitoring for the sports betting platform.
**Last Updated**: 2026-02-27

## Deployment Options

| Method | Best For | Complexity |
|--------|----------|------------|
| **Docker Compose** (recommended) | Production | Medium |
| systemd services | Linux servers | High |
| tmux/screen | Quick testing | Low |

## Docker Compose (Recommended)

```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# Docs:     http://localhost:8000/docs
```

## Agent Processes

6 background agents run continuously:
- OddsAgent, AnalysisAgent, ExpertAgent
- ScrapingAgent, TelegramAgent, OrchestrationAgent

## Scheduling

```bash
# Cron: Run orchestrator hourly
0 * * * * cd /path/to/project && python3 backend/run_orchestrator.py

# Telegram: 3x daily reports
python3 backend/telegram_cron.py --daemon
```

## Monitoring

```bash
docker-compose logs -f backend     # Live backend logs
docker-compose logs -f frontend    # Live frontend logs
journalctl -u sports-betting -f    # systemd logs
tail -f logs/app.log               # Direct log file
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Python version mismatch | Use 3.9+ |
| Missing deps | `pip install -r backend/requirements.txt` |
| Env vars missing | Copy `.env.example` → `.env`, fill values |
| Port conflicts | Check 3000/8000 aren't in use |
| Docker stale | `docker-compose down && docker-compose up --build` |

## 📂 Codebase References

- **Docker**: `docker-compose.yml`, `Dockerfile`
- **Server**: `backend/run_server.py`
- **Cron**: `backend/telegram_cron.py`
- **Full docs**: `DEPLOYMENT.md` (root)
