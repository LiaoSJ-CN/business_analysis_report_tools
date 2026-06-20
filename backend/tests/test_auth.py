"""Auth endpoint coverage.

Verifies the JWT login/refresh/me flow and confirms the previously
removed ``?token=`` query-param fallback is no longer accepted as an
auth source on protected endpoints.
"""

from fastapi.testclient import TestClient


def test_login_success_returns_token_pair(client: TestClient) -> None:
    r = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20
    assert isinstance(body["refresh_token"], str) and len(body["refresh_token"]) > 20
    # Access and refresh tokens must be distinct.
    assert body["access_token"] != body["refresh_token"]


def test_login_wrong_password_is_401(client: TestClient) -> None:
    r = client.post("/auth/login", json={"username": "admin", "password": "WRONG"})
    assert r.status_code == 401


def test_login_wrong_username_is_401(client: TestClient) -> None:
    r = client.post("/auth/login", json={"username": "nobody", "password": "admin"})
    assert r.status_code == 401


def test_me_with_valid_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"username": "admin"}


def test_me_without_token_is_401(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_garbage_token_is_401(client: TestClient) -> None:
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_refresh_with_valid_refresh_token(client: TestClient) -> None:
    login = client.post("/auth/login", json={"username": "admin", "password": "admin"}).json()
    r = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)


def test_refresh_with_access_token_is_rejected(client: TestClient) -> None:
    """Access tokens must not be accepted at /refresh (separate ``type`` claim)."""
    login = client.post("/auth/login", json={"username": "admin", "password": "admin"}).json()
    r = client.post("/auth/refresh", json={"refresh_token": login["access_token"]})
    assert r.status_code == 401


def test_query_param_token_fallback_rejected(client: TestClient, auth_headers: dict) -> None:
    """``?token=`` was removed — protected endpoints must NOT honor it.

    The auth path now strictly requires an ``Authorization: Bearer``
    header. A token in a query string should be rejected with 401.
    """
    token = auth_headers["Authorization"].split(" ", 1)[1]
    r = client.get("/auth/me", params={"token": token})
    assert r.status_code == 401, (
        f"expected 401 for ?token= fallback, got {r.status_code}; "
        "the query-param auth path must stay removed"
    )
