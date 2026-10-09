"""Composition-root guards and adapter selection (src/bootstrap.py).

Sibling to test_bootstrap_identity.py and test_bootstrap_extraction.py. These
pin the remaining fail-closed choices: local-disk evidence storage, the Clerk
authorised-party requirement, billing and e-mail adapter selection, platform
administration, and the worker dispatcher's outcome mapping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

import src.platform.config as config
from src import bootstrap
from src.modules.auth.infrastructure.clerk_adapter import ClerkIdentityAdapter
from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter
from src.modules.billing.infrastructure.payhere_adapter import PayHereBillingAdapter
from src.modules.billing.infrastructure.platform_admin import (
    DenyAllPlatformAdminAdapter,
    SettingsPlatformAdminAdapter,
)
from src.modules.billing.infrastructure.stub_adapter import StubBillingAdapter
from src.modules.notification.application.notification_service import DELIVER_JOB_TYPE
from src.modules.notification.infrastructure.email.console_adapter import ConsoleEmailAdapter
from src.modules.notification.infrastructure.email.resend_adapter import ResendEmailAdapter
from src.modules.notification.jobs import NOTIFICATION_CONSUMED_EVENTS
from src.modules.party.infrastructure.matter_access_stub import MatterServiceUnavailableError
from src.platform.errors import ServiceMisconfiguredError
from src.platform.messaging.dispatcher import MessageResult
from src.platform.messaging.outbox import KIND_EVENT, KIND_JOB, ClaimedMessage

DEPLOYED_ENVIRONMENTS = ["staging", "production"]
SESSION = cast(AsyncSession, object())


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    config._settings = None


# ── Identity ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_identity_guards_raise_the_typed_misconfiguration_error(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, USE_STUB_IDENTITY="true")
    with pytest.raises(ServiceMisconfiguredError) as excinfo:
        bootstrap.build_identity_adapter()
    assert excinfo.value.http_status == 503
    assert environment in excinfo.value.reason
    assert environment not in excinfo.value.message


def test_unconfigured_clerk_falls_back_to_stub_only_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT="local",
        USE_STUB_IDENTITY="false",
        CLERK_ISSUER="",
        CLERK_SECRET_KEY="",
    )
    assert isinstance(bootstrap.build_identity_adapter(), StubIdentityAdapter)


@pytest.mark.parametrize("environment", ["local", "production"])
def test_clerk_without_authorised_party_is_refused_everywhere(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT=environment,
        USE_STUB_IDENTITY="false",
        CLERK_ISSUER="https://clerk.example.test",
        CLERK_SECRET_KEY="sk_test_synthetic",
        CLERK_AUTHORIZED_PARTY=" , ",
    )
    with pytest.raises(ServiceMisconfiguredError, match="CLERK_AUTHORIZED_PARTY"):
        bootstrap.build_identity_adapter()


def test_fully_configured_clerk_selects_the_real_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT="production",
        USE_STUB_IDENTITY="false",
        CLERK_ISSUER="https://clerk.example.test",
        CLERK_SECRET_KEY="sk_test_synthetic",
        CLERK_AUTHORIZED_PARTY="https://app.example.test",
    )
    assert isinstance(bootstrap.build_identity_adapter(), ClerkIdentityAdapter)


# ── Source-file storage ─────────────────────────────────────────────────────


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_filesystem_storage_is_refused_when_deployed(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, SOURCE_FILE_STORAGE="filesystem")
    with pytest.raises(ServiceMisconfiguredError, match="SOURCE_FILE_STORAGE=filesystem"):
        bootstrap.build_ingestion_service(SESSION)


def test_unknown_storage_backend_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, ENVIRONMENT="local", SOURCE_FILE_STORAGE="ftp")
    with pytest.raises(ServiceMisconfiguredError, match="Unknown SOURCE_FILE_STORAGE"):
        bootstrap.build_ingestion_service(SESSION)


def test_ingestion_without_a_provider_leaves_the_pipeline_unwired(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Gemini selected with no key: uploads still work, nothing claims to be processed."""
    _configure(
        monkeypatch,
        ENVIRONMENT="test",
        SOURCE_FILE_STORAGE="filesystem",
        SOURCE_FILE_STORAGE_DIR=str(tmp_path),
        EXTRACTION_PROVIDER="gemini",
        GEMINI_API_KEY="",
    )
    service = bootstrap.build_ingestion_service(SESSION)
    assert service._jobs._pipeline is None  # noqa: SLF001


def test_ingestion_with_the_stub_provider_wires_a_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT="test",
        SOURCE_FILE_STORAGE="filesystem",
        SOURCE_FILE_STORAGE_DIR=str(tmp_path),
        EXTRACTION_PROVIDER="stub",
    )
    service = bootstrap.build_ingestion_service(SESSION)
    assert service._jobs._pipeline is not None  # noqa: SLF001


# ── Billing, platform admin, e-mail, party ──────────────────────────────────


def test_billing_defaults_to_the_stub_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, USE_STUB_BILLING="true", PAYHERE_MERCHANT_SECRET="secret")
    assert isinstance(bootstrap.build_billing_adapter(), StubBillingAdapter)


def test_billing_without_a_merchant_secret_stays_on_the_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, USE_STUB_BILLING="false", PAYHERE_MERCHANT_SECRET="")
    assert isinstance(bootstrap.build_billing_adapter(), StubBillingAdapter)


def test_billing_selects_payhere_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, USE_STUB_BILLING="false", PAYHERE_MERCHANT_SECRET="synthetic")
    assert isinstance(bootstrap.build_billing_adapter(), PayHereBillingAdapter)


