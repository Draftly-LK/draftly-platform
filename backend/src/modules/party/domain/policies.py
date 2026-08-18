"""Party domain policies — confidentiality, capabilities, duplicate helpers."""

from __future__ import annotations

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import (
    SPECIAL_CAPABILITIES,
    is_capability_granted,
)
from src.modules.party.domain.models import (
    ConfidentialityLevel,
    EvidenceState,
    ScreeningOutcome,
    ScreeningResult,
)
from src.platform.errors import CapabilityDeniedError

# A beneficial ownership chain deeper than this is a modelling error or an
# attempt to exhaust the traversal; either way it is refused (§3.3).
MAX_BENEFICIAL_OWNERSHIP_DEPTH = 12
MAX_BENEFICIAL_OWNERSHIP_NODES = 500

# Party reads are gated: a role holding no party capability at all (maintainer)
# has no business in the protected identity tier.
PARTY_ACCESS_CAPABILITIES = ("party.record-identity", "party.read-identity")

_CONFIDENTIALITY_ORDER = {
    ConfidentialityLevel.STANDARD: 0,
    ConfidentialityLevel.PRIVATE_MATTER: 1,
    ConfidentialityLevel.RESTRICTED_COMPLIANCE: 2,
}

_EVIDENCE_TRANSITIONS: dict[EvidenceState, frozenset[EvidenceState]] = {
    EvidenceState.RECORDED: frozenset(
        {
            EvidenceState.VERIFIED,
            EvidenceState.REJECTED,
            EvidenceState.EXPIRED,
            EvidenceState.SUPERSEDED,
        }
    ),
    EvidenceState.VERIFIED: frozenset({EvidenceState.EXPIRED, EvidenceState.SUPERSEDED}),
    EvidenceState.REJECTED: frozenset({EvidenceState.SUPERSEDED}),
    EvidenceState.EXPIRED: frozenset({EvidenceState.SUPERSEDED}),
    EvidenceState.SUPERSEDED: frozenset(),
}


def require_capability(role: Role, capability: str) -> None:
    """Enforce role capability; V0 grants compliance.* to administrator only."""
    if capability in SPECIAL_CAPABILITIES:
        if role == Role.ADMINISTRATOR and capability in ("compliance.act", "compliance.view"):
            return
        raise CapabilityDeniedError(
            f"Capability '{capability}' is not granted.",
            capability=capability,
        )
    if not is_capability_granted(role, capability):
        raise CapabilityDeniedError(
            f"Capability '{capability}' is not granted to role '{role}'.",
            capability=capability,
        )


def require_party_access(role: Role) -> None:
    """Refuse any role that holds no party capability at all."""
    if not any(is_capability_granted(role, cap) for cap in PARTY_ACCESS_CAPABILITIES):
        raise CapabilityDeniedError(
            "Access to the protected identity tier is not granted to this role.",
            capability="party.record-identity",
        )


def holds_compliance_view(role: Role) -> bool:
    """True when the actor may see that a screening record exists at all."""
    return role == Role.ADMINISTRATOR


def is_evidence_transition_allowed(current: EvidenceState, target: EvidenceState) -> bool:
    return target in _EVIDENCE_TRANSITIONS.get(current, frozenset())


def effective_confidentiality(
    party_level: ConfidentialityLevel,
    screenings: list[ScreeningResult],
) -> ConfidentialityLevel:
    """Maximum of party setting and any restricted screening outcome."""
    level = party_level
    for result in screenings:
        if result.outcome in (
            ScreeningOutcome.POTENTIAL_MATCH,
            ScreeningOutcome.CONFIRMED_MATCH,
        ):
            candidate = ConfidentialityLevel.RESTRICTED_COMPLIANCE
            if _CONFIDENTIALITY_ORDER[candidate] > _CONFIDENTIALITY_ORDER[level]:
                level = candidate
    return level


def identifier_last4(value: str) -> str:
    """Last four characters, or nothing at all when that would be the whole value."""
    stripped = value.strip()
    if len(stripped) <= 4:
        return ""
    return stripped[-4:]


def normalise_name_for_probe(name: str) -> str:
    return " ".join(name.lower().split())
