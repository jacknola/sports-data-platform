# Technology Stack

## Backend
- **Language:** Python 3.11+
- **Framework:** FastAPI (High performance, async support)
- **ORM:** SQLAlchemy 2.0+ (with async support)
- **Database:** PostgreSQL (Primary relational data)
- **Cache & Task Queue:** Redis
- **Background Worker:** Celery (for long-running analysis and scraping)
- **Logging:** loguru (Structured logging)
- **Configuration:** Pydantic BaseSettings

## Frontend
- **Framework:** React (Vite-based)
- **Language:** TypeScript
- **State Management:** TanStack Query (React Query)
- **Styling:** Tailwind CSS
- **Data Visualization:** Recharts
- **Icons:** Lucide React

## Data & Analytics
- **Bayesian Modeling:** PyMC
- **Machine Learning:** Hugging Face Transformers, XGBoost, TensorFlow, scikit-learn
- **Vector Database:** Qdrant (for situational similarity and RAG)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **Sports Data:** nba_api
- **Web Scraping:** Crawl4AI, Playwright, Selenium
- **Evaluation:** Custom Brier Score and ROI metrics framework

## Integrations
- **Database/Reporting:** Notion, Google Sheets
- **Communication:** Telegram (Bot API), Twitter (X API)

## Infrastructure
- **Containerization:** Docker, Docker Compose
- **Migrations:** Alembic
- **Testing:** pytest, pytest-asyncio, pytest-cov
- **Linting:** ruff (Python), eslint (TypeScript)
