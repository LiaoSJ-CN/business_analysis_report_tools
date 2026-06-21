"""API routes for data exploration (SQL query execution)."""

import logging

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.data_source import DataSource
from app.services.connection import ConnectionError

logger = logging.getLogger(__name__)
from app.services.report_generator import _get_or_create_engine

router = APIRouter(
    prefix="/explorer",
    tags=["explorer"],
    dependencies=[Depends(get_current_user)],
)


class QueryRequest(BaseModel):
    """SQL query request."""

    data_source_id: int
    sql: str


class QueryResponse(BaseModel):
    """SQL query response."""

    success: bool
    columns: list[str]
    rows: list[dict]
    row_count: int
    error: str | None = None


# Dangerous SQL keywords that should not be allowed
FORBIDDEN_KEYWORDS = [
    "DROP",
    "DELETE",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "INSERT",
    "UPDATE",
    "GRANT",
    "REVOKE",
]


def is_safe_sql(sql: str) -> bool:
    """Check if SQL appears safe (SELECT only).

    Strips comments first (the DB ignores them, so what reaches the engine
    is what we must validate), then enforces: must start with SELECT, no
    stacked statements (any ';' is forbidden), no DDL/DML keywords.
    """
    import re
    # Strip block comments (/* ... */, may span newlines) and line
    # comments (-- to end of line). Replace with a space so word
    # boundaries don't merge across the seam.
    s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    s = re.sub(r"--[^\n]*", " ", s)
    upper_sql = s.upper().strip()

    # No stacked statements: reject any ';' anywhere.
    if ";" in upper_sql:
        return False
    # Must start with SELECT.
    if not upper_sql.startswith("SELECT"):
        return False
    # No DDL/DML keywords as whole words (after comment stripping, so a
    # keyword buried in a comment is fine; one in actual code isn't).
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(r"\b" + keyword + r"\b", upper_sql):
            return False
    return True


@router.post("/query", response_model=QueryResponse)
def execute_query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    """Execute a SELECT SQL query against a data source."""
    # Get data source
    data_source = db.query(DataSource).filter(DataSource.id == request.data_source_id).first()
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {request.data_source_id} not found",
        )

    # Security check
    if not is_safe_sql(request.sql):
        return QueryResponse(
            success=False,
            columns=[],
            rows=[],
            row_count=0,
            error="Only SELECT queries are allowed for security reasons",
        )

    # Build connection and execute using pandas
    try:
        engine = _get_or_create_engine(data_source)

        df = pd.read_sql(text(request.sql), engine)

        columns = df.columns.tolist()
        rows = df.to_dict("records")
        row_count = len(rows)

        # Convert types for JSON serialization
        import numpy as np
        cleaned_rows = []
        for row in rows:
            cleaned_row = {}
            for k, v in row.items():
                if pd.isna(v) or v is None:
                    cleaned_row[k] = None
                elif isinstance(v, (np.integer, np.floating)):
                    cleaned_row[k] = v.item()
                else:
                    cleaned_row[k] = v
            cleaned_rows.append(cleaned_row)

        return QueryResponse(
            success=True,
            columns=columns,
            rows=cleaned_rows,
            row_count=row_count,
        )

    except ConnectionError as exc:
        return QueryResponse(
            success=False,
            columns=[],
            rows=[],
            row_count=0,
            error=f"Connection error: {exc}",
        )
    except Exception as exc:
        logger.exception("Unexpected error during query execution for data source %s", request.data_source_id)
        return QueryResponse(
            success=False,
            columns=[],
            rows=[],
            row_count=0,
            error="An unexpected error occurred. Please check the server logs for details.",
        )
