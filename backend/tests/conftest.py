"""Shared pytest fixtures.

Tests rely on:
  - A running FastAPI app under ``app.main:app`` (uses the real
    ``app.db`` SQLite metadata database — same as dev).
  - A seeded dataset: at least one active ``Report`` and one ``DataSource``.
    Run ``python scripts/seed_reports.py`` once if the DB is empty.
  - ``JWT_SECRET_KEY`` set in the environment before the app modules are
    imported, so the access tokens we mint here use a stable key.

Tests that need a fresh sqlite (engine cache, data source CRUD for
non-mutating checks) use the ``tmp_sqlite_path`` fixture, which gives
an isolated file under pytest's tmp dir and never touches ``app.db``.
"""

import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path so `from app...` works regardless
# of where pytest is invoked from.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Stable JWT secret so tokens minted in tests verify on subsequent
# requests. Must be set BEFORE app modules import settings.
os.environ.setdefault("JWT_SECRET_KEY", "pytest-secret-do-not-use-in-prod")

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.jwt_auth import create_access_token
from app.services.report_generator import _engine_cache


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Authorization header with a freshly-minted access token for admin."""
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client() -> TestClient:
    """A FastAPI TestClient bound to the real ``app`` instance.

    Use ``client`` (not a function-scoped fresh app) so router-level
    state and the APScheduler singleton behave like production.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tmp_sqlite_path(tmp_path) -> str:
    """Path to a fresh sqlite file under pytest's tmp dir.

    The file is not pre-created — caller's responsibility to populate if
    needed. Always auto-cleaned by pytest's tmp_path teardown.
    """
    return str(tmp_path / "test.db")


@pytest.fixture
def engine_cache_cleanup():
    """Clear the module-level engine cache before AND after the test.

    Engine cache is process-global; without this, a test polluting the
    cache can leak into siblings. We also evict on teardown to free DB
    file handles on Windows / test parallelism.
    """
    _engine_cache.clear()
    yield
    # Dispose any engines left behind so sqlite file handles are released.
    for engine in list(_engine_cache.values()):
        engine.dispose()
    _engine_cache.clear()
