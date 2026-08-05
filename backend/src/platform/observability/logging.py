"""Structured logging setup using structlog.

Rules (infrastructure.md §Observability):
- Always bind correlation_id and organisation_id.
- Never log token values, raw JWT content, PII, stack fragments, or SQL text.
- Log at INFO for normal operations; ERROR for unhandled exceptions only.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Call once at application startup."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer()
            if sys.stderr.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_request_context(
    correlation_id: str,
    organisation_id: str = "",
) -> None:
    """Bind per-request keys so every log line in this request carries them."""
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        organisation_id=organisation_id,
    )


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
