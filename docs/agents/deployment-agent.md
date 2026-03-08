# Deployment Agent — Actionable Tasks

> This agent handles Docker configuration, CI/CD pipelines, environment setup, monitoring, and production deployment.

---

## Identity & Scope

- **Name:** Deployment Agent
- **Tools:** Docker, Docker Compose, GitHub Actions, nginx, systemd
- **Responsibilities:** Container management, CI/CD, environment config, health monitoring, SSL/TLS

---

## Setup Commands

```bash
# Build all containers
docker-compose build

# Start full stack
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Verification Commands

```bash
# Health checks
curl http://localhost:8000/api/v1/health
curl http://localhost:3000

# Backend API docs
curl http://localhost:8000/docs

# Container resource usage
docker stats
```

---

## Priority Tasks

### P0 — Critical Infrastructure

- [ ] **Add health checks to docker-compose.yml**
  ```yaml
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  frontend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
  ```

- [ ] **Add restart policies**
  ```yaml
  backend:
    restart: unless-stopped
  frontend:
    restart: unless-stopped
  ```

- [ ] **Add resource limits**
  ```yaml
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
  ```

### P1 — CI/CD Pipeline

- [ ] **Create `.github/workflows/ci.yml`**
  ```yaml
  name: CI
  on: [push, pull_request]
  jobs:
    backend-tests:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version: '3.9'
        - run: pip install -r backend/requirements.txt
        - run: cd backend && pytest tests/unit/ --tb=short -q
    
    frontend-build:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with:
            node-version: '18'
        - run: cd frontend && npm ci && npm run build
    
    lint:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - run: pip install ruff black
        - run: ruff check backend/app/
        - run: cd frontend && npm ci && npm run lint
  ```

- [ ] **Create `.github/workflows/deploy.yml`** for production deployment
  - Trigger on main branch push
  - Build Docker images
  - Push to container registry
  - Deploy to production server

### P2 — Environment Management

- [ ] **Create `env.production.example`** with production values documented
  ```bash
  # REQUIRED
  DATABASE_URL=postgresql://user:pass@host:5432/dbname
  SECRET_KEY=<generate-with-openssl-rand-hex-32>
  REDIS_URL=redis://:password@redis-host:6379/0

  # REQUIRED API KEYS
  ODDS_API_KEY=<your-key>
  TELEGRAM_BOT_TOKEN=<your-token>
  TELEGRAM_CHAT_ID=<your-chat-id>

  # OPTIONAL
  GOOGLE_SHEETS_CREDENTIALS_PATH=/app/credentials.json
  SUPABASE_URL=https://your-project.supabase.co
  SUPABASE_KEY=<your-key>
  ```

- [ ] **Add environment validation at startup**
  ```python
  # In main.py or config
  REQUIRED_VARS = ["DATABASE_URL", "SECRET_KEY", "ODDS_API_KEY"]
  missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
  if missing:
      raise EnvironmentError(f"Missing required env vars: {missing}")
  ```

- [ ] **Document which env vars are required vs optional** in `.env.example`

### P3 — SSL/TLS & Security

- [ ] **Add nginx reverse proxy** with SSL termination
  ```nginx
  server {
      listen 443 ssl;
      ssl_certificate /etc/letsencrypt/live/domain/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/domain/privkey.pem;

      location /api/ {
          proxy_pass http://backend:8000/;
      }
      location / {
          proxy_pass http://frontend:3000/;
      }
  }
  ```

- [ ] **Add security headers in nginx**
  ```nginx
  add_header X-Content-Type-Options nosniff;
  add_header X-Frame-Options DENY;
  add_header X-XSS-Protection "1; mode=block";
  add_header Content-Security-Policy "default-src 'self'";
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
  ```

### P4 — Monitoring & Logging

- [ ] **Add structured logging format** for production
  ```python
  # In main.py
  import json
  logger.add(
      "/var/log/app/backend.log",
      format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
      rotation="100 MB",
      retention="30 days",
      compression="gz"
  )
  ```

- [ ] **Add Docker log rotation**
  ```yaml
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
  ```

- [ ] **Create `/api/v1/health` endpoint** (if not exists) with deep checks
  ```python
  @router.get("/health")
  async def health():
      checks = {
          "database": await check_db(),
          "redis": await check_redis(),
          "odds_api": await check_odds_api(),
      }
      status = "healthy" if all(checks.values()) else "degraded"
      return {"status": status, "checks": checks}
  ```

---

## Production Checklist

Before deploying:

- [ ] All unit tests pass
- [ ] No hardcoded credentials in source
- [ ] SECRET_KEY is unique and strong
- [ ] DATABASE_URL points to production database
- [ ] CORS origins restricted to production domains
- [ ] Rate limiting enabled
- [ ] SSL/TLS configured
- [ ] Health checks configured
- [ ] Log rotation enabled
- [ ] Backup strategy documented
- [ ] Rollback procedure documented

---

## Docker Commands Reference

```bash
# Rebuild single service
docker-compose build backend

# View logs for specific service
docker-compose logs -f --tail=100 backend

# Execute command in running container
docker-compose exec backend python3 -c "from app.config import settings; print(settings.DATABASE_URL)"

# Restart single service
docker-compose restart backend

# Scale service
docker-compose up -d --scale backend=2

# Remove all containers and volumes
docker-compose down -v
```
