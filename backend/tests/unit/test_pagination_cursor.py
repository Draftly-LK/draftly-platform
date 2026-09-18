"""Pagination cursors are opaque and signed (api-conventions.md §2, finding F4).

Two modules issue cursors: ``platform.api.pagination`` (billing) and
``platform.pagination`` (party, matter agent). The convention binds both, so
both are held to it: a client can round-trip a cursor, and cannot forge,
truncate, edit or replay one across a key rotation.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

import src.platform.config as settings_module
from src.platform import pagination as shared
from src.platform.api import pagination as api
from src.platform.errors import DraftlyError


def _use_signing_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setenv("API_CURSOR_SIGNING_KEY", key)
    settings_module._settings = None


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_signing_key(monkeypatch, "synthetic-cursor-key-one")


# ── platform.api.pagination: dict cursors (billing) ──────────────────────────


def test_api_cursor_round_trips() -> None:
    payload = {"after": "pln_synthetic_0042"}

    assert api.decode_cursor(api.encode_cursor(payload)) == payload


def test_api_cursor_from_a_rotated_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = api.encode_cursor({"after": "pln_synthetic_0042"})
    _use_signing_key(monkeypatch, "synthetic-cursor-key-two")

    with pytest.raises(api.InvalidCursorError):
        api.decode_cursor(cursor)


def test_api_cursor_with_an_edited_body_is_rejected() -> None:
    raw = base64.urlsafe_b64decode(api.encode_cursor({"after": "pln_a"}))
    body, signature = raw.rsplit(b".", 1)
    edited = body.replace(b"pln_a", b"pln_b")

    with pytest.raises(api.InvalidCursorError):
        api.decode_cursor(base64.urlsafe_b64encode(edited + b"." + signature).decode())


def test_api_cursor_forged_without_the_key_is_rejected() -> None:
    body = json.dumps({"after": "pln_synthetic_other_tenant"}).encode()
    forged = base64.urlsafe_b64encode(body + b"." + b"0" * 16).decode()

    with pytest.raises(api.InvalidCursorError):
        api.decode_cursor(forged)


@pytest.mark.parametrize(
    "mangle",
    [
        pytest.param(lambda cursor: cursor[: len(cursor) // 2], id="truncated"),
        pytest.param(lambda cursor: "", id="empty"),
        pytest.param(lambda cursor: "!!!not-base64!!!", id="not-base64"),
        pytest.param(lambda cursor: "é" + cursor, id="non-ascii"),
        pytest.param(
            lambda cursor: base64.urlsafe_b64encode(b"no-signature-separator").decode(),
            id="no-signature",
        ),
    ],
)
def test_api_cursor_that_is_malformed_is_a_400_not_a_500(
    mangle: Callable[[str], str],
) -> None:
    with pytest.raises(api.InvalidCursorError) as caught:
        api.decode_cursor(mangle(api.encode_cursor({"after": "pln_a"})))

    assert caught.value.http_status == 400


def test_api_cursors_refuse_to_sign_with_the_dev_key_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    _use_signing_key(monkeypatch, "")

    with pytest.raises(RuntimeError, match="API_CURSOR_SIGNING_KEY"):
        api.encode_cursor({"after": "pln_a"})


@pytest.mark.parametrize(
    ("requested", "effective"),
    [(None, api.DEFAULT_LIMIT), (0, 1), (-1, 1), (1, 1), (100, 100), (101, 100)],
)
def test_api_limit_is_clamped(requested: int | None, effective: int) -> None:
    assert api.clamp_limit(requested) == effective


def test_paging_by_id_is_stable_when_a_row_lands_after_page_one() -> None:
    rows: list[dict[str, Any]] = [{"id": f"row_{n:02d}"} for n in range(1, 6)]
    first, info = api.paginate_by_id(rows, limit=2, cursor=None)

    rows.append({"id": "row_06"})
    second, _ = api.paginate_by_id(rows, limit=2, cursor=info.next_cursor)

    assert [row["id"] for row in first] == ["row_01", "row_02"]
    assert [row["id"] for row in second] == ["row_03", "row_04"]


def test_paging_by_id_rejects_a_cursor_for_a_row_that_is_not_there() -> None:
    rows = [{"id": "row_01"}, {"id": "row_02"}]

    with pytest.raises(api.InvalidCursorError):
        api.paginate_by_id(rows, limit=1, cursor=api.encode_cursor({"after": "row_99"}))


# ── platform.pagination: (created_at, id) cursors (party, matter agent) ─────

MOMENT = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)


def _unsigned(payload: dict[str, Any]) -> str:
    """What a client can build by hand from a cursor it has seen."""
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def test_shared_cursor_round_trips() -> None:
    cursor = shared.Cursor(created_at=MOMENT, id="pty_synthetic_0042")

    assert shared.decode_cursor(shared.encode_cursor(cursor)) == cursor


def test_shared_cursor_built_by_hand_is_rejected() -> None:
    """A client that decodes one cursor must not be able to write another."""
    forged = _unsigned({"createdAt": MOMENT.isoformat(), "id": "pty_synthetic_other"})

    with pytest.raises(shared.InvalidCursorError):
        shared.decode_cursor(forged)


def test_shared_cursor_from_a_rotated_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = shared.encode_cursor(shared.Cursor(created_at=MOMENT, id="pty_a"))
    _use_signing_key(monkeypatch, "synthetic-cursor-key-two")

    with pytest.raises(shared.InvalidCursorError):
        shared.decode_cursor(cursor)


@pytest.mark.parametrize("value", ["!!!not-base64!!!", "é", "e30", _unsigned({"id": 1})])
def test_shared_cursor_that_is_malformed_is_a_400_not_a_500(value: str) -> None:
    with pytest.raises(DraftlyError) as caught:
        shared.decode_cursor(value)

    assert caught.value.code == "invalid_cursor"
    assert caught.value.http_status == 400


@pytest.mark.parametrize("value", [None, ""])
def test_no_shared_cursor_means_the_first_page(value: str | None) -> None:
    assert shared.decode_cursor(value) is None


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_shared_limit_out_of_range_is_refused_not_clamped(limit: int) -> None:
    with pytest.raises(shared.InvalidLimitError):
        shared.normalise_limit(limit)


@pytest.mark.parametrize(
    ("requested", "effective"), [(None, shared.DEFAULT_PAGE_LIMIT), (1, 1), (100, 100)]
)
def test_shared_limit_in_range_is_kept(requested: int | None, effective: int) -> None:
    assert shared.normalise_limit(requested) == effective
