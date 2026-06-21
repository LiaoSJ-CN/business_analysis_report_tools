"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.auth_state import is_jti_revoked
from app.services.jwt_auth import decode_token

# auto_error=False so a missing Authorization header doesn't itself 401;
# the call site raises the final 401 with a clear message.
_bearer = HTTPBearer(auto_error=False)


def _credentials_from_request(request: Request) -> HTTPAuthorizationCredentials | None:
    """Read the bearer token from the cookie (P3 / SEC-6) or the
    ``Authorization`` header (CLI / curl fallback).

    Order: cookie first, then header. The frontend sends the cookie
    automatically; ``Authorization: Bearer`` is only useful for direct
    API calls.
    """
    cookie = request.cookies.get(settings.access_cookie_name)
    if cookie:
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=cookie)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:])
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    """Return the authenticated username from the cookie or the
    ``Authorization`` header.

    Raises 401 if neither is present or the token is invalid. The
    previous ``?token=`` query-param fallback (kept for the old
    iframe-loaded preview) was removed when ReportPreview switched to
    fetching the HTML via Authorization header and pointing the iframe
    at a blob: URL.

    P3 (PY-25) additions: the jti claim is checked against the
    ``revoked_jti`` deny-list on every request, so a logged-out token
    is rejected even if its signature and exp are still valid.
    """
    creds = _credentials_from_request(request)
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_token(creds.credentials, expected_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    jti = payload.get("jti")
    if jti and is_jti_revoked(db, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    return str(payload["sub"])


def get_current_token(request: Request) -> str:
    """Return the raw bearer token from the cookie or the ``Authorization`` header.

    Used by ``/auth/logout`` to read the token's jti for revocation.
    Raises 401 if neither is present — logout requires auth, since
    there's no token to revoke without one.
    """
    creds = _credentials_from_request(request)
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return creds.credentials


def get_refresh_token_from_request(
    request: Request, body_token: str | None = None
) -> str | None:
    """Read the refresh token from the request body first, then the cookie.

    Body takes precedence so a caller that explicitly POSTs
    ``{"refresh_token": "..."}`` (CLI / curl, body-only tests) always
    gets the token they asked for — even if the browser happens to
    also have a (possibly stale) cookie on the same request. When no
    body is provided, fall back to the HttpOnly cookie the SPA
    receives on login.

    Returns None if neither is present so the caller can return 400
    instead of 401 (the client is structurally wrong, not unauth'd).
    """
    if body_token:
        return body_token
    return request.cookies.get(settings.refresh_cookie_name)
