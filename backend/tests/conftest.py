"""
Shared pytest configuration and fixtures.

IMPORTANT – import order:
  The project has both  app/config.py  (Pydantic Settings)  and
  app/config/           (package directory with nba_dvp_slate.json).
  Python's import system favours the package over the module, so a plain
  `from app.config import settings` would resolve to the empty package
  __init__ and fail.

  We work around this by:
    1. Setting required env vars with os.environ *before* any app import.
    2. Loading app/config.py directly via importlib and registering it
       under sys.modules["app.config"], overriding the empty package entry.
"""
import os
import sys
import importlib.util

# ---------------------------------------------------------------------------
# Step 1: env vars MUST be set before app/config.py is executed because
#         Settings() reads them at class instantiation time.
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test_secret_key_not_for_production")

# ---------------------------------------------------------------------------
# Step 2: Pre-register the Settings module so `from app.config import settings`
#         finds the Pydantic Settings object instead of the empty package.
# ---------------------------------------------------------------------------
_config_path = os.path.join(os.path.dirname(__file__), "..", "app", "config", "__init__.py")
_config_spec = importlib.util.spec_from_file_location("app.config", _config_path)
_config_module = importlib.util.module_from_spec(_config_spec)
sys.modules["app.config"] = _config_module
_config_spec.loader.exec_module(_config_module)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped SQLite in-memory engine with all tables created."""
    from app.database import Base
    from app.models import bet, game, team, player
    _ = (bet, game, team, player)  # import to register models with SQLAlchemy Base

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    """Function-scoped DB session; rolls back after each test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Shared slate fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_slate():
    return {
        "date": "2026-02-22",
        "games": [
            {
                "home": "LAL",
                "away": "BOS",
                "spread": -5.5,
                "over_under": 220.0,
            },
            {
                "home": "GSW",
                "away": "MIA",
                "spread": 3.0,
                "over_under": 215.0,
            },
        ],
    }
