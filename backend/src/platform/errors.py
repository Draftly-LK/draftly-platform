"""Safe HTTP error mapping shared by all Draftly modules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)

_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    400: ("bad_request", "The request could not be processed."),
    401: ("authentication_required", "A valid identity is required."),
    403: ("capability_denied", "You do not have permission to perform this action."),
    404: ("not_found", "The requested resource was not found."),
    405: ("method_not_allowed", "The requested method is not allowed."),
    409: ("conflict", "The request conflicts with the current resource state."),
    412: ("precondition_failed", "The resource has changed since it was read."),
    422: ("domain_rule_refused", "The request was refused by a domain rule."),
    428: ("precondition_required", "A required request precondition is missing."),
    429: ("rate_limit_exceeded", "The request limit has been reached."),
    503: ("dependency_unavailable", "A required dependency is unavailable."),
}


class ApiError(Exception):
    """An expected application failure with a safe public representation."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = dict(details or {})
        self.headers = dict(headers or {})


def correlation_id_for(request: Request) -> str:
    """Return the middleware-issued identifier without trusting request data here."""

    correlation_id = getattr(request.state, "correlation_id", None)
    if isinstance(correlation_id, str):
        return correlation_id
    return f"corr-{uuid4()}"


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the repository-wide error envelope."""

    correlation_id = correlation_id_for(request)
    response_headers = dict(headers or {})
    response_headers["X-Correlation-Id"] = correlation_id
    return JSONResponse(
        status_code=status_code,
        headers=response_headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": dict(details or {}),
                "correlationId": correlation_id,
            }
        },
    )


def internal_error_response(request: Request) -> JSONResponse:
    """Return a generic response that cannot disclose an exception or private value."""

    return error_response(
        request,
        status_code=500,
        code="internal_error",
        message="An unexpected error occurred.",
    )


def _validation_fields(exc: RequestValidationError) -> list[str]:
    fields: list[str] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part not in {"body", "query"}]
        field = ".".join(location)
        if field and field not in fields:
            fields.append(field)
    return fields


def install_exception_handlers(app: FastAPI) -> None:
    """Install stable, privacy-safe mappings for every non-success response."""

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=400,
            code="request_invalid",
            message="The request is invalid.",
            details={"fields": _validation_fields(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        code, message = _HTTP_ERRORS.get(
            exc.status_code,
            ("http_error", "The request could not be completed."),
        )
        return error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=message,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        await logger.aerror(
            "unhandled_application_error",
            exceptionType=type(exc).__name__,
        )
        return internal_error_response(request)
