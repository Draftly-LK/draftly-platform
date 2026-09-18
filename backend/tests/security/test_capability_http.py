"""Roles, platform grants and step-up, enforced over HTTP (TESTING_PLAN.md §8.2).

The capability map is well tested in isolation. These check the wired half:
that the wrong role gets a 403 envelope from the real route, and that the
right one is let past the guard.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

import src.platform.config as settings_module
from src.modules.auth.domain.models import Role
from tests.factories.constants import USER_A, USER_B
from tests.security.harness import Harness

SUBJECT_A = "user_synthetic_a"
SUBJECT_B = "user_synthetic_b"

PLAN_BODY: dict[str, Any] = {
    "code": "synthetic-plan",
    "family": "synthetic",
    "name": "Synthetic plan",
    "billingInterval": "monthly",
    "currency": "LKR",
    "priceMinorUnits": 100000,
}

ADMIN_ROUTES = [
    ("POST", "/api/v1/admin/plans", PLAN_BODY),
    ("POST", "/api/v1/admin/plans/pv_synthetic/activate", None),
    (
        "POST",
        "/api/v1/admin/subscriptions/sub_synthetic/grant-trial",
        {"planVersionId": "pv_synthetic", "trialDays": 14},
    ),
]


def _error_code(response: Any) -> str:
    return str(response.json()["error"]["code"])


# ── Platform administration ─────────────────────────────────────────────────


def _platform_admins(monkeypatch: pytest.MonkeyPatch, user_ids: str) -> None:
    """Set the staff allowlist and drop cached settings so the app re-reads it.

    ``create_app`` reads settings when the harness builds the app, so a change
    made afterwards is invisible until the cache is cleared.
    """
    monkeypatch.setenv("PLATFORM_ADMIN_USER_IDS", user_ids)
    settings_module._settings = None


@pytest.fixture
def no_platform_admins(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    _platform_admins(monkeypatch, "")


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ROUTES)
async def test_no_account_role_reaches_plan_administration(
    harness: Harness,
    no_platform_admins: None,
    role: Role,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    """``platform.administer`` is Draftly staff, not a customer's administrator."""
    await harness.link(SUBJECT_A, USER_A, role=role)

    response = await harness.client.request(
        method, path, json=body, headers=harness.signed_in(SUBJECT_A)
    )

    assert response.status_code == 403
    assert _error_code(response) == "capability_denied"


async def test_a_platform_grant_lets_the_caller_past_the_admin_guard(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the guard, the plan's own validation answers — not a 403."""
    _platform_admins(monkeypatch, USER_A)
    await harness.link(SUBJECT_A, USER_A, role=Role.REVIEWER)

    response = await harness.client.post(
        "/api/v1/admin/plans",
        json={**PLAN_BODY, "priceMinorUnits": -1},
        headers=harness.signed_in(SUBJECT_A),
    )

    assert response.status_code == 422
    assert _error_code(response) == "invalid_plan_input"


async def test_the_grant_is_per_user_not_per_role(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    _platform_admins(monkeypatch, USER_B)
    await harness.link(SUBJECT_A, USER_A, role=Role.ADMINISTRATOR)

    response = await harness.client.post(
        "/api/v1/admin/plans", json=PLAN_BODY, headers=harness.signed_in(SUBJECT_A)
    )

    assert response.status_code == 403


# ── Role-gated capabilities ─────────────────────────────────────────────────


async def test_a_role_without_party_record_identity_cannot_create_a_party(
    harness: Harness,
) -> None:
    await harness.link(SUBJECT_A, USER_A, role=Role.MAINTAINER)

    response = await harness.client.post(
        "/api/v1/parties",
        json={"partyKind": "natural-person", "displayName": "Synthetic Party (synthetic)"},
        headers=harness.signed_in(SUBJECT_A),
    )

    assert response.status_code == 403
    assert _error_code(response) == "capability_denied"


@pytest.mark.parametrize("role", [Role.REVIEWER, Role.MAINTAINER])
async def test_a_role_without_user_role_set_cannot_change_roles(
    harness: Harness, role: Role
) -> None:
    await harness.link(SUBJECT_A, USER_A, role=role)

    response = await harness.client.patch(
        "/api/v1/me/role",
        json={"role": "approver"},
        headers={
            **harness.signed_in(SUBJECT_A),
            "X-Step-Up-Token": harness.minter.mint(SUBJECT_A, auth_time=int(time.time())),
        },
    )

    assert response.status_code == 403
    assert _error_code(response) == "capability_denied"


# ── Step-up on role changes ─────────────────────────────────────────────────


def _step_up(harness: Harness, subject: str, **claims: Any) -> dict[str, str]:
    claims.setdefault("auth_time", int(time.time()))
    return {"X-Step-Up-Token": harness.minter.mint(subject, **claims)}


async def test_a_role_change_without_step_up_is_refused(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A, role=Role.APPROVER)

    response = await harness.client.patch(
        "/api/v1/me/role", json={"role": "administrator"}, headers=harness.signed_in(SUBJECT_A)
    )

    assert response.status_code == 403
    assert _error_code(response) == "step_up_required"


@pytest.mark.parametrize(
    "step_up",
    [
        pytest.param({"auth_time": None}, id="no-auth-time"),
        pytest.param({"auth_time": int(time.time()) - 3600}, id="session-too-old"),
        pytest.param({"exp": int(time.time()) - 3600}, id="expired-token"),
    ],
)
async def test_a_stale_or_unverifiable_step_up_is_refused(
    harness: Harness, step_up: dict[str, Any]
) -> None:
    await harness.link(SUBJECT_A, USER_A, role=Role.APPROVER)

    response = await harness.client.patch(
        "/api/v1/me/role",
        json={"role": "administrator"},
        headers={**harness.signed_in(SUBJECT_A), **_step_up(harness, SUBJECT_A, **step_up)},
    )

    assert response.status_code == 403
    assert _error_code(response) == "step_up_required"


async def test_a_step_up_token_for_another_user_is_refused(harness: Harness) -> None:
    """A fresh session proves who re-authenticated, so it must be the actor."""
    await harness.link(SUBJECT_A, USER_A, role=Role.APPROVER)
    await harness.link(SUBJECT_B, USER_B, role=Role.APPROVER)

    response = await harness.client.patch(
        "/api/v1/me/role",
        json={"role": "administrator"},
        headers={**harness.signed_in(SUBJECT_A), **_step_up(harness, SUBJECT_B)},
    )

    assert response.status_code == 403
    assert _error_code(response) == "step_up_required"


async def test_a_fresh_step_up_changes_the_actors_own_role(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A, role=Role.APPROVER)

    response = await harness.client.patch(
        "/api/v1/me/role",
        json={"role": "administrator"},
        headers={**harness.signed_in(SUBJECT_A), **_step_up(harness, SUBJECT_A)},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "administrator"
    stored = await harness.users.get(USER_A)
    assert stored is not None and stored.role is Role.ADMINISTRATOR


async def test_a_role_change_that_would_lock_the_actor_out_is_refused(
    harness: Harness,
) -> None:
    """Maintainer lacks user.role.set, so the actor could never change back."""
    await harness.link(SUBJECT_A, USER_A, role=Role.APPROVER)

    response = await harness.client.patch(
        "/api/v1/me/role",
        json={"role": "maintainer"},
        headers={**harness.signed_in(SUBJECT_A), **_step_up(harness, SUBJECT_A)},
    )

    assert response.status_code == 409
    assert _error_code(response) == "role_lockout"
