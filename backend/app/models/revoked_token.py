"""Revoked-JTI table (P3 / PY-25).

Pre-P3, ``/auth/logout`` was a no-op: clients discarded tokens
themselves, but the JWT remained cryptographically valid until its
``exp`` claim. A leaked access token therefore kept working for up
to 24h (the configured access-token lifetime).

P3 mints every token with a unique ``jti`` claim (see
``app.services.jwt_auth``). On logout, that jti is inserted here.
``app.deps.get_current_user`` consults this table on every request,
so a revoked token is rejected with 401 even though its signature
and exp are still valid.

``expires_at`` is duplicated from the token's ``exp`` claim so a
periodic cleanup can drop entries whose tokens have already expired
naturally — at that point the row serves no purpose.
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from app.database import Base


class RevokedToken(Base):
    """A JWT id (``jti`` claim) that has been explicitly invalidated."""

    __tablename__ = "revoked_jti"

    # uuid4 hex is 32 chars; pad the column for headroom.
    jti = Column(String(64), primary_key=True)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging
        return f"<RevokedToken(jti='{cast(str, self.jti)[:8]}…', expires_at={self.expires_at})>"
