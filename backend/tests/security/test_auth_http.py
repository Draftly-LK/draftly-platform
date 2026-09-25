"""The real token path over HTTP: HTTPBearer → AuthService → ClerkIdentityAdapter.

Every other API suite overrides ``get_request_context``, so none of them has
ever seen a 401. These do not. The app, the dependency chain and the Clerk
adapter are the production ones; the only substitutions are the adapter's key
source (a key minted for this run instead of Clerk's JWKS endpoint) and
in-memory user stores. TESTING_PLAN.md §8.1, finding F1.
"""

from __future__ import annotations

import re
import time
from typing import Any

import jwt
import pytest
import structlog

from src.api.deps import get_billing_service
from src.main import create_app
from src.modules.auth.domain.models import AccountStatus, Role
from tests.factories.constants import USER_A
from tests.factories.tokens import KEY_ID, TokenMinter
from tests.security.harness import LEEWAY_SECONDS, Harness

SUBJECT_A = "user_synthetic_a"


def _protected_routes() -> list[tuple[str, str]]:
    """Every operation the OpenAPI description marks as needing a bearer token.

    Read from the public schema rather than router internals, so the sweep
    follows the documented surface. Path parameters get a synthetic value.
    """
    spec = create_app().openapi()
    found: list[tuple[str, str]] = []
    for path, operations in spec["paths"].items():
        concrete = re.sub(r"\{[^}]+\}", "synthetic", path)
        for method, operation in operations.items():
            if operation.get("security"):
                found.append((method.upper(), concrete))
    return sorted(found)


PROTECTED_ROUTES = _protected_routes()


def _assert_envelope(body: dict[str, Any], code: str, correlation_id: str | None = None) -> None:
    error = body["error"]
    assert error["code"] == code
    assert error["message"]
    if correlation_id is not None:
        assert error["correlation_id"] == correlation_id


# ── Missing and malformed credentials ────────────────────────────────────────


def test_the_sweep_found_the_api_surface() -> None:
    """Guards the sweep below: an empty route list would pass vacuously."""
    assert len(PROTECTED_ROUTES) > 100
    assert ("GET", "/api/v1/me") in PROTECTED_ROUTES
    assert ("POST", "/api/v1/me/provision") in PROTECTED_ROUTES


@pytest.mark.parametrize(("method", "path"), PROTECTED_ROUTES)
async def test_missing_authorization_header_returns_401(
    harness: Harness, method: str, path: str
) -> None:
    response = await harness.client.request(
        method, path, headers={"X-Correlation-Id": "corr_missing_auth"}
    )

    assert response.status_code == 401
    _assert_envelope(response.json(), "unauthenticated", "corr_missing_auth")
    assert response.headers["X-Correlation-Id"] == "corr_missing_auth"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer", "Bearer ", "Basic c3ludGhldGljOnVzZXI=", "a.bare.token"],
)
async def test_a_header_without_a_bearer_token_returns_401(
    harness: Harness, authorization: str
) -> None:
    response = await harness.client.get("/api/v1/me", headers={"Authorization": authorization})

    assert response.status_code == 401
    _assert_envelope(response.json(), "unauthenticated")


async def test_a_bearer_value_that_is_not_a_jwt_returns_401(harness: Harness) -> None:
    response = await harness.client.get("/api/v1/me", headers=harness.bearer("not-a-jwt"))

    assert response.status_code == 401
    _assert_envelope(response.json(), "identity_validation_failed")


# ── Token validation ─────────────────────────────────────────────────────────


async def test_a_valid_token_for_a_linked_identity_is_admitted(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A)

    response = await harness.client.get(
        "/api/v1/me", headers=harness.bearer(harness.minter.mint(SUBJECT_A))
    )

    assert response.status_code == 200
    assert response.json()["id"] == USER_A


async def test_a_token_expired_beyond_the_leeway_returns_401(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A)
    expired = harness.minter.mint(SUBJECT_A, exp=int(time.time()) - LEEWAY_SECONDS - 60)

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(expired))

    assert response.status_code == 401
    _assert_envelope(response.json(), "identity_validation_failed")


async def test_a_token_expired_within_the_leeway_is_admitted(harness: Harness) -> None:
    """Clock drift between this host and Clerk must not lock users out."""
    await harness.link(SUBJECT_A, USER_A)
    just_expired = harness.minter.mint(SUBJECT_A, exp=int(time.time()) - 20)

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(just_expired))

    assert response.status_code == 200


async def test_a_tampered_signature_returns_401(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A)
    token = harness.minter.mint(SUBJECT_A)
    head, payload, signature = token.split(".")
    tampered = (
        f"{head}.{payload}.{signature[:-6]}{'AAAAAA' if signature[-6:] != 'AAAAAA' else 'BBBBBB'}"
    )

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(tampered))

    assert response.status_code == 401
    _assert_envelope(response.json(), "identity_validation_failed")


async def test_a_token_signed_by_another_key_returns_401(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A)
    forged = TokenMinter().mint(SUBJECT_A)  # same kid, different private key

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(forged))

    assert response.status_code == 401


