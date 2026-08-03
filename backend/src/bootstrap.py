"""Composition root for technical platform dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from src.platform.config import Settings

ReadinessCheck = Callable[[], Awaitable[bool]]


@dataclass(frozen=True)
class Runtime:
    """Dependencies available to the HTTP application."""

    settings: Settings
    readiness_checks: Mapping[str, ReadinessCheck]


def bootstrap(
    *,
    settings: Settings | None = None,
    readiness_checks: Mapping[str, ReadinessCheck] | None = None,
) -> Runtime:
    """Construct the Phase 0 runtime without external dependencies."""

    return Runtime(
        settings=settings or Settings(),
        readiness_checks=dict(readiness_checks or {}),
    )
