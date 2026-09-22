"""Pagination envelope and opaque signed cursors (api-conventions.md §2).

No list endpoint returns an unbounded array. ``limit`` is clamped to 100 and
cursors are opaque and signed so a client cannot craft one to walk past its own
tenant scope.
"""

from __future__ import annotations

import base64
import hmac
import json
from hashlib import sha256
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.platform.config import get_settings
from src.platform.errors import DraftlyError

MAX_LIMIT = 100
DEFAULT_LIMIT = 50

T = TypeVar("T")


class InvalidCursorError(DraftlyError):
    code = "invalid_cursor"
    http_status = 400
    message = "The pagination cursor is not valid."


class PageInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    next_cursor: str | None = None
    has_more: bool = False
    limit: int = DEFAULT_LIMIT


class Page(BaseModel, Generic[T]):  # noqa: UP046
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[T]
    page: PageInfo


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if limit < 1:
        return 1
    return min(limit, MAX_LIMIT)


def _signing_key() -> bytes:
    settings = get_settings()
    key = settings.api_cursor_signing_key
    if not key:
        if settings.is_production:
            raise RuntimeError("API_CURSOR_SIGNING_KEY is required in production.")
        key = "local-development-cursor-key"
    return key.encode("utf-8")


def encode_cursor(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(_signing_key(), body, sha256).digest()[:16]
    return base64.urlsafe_b64encode(body + b"." + signature).decode("ascii")


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        # The signature is binary and may itself contain a ``.`` byte. Split
        # by its fixed width instead of searching within untrusted bytes.
        if len(raw) < 18 or raw[-17] != ord("."):
            raise ValueError("invalid cursor framing")
        body, signature = raw[:-17], raw[-16:]
    except Exception:
        raise InvalidCursorError()
    expected = hmac.new(_signing_key(), body, sha256).digest()[:16]
    if not hmac.compare_digest(signature, expected):
        raise InvalidCursorError()
    decoded: dict[str, Any] = json.loads(body.decode("utf-8"))
    return decoded


def paginate_by_id(  # noqa: UP047
    rows: list[T], *, limit: int, cursor: str | None, key: str = "id"
) -> tuple[list[T], PageInfo]:
    """Page an already tenant-filtered, stably ordered list by its tie-breaker id.

    Used by the small catalogue and aggregate reads. Repositories that can push
    the keyset into SQL should do so instead of calling this.
    """
    effective_limit = clamp_limit(limit)
    start = 0
    if cursor:
        after = decode_cursor(cursor).get("after")
        for index, row in enumerate(rows):
            if str(getattr(row, key, None) or _mapping_key(row, key)) == after:
                start = index + 1
                break
        else:
            raise InvalidCursorError()

    window = rows[start : start + effective_limit]
    has_more = start + effective_limit < len(rows)
    next_cursor = None
    if has_more and window:
        last = window[-1]
        last_key = str(getattr(last, key, None) or _mapping_key(last, key))
        next_cursor = encode_cursor({"after": last_key})
    return window, PageInfo(next_cursor=next_cursor, has_more=has_more, limit=effective_limit)


def _mapping_key(row: object, key: str) -> str:
    if isinstance(row, dict):
        return str(row.get(key, ""))
    return ""
