"""
pipeline-doctor FastAPI application entry point.

Keep this lean. Routes live in routers/, business logic in services/.
This file should read like a configuration file, not a kitchen sink.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import analyze, health, lineage, query

# ---------------------------------------------------------------------------
# Structured logging setup — configure once at import time
# ---------------------------------------------------------------------------


def configure_logging(log_level: str = "INFO") -> None:
    """Set up structlog with a consistent processor chain.

    In development we use the pretty ConsoleRenderer; in production swap to
    JSONRenderer so log aggregators (Datadog, CloudWatch) can parse fields.
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown logic.

    Right now startup just logs. When we add PostgreSQL we'll initialize
    the connection pool here and tear it down on shutdown.
    """
    startup_log = structlog.get_logger("startup")

    try:
        from app.config import get_settings

        settings = get_settings()
        configure_logging(settings.log_level)
        startup_log.info(
            "pipeline_doctor_starting",
            version="0.1.0",
            claude_model=settings.claude_model,
            log_level=settings.log_level,
        )
    except Exception as exc:
        # Don't block startup if settings fail (e.g. running tests without .env)
        configure_logging("INFO")
        startup_log.warning(
            "settings_load_failed",
            error=str(exc),
            note="running with defaults — set .env for production",
        )

    startup_log.info("pipeline_doctor_ready")
    yield

    startup_log.info("pipeline_doctor_shutdown")


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="pipeline-doctor",
    description=(
        "AI-powered dbt pipeline debugger. Upload your manifest.json and "
        "run_results.json to get instant failure analysis, lineage visualization, "
        "and Claude-powered fix suggestions."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow all origins for local development.
# When deploying behind a real domain, tighten this to specific origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router, tags=["health"])
app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
app.include_router(lineage.router, prefix="/lineage", tags=["lineage"])
app.include_router(query.router, prefix="/query", tags=["query"])

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

_error_log = structlog.get_logger("error_handler")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    _error_log.warning(
        "validation_error",
        path=str(request.url),
        error=str(exc),
    )
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _error_log.error(
        "unhandled_exception",
        path=str(request.url),
        exc_type=type(exc).__name__,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