async def test_platform_admin_denies_everyone_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, PLATFORM_ADMIN_USER_IDS="  ")
    adapter = bootstrap.build_platform_admin_adapter()
    assert isinstance(adapter, DenyAllPlatformAdminAdapter)
    assert await adapter.is_platform_admin("usr_1") is False


async def test_platform_admin_allowlist_grants_only_listed_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, PLATFORM_ADMIN_USER_IDS="usr_1, usr_2")
    adapter = bootstrap.build_platform_admin_adapter()
    assert isinstance(adapter, SettingsPlatformAdminAdapter)
    assert await adapter.is_platform_admin("usr_2") is True
    assert await adapter.is_platform_admin("usr_3") is False


def test_email_is_console_unless_outbound_is_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, RESEND_API_KEY="re_synthetic", RESEND_OUTBOUND_ENABLED="false")
    assert isinstance(bootstrap.build_email_adapter(), ConsoleEmailAdapter)

    _configure(monkeypatch, RESEND_API_KEY="", RESEND_OUTBOUND_ENABLED="true")
    assert isinstance(bootstrap.build_email_adapter(), ConsoleEmailAdapter)


def test_email_selects_resend_when_key_and_gate_are_both_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, RESEND_API_KEY="re_synthetic", RESEND_OUTBOUND_ENABLED="true")
    assert isinstance(bootstrap.build_email_adapter(), ResendEmailAdapter)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_party_matter_access_stub_is_refused_when_deployed(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment)
    with pytest.raises(MatterServiceUnavailableError):
        bootstrap.build_party_matter_access()


async def test_practising_notary_adapter_delegates_to_auth() -> None:
    calls: list[Any] = []

    class FakeAuth:
        async def require_practising_notary(self, ctx: Any) -> None:
            calls.append(ctx)

    ctx = cast(Any, object())
    await bootstrap.AuthPractisingNotaryAdapter(cast(Any, FakeAuth())).assert_practising(ctx)
    assert calls == [ctx]


# ── Service assembly and routing ────────────────────────────────────────────


def test_request_scoped_services_share_the_request_session() -> None:
    matter = bootstrap.build_matter_service(SESSION)
    approval = bootstrap.build_approval_service(SESSION)
    # The check service is its own issue gate; drafting and approval read it.
    assert type(approval._issues).__name__ == "CheckService"  # noqa: SLF001
    assert type(matter._checklist).__name__ == "ChecklistService"  # noqa: SLF001


def test_every_router_is_mounted_under_api_v1() -> None:
    app = FastAPI()
    bootstrap.register_routers(app)
    api_paths = set(app.openapi()["paths"])
    assert api_paths
    assert all(p.startswith("/api/v1/") for p in api_paths)
    assert "/api/v1/me" in api_paths


# ── Worker dispatcher ───────────────────────────────────────────────────────


def _message(kind: str, name: str) -> ClaimedMessage:
    return ClaimedMessage(
        id=1,
        organisation_id="org_1",
        kind=kind,
        name=name,
        payload={"deliveryId": "dlv_1", "organisationId": "org_1"},
        idempotency_key="k",
        attempts=1,
    )


def test_dispatcher_registers_the_delivery_job_and_every_consumed_event() -> None:
    from src.modules.matter_agent.jobs import RUN_TURN_JOB_TYPE

    registered = set(bootstrap.build_dispatcher().registered())
    expected = {
        (KIND_JOB, DELIVER_JOB_TYPE),
        (KIND_JOB, RUN_TURN_JOB_TYPE),
        (KIND_EVENT, "document.processing-completed"),
    } | {(KIND_EVENT, name) for name in NOTIFICATION_CONSUMED_EVENTS}
    assert registered == expected


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("delivered", MessageResult.DONE),
        ("suppressed", MessageResult.DONE),
        ("permanent-failure", MessageResult.DONE),
        ("unknown-delivery", MessageResult.DONE),
        ("retry", MessageResult.RETRY),
        ("dead-letter", MessageResult.DEAD_LETTER),
        ("something-new", MessageResult.FAILED),
    ],
)
async def test_delivery_outcomes_map_to_outbox_results(
    monkeypatch: pytest.MonkeyPatch, outcome: str, expected: MessageResult
) -> None:
    import src.modules.notification.jobs as jobs

    seen: list[dict[str, Any]] = []

    async def fake_delivery(session: Any, payload: dict[str, Any]) -> str:
        seen.append(payload)
        return outcome

    monkeypatch.setattr(jobs, "run_delivery_job", fake_delivery)
    dispatcher = bootstrap.build_dispatcher()

    result = await dispatcher.dispatch(SESSION, _message(KIND_JOB, DELIVER_JOB_TYPE))

    assert result is expected
    assert seen == [{"deliveryId": "dlv_1", "organisationId": "org_1"}]


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("processed", MessageResult.DONE),
        ("duplicate", MessageResult.DONE),
        ("suppressed", MessageResult.DONE),
        ("dead-letter", MessageResult.DEAD_LETTER),
        ("retry", MessageResult.FAILED),
    ],
)
async def test_event_consumer_outcomes_map_to_outbox_results(
    monkeypatch: pytest.MonkeyPatch, outcome: str, expected: MessageResult
) -> None:
    import src.modules.notification.jobs as jobs

    async def fake_consume(session: Any, payload: dict[str, Any]) -> str:
        return outcome

    monkeypatch.setattr(jobs, "consume_registered_event", fake_consume)
    dispatcher = bootstrap.build_dispatcher()
    event_name = sorted(NOTIFICATION_CONSUMED_EVENTS)[0]

    assert await dispatcher.dispatch(SESSION, _message(KIND_EVENT, event_name)) is expected
