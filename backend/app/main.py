"""FastAPI application entry point."""

import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.db_migrations import ensure_columns
from app.models import data_source as _data_source_module  # noqa: F401
from app.models import report as _report_module  # noqa: F401
from app.routers import auth, data_source, explorer, report, scheduler
from app.services.scheduler import get_scheduler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

Base.metadata.create_all(bind=engine)
# Backfill any columns added to models after the table was first created;
# create_all only creates missing tables, never missing columns.
ensure_columns(engine)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    if settings.scheduler_disabled:
        logger.info(
            "Scheduler is DISABLED in this process — "
            "run 'python -m app.scheduler_runner' as a sidecar for "
            "scheduled report generation."
        )
    else:
        logger.info(
            "Scheduler is ENABLED in this process — "
            "for multi-worker deployments set SCHEDULER_DISABLED=true "
            "and run the sidecar separately."
        )
        scheduler = get_scheduler()
        db = SessionLocal()
        try:
            scheduler.sync_with_database(db)
            scheduler.start()
        finally:
            db.close()

    yield

    if not settings.scheduler_disabled:
        get_scheduler().shutdown()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(data_source.router)
app.include_router(report.router)
app.include_router(scheduler.router)
app.include_router(explorer.router)

# Serve locally-bundled Chart.js so generated HTML previews work without external CDN.
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check — includes database connectivity probe."""
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as exc:
        db_status = f"unavailable: {exc}"
        logger.error("Health check: database probe failed — %s", exc)

    overall = "ok" if db_status == "ok" else "unhealthy"
    return {
        "status": overall,
        "database": db_status,
    }
