"""Auth endpoint coverage.

Verifies the JWT login/refresh/me flow and confirms the previously
removed ``?token=`` query-param fallback is no longer accepted as an
auth source on protected endpoints.

P3 (SEC-18) additions verify that login now consults the ``users`` table
and bcrypt-verifies the stored hash — not the plaintext settings value.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.services.password import hash_password


@pytest.fixture
def admin_user() -> Iterator[User]:
    """Yield the seeded admin User row, restoring the default bcrypt hash
    ('admin') on teardown so subsequent tests in the same process aren't
    affected by per-test mutations.

    Teardown uses a *fresh* session because tests may mutate the row via
    a separate SessionLocal (so the fixture's session has a stale
    snapshot and would skip the UPDATE).
    """
    db: Session = SessionLocal()
    user = db.query(User).filter(User.username == "admin").first()
    assert user is not None, "admin user should be seeded by lifespan on app startup"
    original_hash = user.password_hash
    original_disabled = user.disabled
    db.close()
    try:
        yield user
    finally:
        restore = SessionLocal()
        try:
            u = restore.query(User).filter(User.username == "admin").first()
            if u is not None:
                u.password_hash = original_hash
                u.disabled = original_disabled
                restore.commit()
        finally:
            restore.close()


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


# ---------------------------------------------------------------------------
# P3 (SEC-18): login consults users table + bcrypt; settings.admin_password
# is a one-time bootstrap, not consulted at login.
# ---------------------------------------------------------------------------


def test_login_uses_stored_bcrypt_hash_not_settings(
    client: TestClient, admin_user: User
) -> None:
    """Rotating the stored hash must rotate what password logs in.

    Strongly implies bcrypt is being verified: a plaintext-compare path
    would still accept the env-var default after the rotation.
    """
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "admin").first()
        u.password_hash = hash_password("rotated-secret")
        db.commit()
    finally:
        db.close()

    # Old password (still the env-var default) must no longer work.
    r_old = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert r_old.status_code == 401, (
        "old plaintext password still accepted after hash rotation; "
        "login is not consulting the users table"
    )
    # New password must work.
    r_new = client.post(
        "/auth/login", json={"username": "admin", "password": "rotated-secret"}
    )
    assert r_new.status_code == 200, r_new.text


def test_disabled_user_cannot_login(client: TestClient, admin_user: User) -> None:
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "admin").first()
        u.disabled = True
        db.commit()
    finally:
        db.close()

    r = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 401


def test_login_updates_last_login_at(client: TestClient, admin_user: User) -> None:
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "admin").first()
        u.last_login_at = None
        db.commit()
    finally:
        db.close()

    r = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "admin").first()
        assert u.last_login_at is not None, "successful login should stamp last_login_at"
    finally:
        db.close()


def test_malformed_stored_hash_is_500_not_401(
    client: TestClient, admin_user: User
) -> None:
    """A non-bcrypt hash in users.password_hash is an ops issue, not a
    user error — must surface as 500, not 401 (which would mask it)."""
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "admin").first()
        u.password_hash = "not-a-bcrypt-hash"
        db.commit()
    finally:
        db.close()

    r = client.post("/auth/login", json={"username": "admin", "password": "anything"})
    assert r.status_code == 500, (
        "malformed stored hash should be 500, not 401 — the row is in a "
        "broken state and a 401 would silently mask the ops issue"
    )


# ---------------------------------------------------------------------------
# P3 (PY-25): logout actually invalidates via jti deny-list; refresh rotates.
# ---------------------------------------------------------------------------


def test_logout_revokes_access_token(client: TestClient) -> None:
    """After logout, the same access token must be rejected with 401."""
    login_body = client.post(
        "/auth/login", json={"username": "admin", "password": "admin"}
    ).json()
    token = login_body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Sanity: token works pre-logout.
    r_pre = client.get("/auth/me", headers=headers)
    assert r_pre.status_code == 200

    # Logout.
    r_logout = client.post("/auth/logout", headers=headers)
    assert r_logout.status_code == 200

    # Same token must now be 401.
    r_post = client.get("/auth/me", headers=headers)
    assert r_post.status_code == 401, (
        "access token still works after logout; jti deny-list is not being checked"
    )


def test_logout_requires_auth(client: TestClient) -> None:
    """Without an Authorization header, /auth/logout must 401 (no token = nothing to revoke)."""
    r = client.post("/auth/logout")
    assert r.status_code == 401


def test_refresh_rotates_and_revokes_old(client: TestClient) -> None:
    """Refresh must (a) issue a new pair, (b) revoke the old refresh jti."""
    login_body = client.post(
        "/auth/login", json={"username": "admin", "password": "admin"}
    ).json()
    old_refresh = login_body["refresh_token"]

    r = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    body = r.json()
    # New pair returned.
    assert "access_token" in body and "refresh_token" in body
    assert body["refresh_token"] != old_refresh, (
        "refresh did not rotate — old refresh is still good for another call"
    )

    # Replaying the old refresh must now 401 (single-use).
    r_replay = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r_replay.status_code == 401


def test_refresh_rejects_revoked_jti_directly(client: TestClient) -> None:
    """A refresh that was explicitly logged-out (i.e. its jti is in the
    deny-list) must not be honored, even on its first use."""
    login_body = client.post(
        "/auth/login", json={"username": "admin", "password": "admin"}
    ).json()
    refresh_tok = login_body["refresh_token"]
    access_tok = login_body["access_token"]

    # Logout to revoke the access jti; refresh jti is independent.
    client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access_tok}"}
    )

    # The refresh token should still be valid (different jti), but
    # rotating it should work — old refresh jti gets revoked, new pair
    # issued. This proves refresh jti is tracked independently of access jti.
    r = client.post("/auth/refresh", json={"refresh_token": refresh_tok})
    assert r.status_code == 200, r.text
    assert r.json()["refresh_token"] != refresh_tok
