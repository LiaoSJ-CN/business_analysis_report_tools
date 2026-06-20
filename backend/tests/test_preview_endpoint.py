"""/reports/{id}/preview endpoint contract.

Drives the endpoint through the FastAPI router (not the service
directly) so a regression in router wiring — e.g. someone refactors
``preview_report`` and forgets to pass ``request.base_url`` — is caught.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.report import Report


@pytest.fixture
def active_report() -> Report:
    db: Session = SessionLocal()
    try:
        report = db.query(Report).filter(Report.is_active.is_(True)).first()
        if not report:
            pytest.skip("no active reports; run seed_reports.py to populate app.db")
        return report
    finally:
        db.close()


def test_preview_requires_auth(client: TestClient, active_report: Report) -> None:
    r = client.get(f"/reports/{active_report.id}/preview", params={"format": "html"})
    assert r.status_code == 401


def test_preview_rejects_query_param_token_fallback(
    client: TestClient, active_report: Report, auth_headers: dict
) -> None:
    """The ?token= query-param path was removed — must stay 401."""
    token = auth_headers["Authorization"].split(" ", 1)[1]
    r = client.get(
        f"/reports/{active_report.id}/preview",
        params={"format": "html", "token": token},
    )
    assert r.status_code == 401, (
        f"?token= fallback must be rejected; got {r.status_code}. "
        "The query-param auth path was removed and must not be reintroduced."
    )


def test_preview_returns_html_with_base_href(
    client: TestClient, active_report: Report, auth_headers: dict
) -> None:
    r = client.get(
        f"/reports/{active_report.id}/preview",
        params={"format": "html"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    ctype = r.headers.get("content-type", "")
    assert "text/html" in ctype, f"expected text/html, got {ctype!r}"
    assert "<base href=" in r.text, (
        "preview HTML missing <base href=...>; the blob-URL iframe "
        "needs this to resolve /static/chart.umd.min.js to the backend"
    )
    assert "/static/chart.umd.min.js" in r.text
    assert "<title>" in r.text


def test_preview_unknown_report_is_404(client: TestClient, auth_headers: dict) -> None:
    r = client.get("/reports/9999999/preview", headers=auth_headers)
    assert r.status_code == 404
