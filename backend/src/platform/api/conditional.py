"""``If-Match`` / ``ETag`` translation for versioned aggregates.

api-conventions.md §3: the wire format for optimistic concurrency is a
conditional request. Domain and application layers keep taking
``expected_version`` as a parameter; the router translates the header.
"""

from __future__ import annotations

from src.platform.errors import PreconditionFailedError, PreconditionRequiredError


def etag_for_version(version: int) -> str:
    return f'"{version}"'


def require_if_match(if_match: str | None) -> int:
    """Return the expected version from an ``If-Match`` header.

    A missing header is 428; an unparsable one is 412 rather than 400 because
    the caller did send a precondition and it does not match any version.
    """
    if if_match is None or not if_match.strip():
        raise PreconditionRequiredError()
    candidate = if_match.strip()
    if candidate.startswith("W/"):
        candidate = candidate[2:]
    candidate = candidate.strip('"')
    try:
        return int(candidate)
    except ValueError:
        raise PreconditionFailedError()
