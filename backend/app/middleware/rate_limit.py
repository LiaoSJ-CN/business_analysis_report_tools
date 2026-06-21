"""Simple in-memory rate limiter for login endpoints.

Zero-dependency sliding-window implementation.  Counters are per-key
(typically IP address) and reset on application restart.  For multi-worker
deployments you would replace this with a Redis-backed implementation, but
the in-memory version provides meaningful brute-force protection for
single-process and development use.

Usage::

    from app.config import settings
    from app.middleware.rate_limit import RateLimiter

    login_limiter = RateLimiter(
        max_requests=settings.login_rate_limit,
        window_seconds=60,
    )

    @router.post("/login")
    def login(req: LoginRequest, request: Request):
        if login_limiter.is_rate_limited(request.client.host):
            raise HTTPException(429, "Too many login attempts")
        ...
"""

from collections import defaultdict
from time import time


class RateLimiter:
    """Sliding-window rate limiter keyed on an arbitrary string."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def is_rate_limited(self, key: str) -> bool:
        """Return True if *key* has exceeded the per-window limit.

        Calling this method also records the attempt — it acts as a
        combined check-and-record, so it must only be called **once** per
        request.
        """
        now = time()
        floor = now - self._window
        bucket = self._attempts[key]
        # Prune timestamps that have fallen out of the window.
        bucket[:] = (t for t in bucket if t > floor)
        if len(bucket) >= self._max_requests:
            return True
        bucket.append(now)
        return False
