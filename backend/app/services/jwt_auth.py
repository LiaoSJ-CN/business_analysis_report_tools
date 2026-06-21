"""JWT helpers for the auth router.

Single shared secret (HS256). Tokens carry a ``type`` claim so access
and refresh tokens can't be used interchangeably, plus a unique ``jti``
claim (P3 / PY-25) so individual tokens can be revoked via the
``revoked_jti`` table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.config import settings

TokenType = Literal["access", "refresh"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(subject: str, token_type: TokenType, expires_in: timedelta) -> str:
    now = _now()
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_in,
        "type": token_type,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    """Mint a short-lived access token for API requests."""
    return _encode(subject, "access", timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(subject: str) -> str:
    """Mint a longer-lived refresh token used only at /auth/refresh."""
    return _encode(subject, "refresh", timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: TokenType = "access") -> dict[str, Any] | None:
    """Decode and validate a JWT. Returns the payload or ``None`` on any
    failure (bad signature, expired, wrong type, malformed).

    Revocation is intentionally **not** checked here — the caller decides
    whether to consult the deny-list. Keeps this function pure and
    trivial to unit-test without a database.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload
