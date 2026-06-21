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
from app.services.report_generator import _get_or_create_engine
from app.services.sql_validator import UnsafeSQLError, validate_select_only

logger = logging.getLogger(__name__)

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

    # Security check — all validation lives in sql_validator now.
    # We keep returning 200 + success=False (not 422) so the existing
    # frontend explorer code path is unchanged.
    try:
        validate_select_only(request.sql)
    except UnsafeSQLError as exc:
        return QueryResponse(
            success=False,
            columns=[],
            rows=[],
            row_count=0,
            error=f"Only SELECT queries are allowed: {exc}",
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
