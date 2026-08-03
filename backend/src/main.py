"""FastAPI application factory for Draftly."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from src.bootstrap import ReadinessCheck, bootstrap
from src.platform.config import Settings
from src.platform.errors import ApiError, install_exception_handlers, internal_error_response
from src.platform.observability.logging import configure_logging

_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _correlation_id(candidate: str | None) -> str:
    if candidate is not None and _CORRELATION_ID_PATTERN.fullmatch(candidate):
        return candidate
    return f"corr-{uuid4()}"


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "unmatched"


def create_app(
    *,
    settings: Settings | None = None,
    readiness_checks: Mapping[str, ReadinessCheck] | None = None,
) -> FastAPI:
    """Create an isolated application with explicitly supplied dependencies."""

    runtime = bootstrap(settings=settings, readiness_checks=readiness_checks)
    configure_logging(
        log_level=runtime.settings.log_level,
        service_name=runtime.settings.service_name,
        environment=runtime.settings.environment,
    )
    logger = structlog.get_logger(__name__)

    application = FastAPI(
        title="Draftly API",
        version="0.1.0",
    )
    install_exception_handlers(application)

    @application.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = _correlation_id(request.headers.get("X-Correlation-Id"))
        request.state.correlation_id = correlation_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            service=runtime.settings.service_name,
            environment=runtime.settings.environment,
            correlationId=correlation_id,
        )
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            await logger.aerror(
                "unhandled_application_error",
                exceptionType=type(exc).__name__,
            )
            response = internal_error_response(request)

        response.headers["X-Correlation-Id"] = correlation_id
        await logger.ainfo(
            "http_request_completed",
            method=request.method,
            route=_route_template(request),
            status=response.status_code,
            durationMs=round((time.perf_counter() - started_at) * 1000, 2),
        )
        structlog.contextvars.clear_contextvars()
        return response

    @application.get("/health/live", include_in_schema=True)
    async def health_live() -> dict[str, str]:
        return {"status": "alive"}

    @application.get("/health/ready", include_in_schema=True)
    async def health_ready() -> dict[str, object]:
        states: dict[str, str] = {}
        for name in sorted(runtime.readiness_checks):
            check = runtime.readiness_checks[name]
            try:
                available = await check()
            except Exception:
                available = False
            states[name] = "available" if available else "unavailable"

        if any(state == "unavailable" for state in states.values()):
            raise ApiError(
                status_code=503,
                code="dependency_unavailable",
                message="One or more required dependencies are unavailable.",
                details={"checks": states},
            )
        return {"status": "ready", "checks": states}

    return application


app = create_app()
