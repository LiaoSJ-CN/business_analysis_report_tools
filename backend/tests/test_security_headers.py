"""Tests for security headers middleware (P5 / SEC-5)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


class TestSecurityHeaders:
    def test_headers_present_on_health(self):
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_headers_present_on_auth(self):
        with TestClient(app) as client:
            resp = client.post(
                "/auth/login",
                json={"username": "nobody", "password": "wrong"},
            )
        assert resp.status_code in (401, 429)
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_headers_disabled(self):
        saved = settings.security_headers_enabled
        settings.security_headers_enabled = False
        try:
            with TestClient(app) as client:
                resp = client.get("/health")
            assert resp.status_code == 200
            assert "x-content-type-options" not in resp.headers
        finally:
            settings.security_headers_enabled = saved

    def test_permissions_policy(self):
        with TestClient(app) as client:
            resp = client.get("/health")
        pp = resp.headers.get("permissions-policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp


class TestCorsTightening:
    """P5 (SEC-17): CORS allow-list tightened."""

    def test_preflight_allows_post(self):
        with TestClient(app) as client:
            resp = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
        assert resp.status_code == 200

    def test_trace_not_in_allow_methods(self):
        with TestClient(app) as client:
            resp = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "TRACE",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
        allow = (resp.headers.get("access-control-allow-methods") or "").upper()
        assert "TRACE" not in allow
