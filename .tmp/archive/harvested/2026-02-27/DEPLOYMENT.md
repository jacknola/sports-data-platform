# Deployment Guide for Sports Data Platform

## Current Status
- ✅ Repository initialized with git
- ✅ All code committed (8 commits)
- ✅ .gitignore configured with sensitive files excluded
- ⚠️ No remote repository configured yet

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository named `sports-data-platform`
3. **DO NOT** initialize with README, .gitignore, or license (we already have these)
4. Copy the repository URL (e.g., `https://github.com/yourusername/sports-data-platform.git`)

## Step 2: Connect to Remote Repository

```bash
cd /Users/jackcurran/sports-data-platform

# Add remote repository
git remote add origin https://github.com/yourusername/sports-data-platform.git

# Verify remote was added
git remote -v

# Push to GitHub
git push -u origin master
```

## Step 3: Set Up Background Agent Processes

### Option A: Using systemd (Linux/macOS)

Create a systemd service file:

```bash
# Create service file
sudo nano /etc/systemd/system/sports-data-agents.service
```

Add this content:

```ini
[Unit]
Description=Sports Data Platform Agents
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/Users/jackcurran/sports-data-platform/backend
ExecStart=/usr/bin/python3 run_server.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/sports-data-agents.log
StandardError=append:/var/log/sports-data-agents.error.log

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable sports-data-agents.service
sudo systemctl start sports-data-agents.service
sudo systemctl status sports-data-agents.service
```

### Option B: Using Docker Compose (Recommended)

Your project already has `docker-compose.yml` configured. To run in background:

```bash
cd /Users/jackcurran/sports-data-platform

# Start services in detached mode
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Option C: Using tmux/screen

```bash
# Install tmux if needed
brew install tmux  # macOS
# or
sudo apt-get install tmux  # Linux

# Start tmux session
tmux new -s sports-agents

# Navigate to project and start
cd /Users/jackcurran/sports-data-platform/backend
python run_server.py

# Detach: Press Ctrl+B, then D
# Reattach: tmux attach -t sports-agents
```

## Step 4: Verify Agents Are Running

```bash
# Check if backend is responding
curl http://localhost:8000/health

# Or visit in browser
open http://localhost:8000
```

## Background Agent Activities

Your system includes these agents that can run in the background:

1. **OrchestratorAgent** - Coordinates multiple agents
2. **OddsAgent** - Fetches and analyzes betting odds
3. **TwitterAgent** - Analyzes Twitter sentiment
4. **AnalysisAgent** - Runs Bayesian analysis
5. **ExpertAgent** - Provides expert insights
6. **ScrapingAgent** - Scrapes sports websites

## Scheduled Tasks

To run agents on a schedule, use cron or systemd timers:

### Example cron job (runs every hour)

```bash
# Edit crontab
crontab -e

# Add this line (adjust path as needed)
0 * * * * cd /Users/jackcurran/sports-data-platform/backend && /usr/bin/python3 -m app.agents.orchestrator
```

## Monitoring

Check agent status and logs:

```bash
# Docker logs
docker-compose logs -f backend

# System logs (if using systemd)
sudo journalctl -u sports-data-agents -f

# Application logs
tail -f /var/log/sports-data-agents.log
```

## Troubleshooting

### Agents not starting
1. Check Python version: `python3 --version` (needs 3.9+)
2. Install dependencies: `pip install -r backend/requirements.txt`
3. Check environment variables in `.env` file

### Port already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Docker issues
```bash
# Rebuild containers
docker-compose up -d --build

# View detailed logs
docker-compose logs backend
```

## Next Steps

1. ✅ Push code to GitHub
2. ✅ Set up background agent process
3. Configure scheduled tasks for automated analysis
4. Set up monitoring and alerting
5. Integrate with deployment pipeline (CI/CD)
