"""The keyset cursors five repositories hand out follow api-conventions.md §2.

matter, approval, check, document and draft each keep a small cursor codec for
their list queries. They must be signed like every other cursor, and a bad
cursor must be a 400 — not a quiet restart from page one, which leaves a
client with a corrupted cursor paging forever, and not a 500.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

import src.platform.config as settings_module
from src.modules.approval.infrastructure import repository as approval
from src.modules.check.infrastructure import repository as check
from src.modules.document.infrastructure import repository as document
from src.modules.draft.infrastructure import repository as draft
from src.modules.matter.infrastructure import repository as matter
from src.platform.errors import DraftlyError

REPOSITORIES = [
    pytest.param(module, id=module.__name__.split(".")[2])
    for module in (matter, approval, check, document, draft)
]
MOMENT = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_CURSOR_SIGNING_KEY", "synthetic-cursor-key")
    settings_module._settings = None


def _hand_built(payload: object) -> str:
    """The cursor format these repositories used to issue, built by a client."""
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _rejects(decode: Callable[[str], object], cursor: str) -> DraftlyError:
    with pytest.raises(DraftlyError) as caught:
        decode(cursor)
    return caught.value


@pytest.mark.parametrize("repository", REPOSITORIES)
def test_a_cursor_round_trips(repository: ModuleType) -> None:
    cursor = repository._encode_cursor(MOMENT, "rec_synthetic_0042")

    assert repository._decode_cursor(cursor) == (MOMENT, "rec_synthetic_0042")


@pytest.mark.parametrize("repository", REPOSITORIES)
def test_a_hand_built_cursor_is_rejected(repository: ModuleType) -> None:
    forged = _hand_built({"t": MOMENT.isoformat(), "id": "rec_synthetic_other"})

    error = _rejects(repository._decode_cursor, forged)

    assert (error.code, error.http_status) == ("invalid_cursor", 400)


@pytest.mark.parametrize("repository", REPOSITORIES)
@pytest.mark.parametrize(
    "cursor",
    [
        pytest.param("!!!not-base64!!!", id="not-base64"),
        pytest.param(_hand_built(["a", "list"]), id="json-list"),
        pytest.param(_hand_built({"t": "not-a-date", "id": "x"}), id="bad-date"),
    ],
)
def test_a_malformed_cursor_is_a_400_not_page_one_or_a_500(
    repository: ModuleType, cursor: str
) -> None:
    error = _rejects(repository._decode_cursor, cursor)

    assert error.http_status == 400


def test_no_module_writes_its_own_cursor_encoding() -> None:
    """Cursors are encoded in platform/ only, so they stay signed in one place."""
    modules = Path(__file__).resolve().parents[2] / "src" / "modules"
    offenders = [
        str(path.relative_to(modules))
        for path in modules.rglob("*.py")
        if "tests" not in path.parts
        and "urlsafe_b64encode" in path.read_text(encoding="utf-8")
        and path.name != "field_encryption.py"  # key derivation, not a cursor
    ]

    assert offenders == []
