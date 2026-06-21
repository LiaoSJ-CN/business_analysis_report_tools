"""User model (P3 / SEC-18).

Replaces the pre-P3 shared admin pattern (``settings.admin_password``
compared with ``!=`` in ``routers/auth.py``). The bootstrap admin user
is seeded from settings on first startup; afterwards the bcrypt hash
in this table is the source of truth.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """An application user. Single role (admin) for now; multi-role
    support is out of scope for P3."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt utf-8 hash
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    disabled = Column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging
        return f"<User(id={self.id}, username='{self.username}')>"
