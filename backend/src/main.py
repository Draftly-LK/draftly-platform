"""FastAPI application factory and lifespan.

All route routers are registered here. Secrets are never read from the DB or
echoed by health routes.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Windows dev only. psycopg's async mode refuses to run on ProactorEventLoop,
# which is the Windows default, so anything that reaches Postgres through
# `asyncio.run()` — scripts, one-off checks — needs the selector loop.
#
# This does NOT cover uvicorn. Since 0.52 uvicorn builds its loop from a
# factory rather than the policy set here, and on Windows it picks
# ProactorEventLoop unless it is running a subprocess:
#
#     if sys.platform == "win32" and not use_subprocess:
#         return asyncio.ProactorEventLoop
#
# `--reload` (and `--workers`) sets use_subprocess, which is why the documented
# dev command works and a bare `uvicorn src.main:app` returns
# "db": "unreachable" from /health/ready. `--loop asyncio` does not help.
# Deployed Linux hosts are unaffected: the win32 branch never runs there.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.platform.config import get_settings
from src.platform.errors import DraftlyError, draftly_exception_handler, unhandled_exception_handler
from src.platform.observability.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging("DEBUG" if settings.environment == "local" else "INFO")
    log = structlog.get_logger()
    if settings.source_file_storage == "gcs":
        # Build the client and validate the bucket policy now. Otherwise a bad
        # bucket, a missing IAM grant, or an unapproved region first shows up
        # when a lawyer tries to upload. Refusing to start is the right answer.
        from src.bootstrap import build_source_file_storage

        build_source_file_storage()
        log.info("startup.storage_ready", bucket=settings.gcs_bucket)
    log.info("startup", environment=settings.environment)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Draftly API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    # In production, set ALLOWED_ORIGINS to the frontend domain.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:4310"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag", "X-Correlation-Id"],
    )

    # ── Correlation ID middleware ────────────────────────────────────────────
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        bind_request_context(correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-Id"] = correlation_id
            return response
        finally:
            clear_request_context()

    # ── Exception handlers ───────────────────────────────────────────────────
    app.add_exception_handler(DraftlyError, draftly_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Health routes ────────────────────────────────────────────────────────
    @app.get("/health/live", tags=["health"])
    async def health_live() -> JSONResponse:
        """Liveness probe — always 200 if the process is up."""
        return JSONResponse({"status": "ok"})

    @app.get("/health/ready", tags=["health"])
    async def health_ready() -> JSONResponse:
        """Readiness probe — checks DB reachability without leaking credentials."""
        from src.platform.db.session import check_db_ready

        db_ok = await check_db_ready()
        payload = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "unreachable"}
        return JSONResponse(payload, status_code=200 if db_ok else 503)

    # ── API routers (registered from bootstrap) ──────────────────────────────
    from src.bootstrap import register_routers

    register_routers(app)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
