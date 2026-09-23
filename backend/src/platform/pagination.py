"""Cursor pagination primitives shared by every list endpoint (api-conventions.md §2).

Offset pagination is not used; it double-counts under concurrent writes. A
cursor is an opaque, signed encoding of the sort key plus the tie-breaker id,
signed the same way as ``platform.api.pagination`` so a client cannot write a
cursor it was not given.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.platform.api import pagination as signed
from src.platform.errors import DraftlyError

MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 50


class InvalidCursorError(DraftlyError):
    code = "invalid_cursor"
    http_status = 400
    message = "The supplied pagination cursor is not valid."


class InvalidLimitError(DraftlyError):
    code = "invalid_limit"
    http_status = 400
    message = f"limit must be between 1 and {MAX_PAGE_LIMIT}."


@dataclass(frozen=True)
class Cursor:
    """Sort key plus tie-breaker id, as required by api-conventions.md §2."""

    created_at: datetime
    id: str


@dataclass
class Page:
    next_cursor: str | None
    has_more: bool
    limit: int


def normalise_limit(limit: int | None) -> int:
    """Clamp-by-refusal: an out-of-range limit is a 400, never a silent clamp."""
    if limit is None:
        return DEFAULT_PAGE_LIMIT
    if limit < 1 or limit > MAX_PAGE_LIMIT:
        raise InvalidLimitError()
    return limit


def encode_cursor(cursor: Cursor) -> str:
    return signed.encode_cursor(
        {"createdAt": cursor.created_at.astimezone(UTC).isoformat(), "id": cursor.id}
    )


def decode_cursor(value: str | None) -> Cursor | None:
    if not value:
        return None
    try:
        payload = signed.decode_cursor(value)
        return Cursor(
            created_at=datetime.fromisoformat(payload["createdAt"]),
            id=str(payload["id"]),
        )
    except (signed.InvalidCursorError, ValueError, KeyError, TypeError) as exc:
        raise InvalidCursorError() from exc
