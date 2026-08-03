"""Privacy-safe structured logging configuration."""

from __future__ import annotations

import logging
import logging.config
from collections.abc import MutableMapping
from typing import Any

import structlog

_SENSITIVE_KEYS = {
    "address",
    "authorization",
    "body",
    "cookie",
    "email",
    "extractedvalue",
    "nic",
    "passport",
    "password",
    "query",
    "querystring",
    "requestbody",
    "responsebody",
    "secret",
    "setcookie",
    "snippet",
    "text",
    "token",
    "value",
}


def _normalized_key(key: str) -> str:
    return "".join(character for character in key.lower() if character.isalnum())


def drop_sensitive_fields(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Remove private-value fields before an event reaches any renderer."""

    for key in list(event_dict):
        if _normalized_key(key) in _SENSITIVE_KEYS:
            event_dict.pop(key, None)
    return event_dict


def configure_logging(*, log_level: str, service_name: str, environment: str) -> None:
    """Configure stdlib and structlog as single-line JSON output."""

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        drop_sensitive_fields,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "foreign_pre_chain": shared_processors,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.processors.JSONRenderer(),
                    ],
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["default"], "level": log_level},
            "loggers": {
                "httpcore": {
                    "handlers": [],
                    "propagate": False,
                    "disabled": True,
                },
                "httpx": {
                    "handlers": [],
                    "propagate": False,
                    "disabled": True,
                },
                "uvicorn.access": {
                    "handlers": [],
                    "level": log_level,
                    "propagate": False,
                    "disabled": True,
                },
            },
        }
    )

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service=service_name,
        environment=environment,
    )
