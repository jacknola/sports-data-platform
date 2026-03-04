"""Tests for FastAPI health and root endpoints (no DB/Redis required)"""
import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_mock_settings():
    """Build a minimal settings-like object."""
    s = MagicMock()
    s.DATABASE_URL = "sqlite+aiosqlite:///./test.db"
    s.REDIS_URL = "redis://localhost:6379"
    s.API_HOST = "0.0.0.0"
    s.API_PORT = 8000
    s.DEBUG = False
    return s


def _inject_stubs():
    """
    Inject lightweight stub modules so that importing main.py doesn't
    require a real database, Redis, or external API credentials.
    """
    stubs = {}

    # pydantic_settings stub
    ps = types.ModuleType("pydantic_settings")
    ps.BaseSettings = object
    stubs["pydantic_settings"] = ps

    # app.config stub (resolves the config.py vs config/ conflict)
    cfg_mod = types.ModuleType("app.config")
    cfg_mod.settings = _make_mock_settings()
    stubs["app.config"] = cfg_mod

    # app.database stub
    db_mod = types.ModuleType("app.database")
    db_mod.init_db = AsyncMock()
    db_mod.get_db = MagicMock()
    stubs["app.database"] = db_mod

    # aioredis / redis stubs used by cache service
    for name in ("redis", "aioredis"):
        m = types.ModuleType(name)
        stubs[name] = m

    # app.services.cache stub
    cache_mod = types.ModuleType("app.services.cache")
    cache_cls = MagicMock()
    cache_cls.get_instance = AsyncMock(return_value=MagicMock())
    cache_mod.RedisCache = cache_cls
    stubs["app.services.cache"] = cache_mod

    # Stub all router modules so their DB / external dependencies don't load
    router_names = [
        "app.routers.bets",
        "app.routers.analyze",
        "app.routers.odds",
        "app.routers.sentiment",
        "app.routers.predictions",
        "app.routers.notion",
        "app.routers.agents",
        "app.routers.google_sheets",
        "app.routers.dvp",
        "app.routers.props",
        "app.routers.live_props",
        "app.routers.cbb_sharp",
        "app.routers.parlays",
        "app.routers.historical",

    ]
    for rname in router_names:
        r = types.ModuleType(rname)
        from fastapi import APIRouter
        r.router = APIRouter()
        stubs[rname] = r

    # Patch into sys.modules (only where not already present)
    for name, mod in stubs.items():
        if name not in sys.modules:
            sys.modules[name] = mod

    return stubs


@pytest.fixture(scope="module")
def client():
    """
    Provide a TestClient for the FastAPI app with all heavy dependencies stubbed.
    """
    import os
    os.environ["ENVIRONMENT"] = "test"

    # Purge only `main` and `app.routers.*` so stub routers take effect on a
    # fresh import of main.py.  Do NOT purge app.models.*, app.services.*, or
    # app.database — those share global state (SQLAlchemy Base.metadata,
    # module-level globals) that other tests depend on; re-importing them
    # corrupts that state in ways that break later tests.
    _purge_prefixes = ("app.routers.",)
    for key in list(sys.modules.keys()):
        if key == "main" or any(key.startswith(p) for p in _purge_prefixes):
            sys.modules.pop(key, None)

    # Inject stubs AFTER the purge so router stubs land in sys.modules
    _inject_stubs()

    # Now safely import (stubs already in sys.modules)
    from fastapi.testclient import TestClient
    import importlib
    main_mod = importlib.import_module("main")
    app = main_mod.app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_root_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_root_has_status_running(client):
    data = client.get("/").json()
    assert data.get("status") == "running"


def test_root_has_version(client):
    data = client.get("/").json()
    assert "version" in data


def test_health_returns_healthy(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_docs_accessible(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_openapi_schema(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "Sports Data Intelligence Platform"
