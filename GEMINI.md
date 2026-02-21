# Sports Data Intelligence Platform - System Context

## Project Overview
The **Sports Data Intelligence Platform** is a sophisticated sports betting analysis and automation system. It utilizes a multi-agent orchestration pattern to combine real-time odds, social sentiment (Twitter), expert reasoning (Gemini AI), and quantitative models (Bayesian & ML) to identify value in sports betting markets.

### Core Architecture
- **Backend**: FastAPI (Python 3.11) with an asynchronous multi-agent system.
- **Frontend**: React (TypeScript) powered by Vite and Tailwind CSS.
- **Agent Orchestration**: An `OrchestratorAgent` coordinates specialized agents (`OddsAgent`, `AnalysisAgent`, `TwitterAgent`, `ExpertAgent`, `ScrapingAgent`) to perform deep-dive analysis.
- **Intelligence Layer**: 
    - **Gemini AI**: Used for complex reasoning and "Sequential Thinking" in betting scenarios.
    - **Bayesian Modeling**: Beta-distribution based posterior probability calculations with conference-tier variance penalties.
    - **ML Services**: Hugging Face (RoBERTa) for sentiment analysis and XGBoost for NBA predictions.
- **Data Layer**: Supabase/PostgreSQL for persistence, Redis for caching and Celery task queuing.

## Building and Running

### Docker (Recommended)
The entire stack is containerized for easy deployment and development.
```bash
docker-compose up --build
```
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Flower (Celery Monitor)**: http://localhost:5555

### Local Development

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Update with your API keys
python main.py
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Development Conventions

### Coding Style & Standards
- **Backend**: Follows modern FastAPI patterns. Use `loguru` for logging. Asynchronous operations are preferred for API and Agent tasks.
- **Frontend**: Use functional components with hooks. Styling is strictly via Tailwind CSS.
- **State Management**: Data fetching and caching are handled by `@tanstack/react-query`.
- **API Communication**: The frontend uses a centralized Axios instance in `src/utils/api.ts` which returns `response.data` directly via interceptors.

### Agent Workflow
- Agents inherit from `BaseAgent` and implement `execute` and `learn_from_mistake`.
- Logic for "Should I use AI?" is encapsulated in the agents to optimize costs and performance.
- Memory of agent decisions is stored in `AgentMemory` to facilitate continuous learning.

### Configuration
- Environment variables are managed via Pydantic `BaseSettings` in `backend/app/config.py`.
- Always update `backend/.env.example` when adding new configuration requirements.

## System Mandates
- **API Access**: All frontend requests must be prefixed with `/api` for the Vite proxy to route them correctly to the backend container.
- **Docker Networking**: When running in Docker, the frontend communicates with the backend via the service name `http://backend:8000`.
- **Security**: Never commit the `.env` file. Ensure sensitive keys for Gemini, Twitter, and Supabase are rotated regularly.
