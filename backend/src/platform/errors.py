"""Uniform error envelope used across every API route.

Every non-2xx response carries exactly one ErrorEnvelope (api-conventions.md §5).
The `code` field is a stable machine-readable identifier; the frontend switches
on `code`, never on `message`.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ── Wire models ─────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}
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
    return make_error_response(exc, correlation_id=correlation_id)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    import structlog

    log = structlog.get_logger()
    log.error("unhandled_exception", exc_type=type(exc).__name__, exc=str(exc))
    correlation_id = getattr(request.state, "correlation_id", "")
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
