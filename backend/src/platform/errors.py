"""Uniform error envelope used across every API route.

Every non-2xx response carries exactly one ErrorEnvelope (api-conventions.md §5).
The `code` field is a stable machine-readable identifier; the frontend switches
on `code`, never on `message`.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Wire models ─────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# ── Domain exception hierarchy ───────────────────────────────────────────────


class DraftlyError(Exception):
    """Base for all domain and application errors."""

    code: str = "internal_error"
    http_status: int = 500
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, **details: Any) -> None:
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class UnauthenticatedError(DraftlyError):
    code = "unauthenticated"
    http_status = 401
    message = "A valid identity token is required."


class CapabilityDeniedError(DraftlyError):
    code = "capability_denied"
    http_status = 403
    message = "This action requires a capability your role does not grant."


class NotFoundError(DraftlyError):
    """Used for both genuine missing resources and non-member existence hiding."""

    code = "not_found"
    http_status = 404
    message = "The requested resource was not found."


class ConflictError(DraftlyError):
    code = "conflict"
    http_status = 409
    message = "The request conflicts with existing state."


class PreconditionRequiredError(DraftlyError):
    code = "precondition_required"
    http_status = 428
    message = "This mutating request requires an If-Match header."


class PreconditionFailedError(DraftlyError):
    code = "precondition_failed"
    http_status = 412
    message = "The resource version has changed since your last read."


class DomainRuleError(DraftlyError):
    """A well-formed request that domain rules refuse (422)."""

    code = "domain_rule_violated"
    http_status = 422
    message = "A domain rule refused this request."


class StepUpRequiredError(DraftlyError):
    code = "step_up_required"
    http_status = 403
    message = "This action requires recent re-authentication."


class ServiceMisconfiguredError(DraftlyError, RuntimeError):
    """A fail-closed deployment guard refused to build a dependency (503).

    The response carries only the generic class message. ``reason`` names the
    setting or environment at fault and is for the server log alone, so a
    misconfigured deployment never describes its own internals to a caller.
    Still a ``RuntimeError``: outside a request (worker start-up, scripts) the
    guard keeps failing the way it always has.
    """

    code = "service_misconfigured"
    http_status = 503
    message = "The service is temporarily unavailable. Please try again later."

    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason

    def __str__(self) -> str:
        return self.reason


# ── Response helpers ─────────────────────────────────────────────────────────


def make_error_response(
    error: DraftlyError,
    correlation_id: str = "",
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=error.code,
            message=error.message,
            details=getattr(error, "details", {}),
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(
        status_code=error.http_status,
        content=envelope.model_dump(),
    )


# ── FastAPI exception handlers ───────────────────────────────────────────────


async def draftly_exception_handler(
    request: Request,
    exc: DraftlyError,
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "")
    if isinstance(exc, ServiceMisconfiguredError):
        structlog.get_logger().error(
            "service_misconfigured",
            path=request.url.path,
            reason=exc.reason,
            correlation_id=correlation_id,
        )
        return make_error_response(exc, correlation_id=correlation_id)
    structlog.get_logger().warning(
        "draftly_error",
        path=request.url.path,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        correlation_id=correlation_id,
    )
    return make_error_response(exc, correlation_id=correlation_id)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    log = structlog.get_logger()
    correlation_id = getattr(request.state, "correlation_id", "")
    # Exception messages may contain SQL parameter sets, provider payloads, or
    # extracted document values. Log only operational metadata; callers can use
    # the correlation id to locate the failing request safely.
    log.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        path=request.url.path,
        correlation_id=correlation_id,
    )
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code="internal_error",
            message="An unexpected error occurred. Please quote the correlation ID when reporting.",
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content=envelope.model_dump(),
    )
