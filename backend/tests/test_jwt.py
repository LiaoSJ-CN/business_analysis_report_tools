"""Tests for JWT helpers (P3 / PY-25: jti claim added for revocation)."""

from __future__ import annotations

from app.services.jwt_auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_jwt_module_exists() -> None:
    """Smoke: importing the module succeeds."""
    assert callable(create_access_token)
    assert callable(create_refresh_token)
    assert callable(decode_token)


def test_access_token_includes_jti() -> None:
    """Every minted access token must carry a unique jti claim so it can be
    individually revoked by the deny-list (P3 / PY-25)."""
    token = create_access_token("alice")
    payload = decode_token(token, expected_type="access")
    assert payload is not None
    assert "jti" in payload
    assert isinstance(payload["jti"], str)
    assert len(payload["jti"]) >= 16  # uuid4 hex is 32 chars


def test_refresh_token_includes_jti() -> None:
    token = create_refresh_token("alice")
    payload = decode_token(token, expected_type="refresh")
    assert payload is not None
    assert "jti" in payload


def test_each_minted_token_has_unique_jti() -> None:
    """Two tokens minted back-to-back must carry distinct jti values —
    otherwise revoking one would invalidate both, which is not what
    callers expect."""
    a = create_access_token("alice")
    b = create_access_token("alice")
    pa = decode_token(a, expected_type="access")
    pb = decode_token(b, expected_type="access")
    assert pa is not None and pb is not None
    assert pa["jti"] != pb["jti"]


def test_decode_token_returns_none_for_invalid_token() -> None:
    """decode_token returns None for any failure (bad sig, expired, etc)."""
    assert decode_token("not.a.jwt") is None
    assert decode_token("") is None


def test_decode_token_enforces_type() -> None:
    """An access token cannot be decoded with expected_type='refresh'."""
    access = create_access_token("alice")
    assert decode_token(access, expected_type="refresh") is None
    assert decode_token(access, expected_type="access") is not None
