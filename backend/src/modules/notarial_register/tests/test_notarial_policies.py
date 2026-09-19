"""Notarial register policies: who may attest, which register year, which moves.

A register serial is allocated per notary and register year, so the year an
attestation lands in decides its number. notarial-register-service.md fixes
attestedAt in Asia/Colombo; the year is Colombo's, whatever zone the caller
sent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.modules.auth.domain.models import Role
from src.modules.notarial_register.domain.errors import (
    InvalidAttestationStateError,
    PractisingNotaryRequiredError,
)
from src.modules.notarial_register.domain.models import AttestationState, SourceKind
from src.modules.notarial_register.domain.policies import (
    assert_state_transition,
    register_year_for,
    require_practising_notary_actor,
    validate_export_source,
)
from src.platform.errors import CapabilityDeniedError, DomainRuleError
from src.platform.request_context import RequestContext
from tests.factories.constants import USER_A

COLOMBO = timezone(timedelta(hours=5, minutes=30))


# ── Register year ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("attested_at", "year"),
    [
        pytest.param(
            datetime(2026, 12, 31, 18, 29, tzinfo=UTC), 2026, id="utc-before-colombo-midnight"
        ),
        pytest.param(
            datetime(2026, 12, 31, 18, 30, tzinfo=UTC), 2027, id="utc-at-colombo-midnight"
        ),
        pytest.param(datetime(2026, 12, 31, 20, 0, tzinfo=UTC), 2027, id="utc-new-year-in-colombo"),
        pytest.param(datetime(2027, 1, 1, 0, 30, tzinfo=COLOMBO), 2027, id="colombo-just-after"),
        pytest.param(
            datetime(2026, 12, 31, 23, 59, tzinfo=COLOMBO), 2026, id="colombo-just-before"
        ),
    ],
)
def test_the_register_year_is_the_colombo_year(attested_at: datetime, year: int) -> None:
    assert register_year_for(attested_at) == year


def test_a_leap_day_attestation_keeps_its_year() -> None:
    assert register_year_for(datetime(2028, 2, 29, 12, 0, tzinfo=COLOMBO)) == 2028


# ── Who may attest ──────────────────────────────────────────────────────────


def test_an_approver_acts_as_the_practising_notary() -> None:
    require_practising_notary_actor(RequestContext(actor_id=USER_A, account_role=Role.APPROVER))


@pytest.mark.parametrize("role", [Role.REVIEWER, Role.MAINTAINER])
def test_other_roles_cannot_attest(role: Role) -> None:
    with pytest.raises((CapabilityDeniedError, PractisingNotaryRequiredError)):
        require_practising_notary_actor(RequestContext(actor_id=USER_A, account_role=role))


# ── Sources and transitions ─────────────────────────────────────────────────


def test_an_export_source_names_its_export() -> None:
    with pytest.raises(DomainRuleError):
        validate_export_source(source_kind=SourceKind.EXPORT, export_id=None, external_reason=None)
    validate_export_source(
        source_kind=SourceKind.EXPORT, export_id="exp_synthetic", external_reason=None
    )


def test_an_external_paper_instrument_gives_a_reason() -> None:
    with pytest.raises(DomainRuleError):
        validate_export_source(source_kind=SourceKind.EXTERNAL, export_id=None, external_reason="")
    validate_export_source(
        source_kind=SourceKind.EXTERNAL,
        export_id=None,
        external_reason="Signed on paper (synthetic)",
    )


@pytest.mark.parametrize("current", list(AttestationState))
def test_a_transition_is_allowed_only_from_its_listed_states(current: AttestationState) -> None:
    allowed = {AttestationState.ATTESTED, AttestationState.REGISTRATION_DEFECTIVE}

    if current in allowed:
        assert_state_transition(current, allowed)
    else:
        with pytest.raises(InvalidAttestationStateError):
            assert_state_transition(current, allowed)
