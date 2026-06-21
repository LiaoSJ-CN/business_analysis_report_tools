"""Tests for the DB-backed sliding-window rate limiter (P3 / PY-8).

Pre-P3, ``app.middleware.rate_limit.RateLimiter`` held counters in
process memory, which meant each gunicorn worker tracked attempts
independently — 10 attempts × N workers = 10N actual login tries.
P3 replaces the in-memory dict with a SQLAlchemy table so all workers
share state.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.middleware.rate_limit import RateLimiter
from app.models.rate_limit import RateLimitEvent


@pytest.fixture(autouse=True)
def _clear_rate_limit_table():
    """Truncate the rate-limit table between tests so buckets don't leak."""
    db: Session = SessionLocal()
    try:
        db.query(RateLimitEvent).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(RateLimitEvent).delete()
        db.commit()
    finally:
        db.close()


def test_first_call_is_not_limited() -> None:
    rl = RateLimiter(max_requests=3, window_seconds=60)
    assert rl.is_rate_limited("ip-1") is False


def test_under_limit_is_not_limited() -> None:
    rl = RateLimiter(max_requests=3, window_seconds=60)
    assert rl.is_rate_limited("ip-1") is False
    assert rl.is_rate_limited("ip-1") is False
    # 3rd call: at limit but not over → still allowed (the call itself counts)
    assert rl.is_rate_limited("ip-1") is False


def test_over_limit_is_limited() -> None:
    rl = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        assert rl.is_rate_limited("ip-1") is False
    # 4th call exceeds limit
    assert rl.is_rate_limited("ip-1") is True
    # Subsequent calls also blocked
    assert rl.is_rate_limited("ip-1") is True


def test_different_keys_have_independent_buckets() -> None:
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.is_rate_limited("ip-a") is False
    assert rl.is_rate_limited("ip-a") is False
    assert rl.is_rate_limited("ip-a") is True  # over limit
    # ip-b is unaffected
    assert rl.is_rate_limited("ip-b") is False
    assert rl.is_rate_limited("ip-b") is False
    assert rl.is_rate_limited("ip-b") is True


def test_window_expiry_resets_count() -> None:
    """With a 1s window, after 1s the bucket should be empty again."""
    rl = RateLimiter(max_requests=2, window_seconds=1)
    assert rl.is_rate_limited("ip-x") is False
    assert rl.is_rate_limited("ip-x") is False
    assert rl.is_rate_limited("ip-x") is True  # over limit
    # Sleep past the window
    time.sleep(1.2)
    assert rl.is_rate_limited("ip-x") is False, (
        "events older than the window should be pruned on the next call"
    )


def test_shared_state_across_instances() -> None:
    """Two RateLimiter instances backed by the same DB see the same state.

    This is the actual fix for PY-8: with the in-memory implementation,
    each instance would have its own dict. The DB-backed version shares
    a table, so multi-worker deployments enforce the global limit.
    """
    rl_a = RateLimiter(max_requests=3, window_seconds=60)
    rl_b = RateLimiter(max_requests=3, window_seconds=60)
    # rl_a consumes the budget
    assert rl_a.is_rate_limited("ip-shared") is False
    assert rl_a.is_rate_limited("ip-shared") is False
    assert rl_a.is_rate_limited("ip-shared") is False
    # rl_b sees rl_a's writes — over limit from the global view
    assert rl_b.is_rate_limited("ip-shared") is True
