"""``If-Match`` / ``ETag`` translation (api-conventions.md §3).

Two helpers parse ``If-Match``: ``platform.api.conditional`` (billing) and the
``api.deps`` dependency (matter, task, check, draft, party, ingestion). Both
are held to what the convention states: an ETag is the quoted version, a
missing header is 428, and the quoted, bare and weak forms name the same
version. The convention is silent on a malformed header, and the two differ
there (412 against 428), so these only require a precondition error.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from src.api.deps import require_if_match as deps_require_if_match
from src.platform.api.conditional import etag_for_version
from src.platform.api.conditional import require_if_match as api_require_if_match
from src.platform.errors import PreconditionFailedError, PreconditionRequiredError

HELPERS = [
    pytest.param(api_require_if_match, id="platform.api.conditional"),
    pytest.param(deps_require_if_match, id="api.deps"),
]


@pytest.mark.parametrize("version", [1, 7, 1024])
def test_an_etag_is_the_quoted_version(version: int) -> None:
    assert etag_for_version(version) == f'"{version}"'


@pytest.mark.parametrize("parse", HELPERS)
@pytest.mark.parametrize("version", [1, 7, 1024])
def test_an_etag_round_trips_through_if_match(
    parse: Callable[[str | None], int], version: int
) -> None:
    assert parse(etag_for_version(version)) == version


@pytest.mark.parametrize("parse", HELPERS)
@pytest.mark.parametrize("header", ['"7"', "7", 'W/"7"', ' "7" '])
def test_quoted_bare_and_weak_forms_name_the_same_version(
    parse: Callable[[str | None], int], header: str
) -> None:
    assert parse(header) == 7


@pytest.mark.parametrize("parse", HELPERS)
def test_a_missing_if_match_is_428(parse: Callable[[str | None], int]) -> None:
    with pytest.raises(PreconditionRequiredError) as caught:
        parse(None)

    assert caught.value.http_status == 428


@pytest.mark.parametrize("parse", HELPERS)
@pytest.mark.parametrize("header", ["", "   ", '"seven"', "*", '"7", "8"', 'W/"x"'])
def test_a_malformed_if_match_is_a_precondition_error(
    parse: Callable[[str | None], int], header: str
) -> None:
    with pytest.raises((PreconditionRequiredError, PreconditionFailedError)) as caught:
        parse(header)

    assert caught.value.http_status in {412, 428}
