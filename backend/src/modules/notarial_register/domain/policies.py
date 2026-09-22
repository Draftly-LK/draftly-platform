"""Notarial register authorization and validation policies."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import is_capability_granted
from src.modules.notarial_register.domain.errors import PractisingNotaryRequiredError
from src.modules.notarial_register.domain.models import AttestationState, SourceKind
from src.platform.errors import CapabilityDeniedError, DomainRuleError
from src.platform.request_context import RequestContext


def require_capability(ctx: RequestContext, capability: str) -> None:
    role = ctx.account_role
    if role is None or not is_capability_granted(role, capability):
        raise CapabilityDeniedError(
            f"Capability '{capability}' is required.",
        )


def require_practising_notary_actor(ctx: RequestContext) -> None:
    """V0: approver role carries instrument.attest and represents a practising notary."""
    require_capability(ctx, "instrument.attest")
    if ctx.account_role not in (Role.APPROVER, Role.ADMINISTRATOR):
        raise PractisingNotaryRequiredError()


def validate_export_source(
    *,
    source_kind: SourceKind,
    export_id: str | None,
    external_reason: str | None,
) -> None:
    if source_kind == SourceKind.EXPORT and not export_id:
        raise DomainRuleError("export_id is required when source_kind is export.")
    if source_kind == SourceKind.EXTERNAL and not external_reason:
        raise DomainRuleError("external_reason is required for external paper instruments.")


def assert_state_transition(current: AttestationState, allowed: set[AttestationState]) -> None:
    from src.modules.notarial_register.domain.errors import InvalidAttestationStateError

    if current not in allowed:
        raise InvalidAttestationStateError(
            f"State '{current.value}' does not allow this transition.",
        )


#: notarial-register-service.md records attestedAt in Asia/Colombo.
REGISTER_TIMEZONE = ZoneInfo("Asia/Colombo")


def register_year_for(attested_at: datetime) -> int:
    """The Colombo calendar year of the attestation, which picks its register.

    Serials run per notary and register year, so a UTC instant late on
    31 December, already 1 January in Colombo, belongs to the new year's
    register. A naive datetime is taken as Colombo time already.
    """
    if attested_at.tzinfo is None:
        return attested_at.year
    return attested_at.astimezone(REGISTER_TIMEZONE).year
