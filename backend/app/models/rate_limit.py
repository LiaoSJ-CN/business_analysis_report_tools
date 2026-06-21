"""Rate-limit event log (P3 / PY-8).

Pre-P3, the login rate limiter held per-IP timestamps in process memory,
which meant each gunicorn worker tracked attempts independently
(10 attempts × N workers = 10N actual login tries). P3 stores each
attempt in this table so all workers share the sliding window.

Schema: ``(key, ts)`` where ``key`` is typically a client IP. ``ts`` is
a Unix timestamp (float seconds) for cheap comparisons in the prune
query. Rows older than the longest configured window are pruned on
each call (and at startup as a safety net).
"""

from __future__ import annotations

from sqlalchemy import Column, Float, Index, Integer, String

from app.database import Base


class RateLimitEvent(Base):
    """One attempted request in a rate-limit window."""

    __tablename__ = "rate_limit_events"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False)
    ts = Column(Float, nullable=False)

    __table_args__ = (
        # Composite index speeds up the per-key prune + count query.
        Index("ix_rate_limit_events_key_ts", "key", "ts"),
    )
