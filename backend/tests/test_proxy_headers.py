"""Tests for proxy_headers middleware (P3.5 / PY-12).

Covers X-Forwarded-For parsing: rightmost-untrusted extraction, trusted-only
passthrough, and the no-trusted-proxies fast path.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

# ---------------------------------------------------------------------------
# Unit tests — _rightmost_untrusted
# ---------------------------------------------------------------------------


class TestRightmostUntrusted:
    """Direct unit tests on the parser (no HTTP involved)."""

    def test_typical_chain(self):
        from app.middleware.proxy_headers import _parse_trusted, _rightmost_untrusted

        trusted = _parse_trusted(["10.0.0.1"])
        result = _rightmost_untrusted("1.2.3.4, 10.0.0.1", trusted)
        assert result == "1.2.3.4"

    def test_multiple_proxies(self):
        from app.middleware.proxy_headers import _parse_trusted, _rightmost_untrusted

        trusted = _parse_trusted(["10.0.0.1", "10.0.0.2"])
        result = _rightmost_untrusted("1.2.3.4, 10.0.0.2, 10.0.0.1", trusted)
        assert result == "1.2.3.4"

    def test_cidr_subnet(self):
        from app.middleware.proxy_headers import _parse_trusted, _rightmost_untrusted

        trusted = _parse_trusted(["10.0.0.0/8"])
        result = _rightmost_untrusted("1.2.3.4, 10.1.2.3", trusted)
        assert result == "1.2.3.4"

    def test_all_trusted_returns_none(self):
        from app.middleware.proxy_headers import _parse_trusted, _rightmost_untrusted

        trusted = _parse_trusted(["10.0.0.0/8"])
        result = _rightmost_untrusted("10.0.0.2, 10.0.0.1", trusted)
        assert result is None

    def test_empty_header_returns_none(self):
        from app.middleware.proxy_headers import _parse_trusted, _rightmost_untrusted

        trusted = _parse_trusted(["10.0.0.1"])
        assert _rightmost_untrusted("", trusted) is None

    def test_malformed_hops_skipped(self):
        from app.middleware.proxy_headers import _parse_trusted, _rightmost_untrusted

        trusted = _parse_trusted(["10.0.0.1"])
        result = _rightmost_untrusted("1.2.3.4, garbage, 10.0.0.1", trusted)
        assert result == "1.2.3.4"

    def test_parse_trusted_skips_bad_entries(self):
        from app.middleware.proxy_headers import _parse_trusted

        nets = _parse_trusted(["10.0.0.1", "not-an-ip", "192.168.0.0/16"])
        assert len(nets) == 2


# ---------------------------------------------------------------------------
# Integration tests — middleware on the running app
# ---------------------------------------------------------------------------


class TestMiddlewareIntegration:
    """Round-trip tests that exercise the middleware through TestClient."""

    def test_no_trusted_proxies_passthrough(self):
        """Without trusted proxies, X-Forwarded-For is ignored."""
        saved = list(settings.trusted_proxies)
        settings.trusted_proxies = []
        try:
            with TestClient(app) as c:
                resp = c.get(
                    "/health",
                    headers={"X-Forwarded-For": "1.2.3.4"},
                )
                assert resp.status_code == 200
        finally:
            settings.trusted_proxies = saved

    def test_trusted_proxy_rewrites_client(self):
        """With a trusted proxy, the X-Forwarded-For rightmost untrusted
        IP becomes the effective client."""
        saved = list(settings.trusted_proxies)
        settings.trusted_proxies = ["127.0.0.1"]
        try:
            with TestClient(app) as c:
                resp = c.get(
                    "/health",
                    headers={"X-Forwarded-For": "1.2.3.4, 127.0.0.1"},
                )
                assert resp.status_code == 200
        finally:
            settings.trusted_proxies = saved

    def test_rate_limit_uses_real_ip_with_trusted_proxy(self):
        """When X-Forwarded-For rewrites the client IP, the login rate
        limiter keys on the real client, not the proxy."""
        from app.middleware.rate_limit import RateLimiter
        from app.routers import auth as auth_mod

        saved_trusted = list(settings.trusted_proxies)
        settings.trusted_proxies = ["127.0.0.1"]

        old_limiter = auth_mod._login_limiter
        auth_mod._login_limiter = RateLimiter(max_requests=2, window_seconds=60)

        try:
            with TestClient(app) as c:
                for _ in range(2):
                    resp = c.post(
                        "/auth/login",
                        json={"username": "nobody", "password": "wrong"},
                        headers={"X-Forwarded-For": "1.2.3.4"},
                    )
                    assert resp.status_code == 401

                resp = c.post(
                    "/auth/login",
                    json={"username": "nobody", "password": "wrong"},
                    headers={"X-Forwarded-For": "1.2.3.4"},
                )
                assert resp.status_code == 429
        finally:
            settings.trusted_proxies = saved_trusted
            auth_mod._login_limiter = old_limiter
