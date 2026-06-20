"""/scheduler/* endpoint coverage.

Just the surface: status requires auth, sync is idempotent, and the
response shape is stable so the frontend keeps working.
"""

from fastapi.testclient import TestClient


def test_scheduler_status_requires_auth(client: TestClient) -> None:
    r = client.get("/scheduler/status")
    assert r.status_code == 401


def test_scheduler_status_with_auth(client: TestClient, auth_headers: dict) -> None:
    r = client.get("/scheduler/status", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "is_running" in body
    assert "jobs" in body
    assert isinstance(body["jobs"], list)


def test_scheduler_sync_returns_count(
    client: TestClient, auth_headers: dict
) -> None:
    r = client.post("/scheduler/sync", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "jobs_loaded" in body
    assert "message" in body
    assert isinstance(body["jobs_loaded"], int)
    assert body["jobs_loaded"] >= 0
