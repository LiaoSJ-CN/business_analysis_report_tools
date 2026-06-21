"""/explorer/query endpoint coverage.

Exercises the SELECT-only safety check, the data-source lookup, and
the happy/sad path of a real query against the seeded sqlite source.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.data_source import DataSource


@pytest.fixture
def seeded_sqlite_source() -> DataSource:
    db: Session = SessionLocal()
    try:
        src = db.query(DataSource).filter(DataSource.db_type == "sqlite").first()
        if not src:
            pytest.skip("no sqlite data source; create one in the UI first")
        return src
    finally:
        db.close()


def test_explorer_requires_auth(client: TestClient) -> None:
    r = client.post("/explorer/query", json={"data_source_id": 1, "sql": "SELECT 1"})
    assert r.status_code == 401


def test_explorer_rejects_non_select(
    client: TestClient, auth_headers: dict, seeded_sqlite_source: DataSource
) -> None:
    for bad in [
        "DROP TABLE x",
        "DELETE FROM x",
        "INSERT INTO x VALUES (1)",
        "UPDATE x SET a=1",
        "CREATE TABLE x (a int)",
        "ALTER TABLE x ADD COLUMN b int",
        "TRUNCATE x",
    ]:
        r = client.post(
            "/explorer/query",
            headers=auth_headers,
            json={"data_source_id": seeded_sqlite_source.id, "sql": bad},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False, f"non-SELECT {bad!r} must be rejected"
        assert "Only SELECT" in (body.get("error") or "")


def test_explorer_rejects_unknown_data_source(
    client: TestClient, auth_headers: dict
) -> None:
    r = client.post(
        "/explorer/query",
        headers=auth_headers,
        json={"data_source_id": 9999999, "sql": "SELECT 1"},
    )
    assert r.status_code == 404


def test_explorer_runs_select_against_seeded_sqlite(
    client: TestClient, auth_headers: dict, seeded_sqlite_source: DataSource
) -> None:
    r = client.post(
        "/explorer/query",
        headers=auth_headers,
        json={
            "data_source_id": seeded_sqlite_source.id,
            "sql": "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 5",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert "name" in body["columns"]
    assert 0 < body["row_count"] <= 5


def test_explorer_sql_error_returns_failure_not_500(
    client: TestClient, auth_headers: dict, seeded_sqlite_source: DataSource
) -> None:
    r = client.post(
        "/explorer/query",
        headers=auth_headers,
        json={
            "data_source_id": seeded_sqlite_source.id,
            "sql": "SELECT * FROM table_that_does_not_exist",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["row_count"] == 0
    assert body["error"]  # populated with the SQL error message


def test_explorer_populates_engine_cache(
    client: TestClient, auth_headers: dict, seeded_sqlite_source: DataSource
) -> None:
    """Regression: explorer previously built a fresh engine on every query
    and immediately disposed it, wasting TCP/auth on remote backends and
    losing `pool_pre_ping=True`. It should now share
    `_engine_cache` with `report_generator` so subsequent queries reuse
    the engine and pick up the pre-ping protection.
    """
    # Force a miss so the test is order-independent: evict any cached engine
    # for this data source first, then assert that a query repopulates it.
    from app.services.report_generator import _engine_cache, evict_engine

    evict_engine(seeded_sqlite_source.id)
    assert seeded_sqlite_source.id not in _engine_cache

    r = client.post(
        "/explorer/query",
        headers=auth_headers,
        json={
            "data_source_id": seeded_sqlite_source.id,
            "sql": "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 1",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True

    assert seeded_sqlite_source.id in _engine_cache
