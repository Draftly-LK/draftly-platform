"""Every versioned write demands If-Match (api-conventions.md §3, Rule 5).

A mutating request against a versioned aggregate must send If-Match; a
missing header is 428. The OpenAPI description says which operations take
it, so this sweeps all of them with a signed-in caller and no header, and
with one that names no version. The version check runs before any lookup,
so no resource needs to exist.
"""

from __future__ import annotations

import re

import pytest

from src.main import create_app
from tests.factories.constants import USER_A
from tests.security.harness import Harness

SUBJECT = "user_synthetic_if_match"


def _versioned_writes() -> list[tuple[str, str]]:
    spec = create_app().openapi()
    found = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            headers = {
                p["name"] for p in operation.get("parameters", []) if p.get("in") == "header"
            }
            if method in {"post", "put", "patch", "delete"} and "If-Match" in headers:
                found.append((method.upper(), re.sub(r"\{[^}]+\}", "synthetic", path)))
    return sorted(found)


#: Idempotent by design: If-Match is optional there (notification/api/router.py).
OPTIONAL = {("POST", "/api/v1/notifications/synthetic/read")}
#: These load the obligation before comparing versions, so a made-up id is a
#: 404 first; tests/db/test_obligation_versions.py covers them with a real one.
CHECKED_AFTER_LOOKUP = {
    ("POST", "/api/v1/obligations/synthetic/cancel"),
    ("POST", "/api/v1/obligations/synthetic/complete"),
    ("POST", "/api/v1/obligations/synthetic/confirm"),
}
#: Bodies that pass validation, for routes that read If-Match in the handler.
BODIES = {
    ("POST", "/api/v1/parties/merges"): {
        "sourcePartyId": "pty_synthetic_a",
        "targetPartyId": "pty_synthetic_b",
        "reason": "Synthetic duplicate",
    },
}
VERSIONED_WRITES = [w for w in _versioned_writes() if w not in OPTIONAL | CHECKED_AFTER_LOOKUP]


def test_the_sweep_found_the_versioned_writes() -> None:
    assert len(VERSIONED_WRITES) >= 18
    assert OPTIONAL | CHECKED_AFTER_LOOKUP <= set(_versioned_writes())


@pytest.mark.parametrize(("method", "path"), VERSIONED_WRITES)
async def test_a_versioned_write_without_if_match_is_428(
    harness: Harness, method: str, path: str
) -> None:
    await harness.link(SUBJECT, USER_A)

    response = await harness.client.request(
        method,
        path,
        json=BODIES.get((method, path), {}),
        headers={**harness.signed_in(SUBJECT), "X-Correlation-Id": "corr_im"},
    )

    assert response.status_code == 428, response.text
    error = response.json()["error"]
    assert (error["code"], error["correlation_id"]) == ("precondition_required", "corr_im")


@pytest.mark.parametrize(("method", "path"), VERSIONED_WRITES)
async def test_an_if_match_naming_no_version_is_refused(
    harness: Harness, method: str, path: str
) -> None:
    await harness.link(SUBJECT, USER_A)

    response = await harness.client.request(
        method,
        path,
        json=BODIES.get((method, path), {}),
        headers={**harness.signed_in(SUBJECT), "If-Match": '"latest"'},
    )

    assert response.status_code in {412, 428}, response.text


def _unguarded_notarial_writes() -> list[str]:
    spec = create_app().openapi()
    return sorted(
        f"{method.upper()} {path}"
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if "notarial-register" in operation.get("tags", [])
        and method in {"post", "put", "patch", "delete"}
        and "If-Match"
        not in {p["name"] for p in operation.get("parameters", []) if p.get("in") == "header"}
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "The notarial register's writes take no If-Match, though attestations carry a "
        "version (TESTING_PLAN.md §4.1). Adding it changes the API contract, so it waits "
        "on the register's owners and its clients."
    ),
)
def test_notarial_register_writes_are_version_guarded() -> None:
    assert _unguarded_notarial_writes() == []


def test_the_notarial_check_sees_the_register_writes() -> None:
    """Guards the xfail above against passing on an empty list."""
    assert len(_unguarded_notarial_writes()) >= 5
