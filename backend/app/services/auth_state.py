"""Auth state shared across the auth flow (P3 / PY-25).

Wraps the ``revoked_jti`` table with helpers for:
- ``revoke_jti(db, jti, expires_at)`` — mark a token as invalid.
- ``is_jti_revoked(db, jti) -> bool`` — deny-list check.
- ``prune_expired_revocations(db) -> int`` — drop rows whose underlying
  tokens have already expired (so the table doesn't grow unbounded).

The deny-list is consulted by ``app.deps.get_current_user`` and by
``/auth/refresh`` (to enforce one-time use of refresh tokens).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, cast

from sqlalchemy import CursorResult, delete, exists, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.models.revoked_token import RevokedToken


def revoke_jti(
    db: Session,
    jti: str,
    expires_at: datetime | int | float,
) -> None:
    """Insert *jti* into the deny-list. Idempotent: revoking the same jti
    twice is a no-op (the PK enforces uniqueness, and we skip the INSERT
    if the row already exists).

    ``expires_at`` accepts either a ``datetime`` (already tz-aware, or
    naive which is treated as UTC) or a Unix timestamp (``int``/``float``
    — what PyJWT returns from ``payload['exp']``).
    """
    if not isinstance(jti, str) or not jti:
        raise ValueError("jti must be a non-empty string")
    if isinstance(expires_at, (int, float)):
        expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    elif isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    else:
        raise TypeError(
            f"expires_at must be datetime, int, or float; got {type(expires_at).__name__}"
        )
    existing = db.get(RevokedToken, jti)
    if existing is None:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))
        db.commit()


def is_jti_revoked(db: Session, jti: str) -> bool:
    """True if *jti* is in the deny-list. Cheap PK lookup."""
    return bool(db.scalar(select(exists().where(RevokedToken.jti == jti))))


def prune_expired_revocations(
    session_factory: Callable[[], Session] = SessionLocal,
) -> int:
    """Delete deny-list rows whose ``expires_at`` is in the past — at
    that point the underlying token would have been rejected by the
    signature/exp check anyway, so the row serves no purpose.

    Intended for periodic invocation (e.g. at startup). Returns the
    number of rows removed.
    """
    now = datetime.now(timezone.utc)
    db = session_factory()
    try:
        result = cast(
            CursorResult[Any],
            db.execute(delete(RevokedToken).where(RevokedToken.expires_at < now)),
        )
        db.commit()
        return int(result.rowcount or 0)
    finally:
        db.close()


__all__ = [
    "revoke_jti",
    "is_jti_revoked",
    "prune_expired_revocations",
    "sessionmaker",
]