async def test_a_token_with_an_unknown_key_id_returns_401(harness: Harness) -> None:
    """Covers an unreachable or unknown JWKS entry: refused, never admitted."""
    await harness.link(SUBJECT_A, USER_A)
    token = harness.minter.mint(SUBJECT_A)
    header = jwt.get_unverified_header(token)
    assert header["kid"] == KEY_ID
    unknown = jwt.encode(
        jwt.decode(token, options={"verify_signature": False}),
        "synthetic-hmac-secret-long-enough-for-sha256",
        algorithm="HS256",
        headers={"kid": "synthetic-unknown"},
    )

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(unknown))

    assert response.status_code == 401


async def test_an_alg_none_token_returns_401(harness: Harness) -> None:
    """The classic JWT bypass: an unsigned token claiming no algorithm."""
    await harness.link(SUBJECT_A, USER_A)
    claims = jwt.decode(harness.minter.mint(SUBJECT_A), options={"verify_signature": False})
    unsigned = jwt.encode(claims, "", algorithm="none", headers={"kid": KEY_ID})

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(unsigned))

    assert response.status_code == 401


@pytest.mark.parametrize("azp", ["https://attacker.synthetic.test", None])
async def test_an_untrusted_or_missing_authorized_party_returns_401(
    harness: Harness, azp: str | None
) -> None:
    """The CLERK_AUTHORIZED_PARTY misconfiguration fails closed."""
    await harness.link(SUBJECT_A, USER_A)
    token = harness.minter.mint(SUBJECT_A, azp=azp)

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(token))

    assert response.status_code == 401
    _assert_envelope(response.json(), "identity_validation_failed")


async def test_a_token_from_another_issuer_returns_401(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A)
    token = harness.minter.mint(SUBJECT_A, iss="https://clerk.other.synthetic.test")

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(token))

    assert response.status_code == 401


async def test_a_token_without_a_subject_returns_401(harness: Harness) -> None:
    token = harness.minter.mint("ignored", sub=None)

    response = await harness.client.get("/api/v1/me", headers=harness.bearer(token))

    assert response.status_code == 401


# ── Account state ────────────────────────────────────────────────────────────


async def test_a_valid_token_for_an_unlinked_identity_is_account_pending(
    harness: Harness,
) -> None:
    """Distinct from 401: the token is fine, the account does not exist yet."""
    response = await harness.client.get(
        "/api/v1/me", headers=harness.bearer(harness.minter.mint("user_synthetic_new"))
    )

    assert response.status_code == 403
    _assert_envelope(response.json(), "account_pending")


async def test_a_suspended_account_is_refused(harness: Harness) -> None:
    await harness.link(SUBJECT_A, USER_A, account_status=AccountStatus.SUSPENDED)

    response = await harness.client.get(
        "/api/v1/me", headers=harness.bearer(harness.minter.mint(SUBJECT_A))
    )

    assert response.status_code == 403
    _assert_envelope(response.json(), "account_suspended")


@pytest.mark.parametrize("email_verified", [False, "false", None])
async def test_provisioning_refuses_an_unverified_email(
    harness: Harness, email_verified: object
) -> None:
    token = harness.minter.mint("user_synthetic_unverified", email_verified=email_verified)

    response = await harness.client.post("/api/v1/me/provision", headers=harness.bearer(token))

    assert response.status_code == 422
    _assert_envelope(response.json(), "email_required")


async def test_provisioning_accepts_the_string_form_of_a_verified_email(
    harness: Harness,
) -> None:
    """Clerk's session-token template can deliver ``"true"`` as a string."""
    token = harness.minter.mint("user_synthetic_string_true", email_verified="true")

    class _NoTrialBilling:
        # Provisioning also starts the account's trial, which needs a database
        # this harness forbids; plan grants are covered by the billing tests.
        async def ensure_trial(self, user_id: str) -> None:
            return None

    harness.app.dependency_overrides[get_billing_service] = lambda: _NoTrialBilling()
    response = await harness.client.post("/api/v1/me/provision", headers=harness.bearer(token))

    assert response.status_code == 200
    assert response.json()["role"] == Role.APPROVER.value


# ── Correlation ──────────────────────────────────────────────────────────────


async def test_the_correlation_id_is_echoed_and_logged(harness: Harness) -> None:
    with structlog.testing.capture_logs() as logs:
        response = await harness.client.get(
            "/api/v1/me", headers={"X-Correlation-Id": "corr_synthetic_echo"}
        )

    assert response.headers["X-Correlation-Id"] == "corr_synthetic_echo"
    _assert_envelope(response.json(), "unauthenticated", "corr_synthetic_echo")
    assert any(
        log.get("event") == "draftly_error" and log.get("correlation_id") == "corr_synthetic_echo"
        for log in logs
    )


async def test_one_requests_identity_does_not_leak_into_the_next(harness: Harness) -> None:
    """The request context is bound per request and cleared after it."""
    await harness.link(SUBJECT_A, USER_A)
    first = await harness.client.get(
        "/api/v1/me",
        headers={**harness.bearer(harness.minter.mint(SUBJECT_A)), "X-Correlation-Id": "corr_a"},
    )
    assert first.status_code == 200

    with structlog.testing.capture_logs(
        processors=[structlog.contextvars.merge_contextvars]
    ) as logs:
        second = await harness.client.get("/api/v1/me", headers={"X-Correlation-Id": "corr_b"})

    assert second.status_code == 401
    error_logs = [log for log in logs if log.get("event") == "draftly_error"]
    assert error_logs
    assert all(log.get("user_id") in (None, "") for log in error_logs)
    assert all(log.get("correlation_id") == "corr_b" for log in error_logs)
