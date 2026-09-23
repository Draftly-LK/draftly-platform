"""Shared FastAPI dependencies (src/api/deps.py): the perimeter every route passes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

import src.platform.config as config
from src.api import deps
from src.modules.auth.application.auth_service import AuthService
from src.modules.auth.domain.models import Role
from src.modules.billing.application.billing_service import BillingService
from src.modules.notarial_register.application.notarial_register_service import (
    NotarialRegisterService,
)
from src.modules.notification.application.notification_service import NotificationService
from src.modules.obligations.application.obligations_service import ObligationsService
from src.modules.party.application.party_service import PartyService
from src.modules.party.infrastructure.matter_access_stub import (
    MatterServiceUnavailableError,
    StubMatterAccessAdapter,
)
from src.platform.errors import (
    PreconditionRequiredError,
    ServiceMisconfiguredError,
    UnauthenticatedError,
)
from src.platform.request_context import RequestContext

SESSION = cast(AsyncSession, object())


def _request(**state: Any) -> Request:
    return cast(Request, SimpleNamespace(state=SimpleNamespace(**state)))


# ── Bearer token ────────────────────────────────────────────────────────────


def test_a_request_without_credentials_is_unauthenticated() -> None:
    with pytest.raises(UnauthenticatedError) as excinfo:
        deps.get_bearer_token(None)
    assert excinfo.value.http_status == 401
    assert excinfo.value.code == "unauthenticated"


def test_the_raw_bearer_token_is_passed_through_unchanged() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok.synthetic")
    assert deps.get_bearer_token(credentials) == "tok.synthetic"


# ── Correlation id ──────────────────────────────────────────────────────────


def test_the_middleware_correlation_id_is_reused() -> None:
    assert deps.get_correlation_id(_request(correlation_id="corr-1")) == "corr-1"


def test_a_missing_correlation_id_is_generated_not_left_blank() -> None:
    first = deps.get_correlation_id(_request())
    second = deps.get_correlation_id(_request(correlation_id=""))
    assert first and second and first != second
    assert len(first) == 36


# ── If-Match ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("header", "version"),
    [('"3"', 3), ("3", 3), ('W/"12"', 12), ('  "7"  ', 7)],
)
def test_if_match_is_parsed_into_the_expected_version(header: str, version: int) -> None:
    assert deps.require_if_match(header) == version


def test_a_mutation_without_if_match_is_428() -> None:
    with pytest.raises(PreconditionRequiredError) as excinfo:
        deps.require_if_match(None)
    assert excinfo.value.http_status == 428


@pytest.mark.parametrize("header", ['"abc"', "*", '""', '"1.5"'])
def test_a_malformed_if_match_is_428_with_a_hint(header: str) -> None:
    with pytest.raises(PreconditionRequiredError, match="quoted integer version"):
        deps.require_if_match(header)


# ── Request context ─────────────────────────────────────────────────────────


async def test_request_context_is_built_by_auth_from_the_token_and_correlation_id() -> None:
    calls: list[dict[str, str]] = []

    class FakeAuth:
        async def build_request_context(self, *, token: str, correlation_id: str) -> RequestContext:
            calls.append({"token": token, "correlation_id": correlation_id})
            return RequestContext(
                actor_id="usr_1", account_role=Role.APPROVER, correlation_id=correlation_id
            )

    ctx = await deps.get_request_context(
        token="tok", correlation_id="corr-9", auth_service=cast(AuthService, FakeAuth())
    )

    assert calls == [{"token": "tok", "correlation_id": "corr-9"}]
    assert (ctx.actor_id, ctx.account_role, ctx.correlation_id) == (
        "usr_1",
        Role.APPROVER,
        "corr-9",
    )


async def test_an_auth_refusal_propagates_and_no_context_is_returned() -> None:
    class RefusingAuth:
        async def build_request_context(self, *, token: str, correlation_id: str) -> RequestContext:
            raise UnauthenticatedError()

    with pytest.raises(UnauthenticatedError):
        await deps.get_request_context(
            token="bad", correlation_id="c", auth_service=cast(AuthService, RefusingAuth())
        )


# ── Service assembly ────────────────────────────────────────────────────────


def _environment(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    config._settings = None


def test_auth_service_is_request_scoped_not_shared() -> None:
    first = deps.get_auth_service(SESSION)
    second = deps.get_auth_service(SESSION)
    assert isinstance(first, AuthService)
    assert first is not second


def test_auth_service_refuses_to_exist_when_identity_is_misconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(
        monkeypatch,
        ENVIRONMENT="production",
        USE_STUB_IDENTITY="false",
        CLERK_ISSUER="",
        CLERK_SECRET_KEY="",
    )
    with pytest.raises(ServiceMisconfiguredError):
        deps.get_auth_service(SESSION)


def test_matter_access_stub_denies_by_default_and_is_refused_when_deployed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert isinstance(deps.get_matter_access_stub(), StubMatterAccessAdapter)
    _environment(monkeypatch, ENVIRONMENT="production")
    with pytest.raises(MatterServiceUnavailableError):
        deps.get_matter_access_stub()


async def test_module_services_are_assembled_over_the_request_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch, BILLING_GRACE_PERIOD_DAYS="9")
    auth = deps.get_auth_service(SESSION)
    ctx = RequestContext(actor_id="usr_1", account_role=Role.APPROVER, correlation_id="c")

    party = deps.get_party_service(SESSION, auth, deps.get_matter_access_stub())
    billing = await deps.get_billing_service(SESSION)

    assert isinstance(party, PartyService)
    assert isinstance(billing, BillingService)
    assert billing._grace_period_days == 9  # noqa: SLF001
    assert isinstance(deps.get_notification_service(SESSION), NotificationService)
    assert isinstance(deps.get_notarial_register_service(SESSION), NotarialRegisterService)
    obligations = await deps.get_obligations_service(ctx, SESSION)
    assert isinstance(obligations, ObligationsService)
    # Not cached: a second request must never reuse the first request's session.
    assert await deps.get_obligations_service(ctx, SESSION) is not obligations
