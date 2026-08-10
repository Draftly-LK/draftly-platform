"""Party domain policies — confidentiality, capabilities, duplicate helpers."""

from __future__ import annotations

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import (
    SPECIAL_CAPABILITIES,
    is_capability_granted,
)
from src.modules.party.domain.models import (
    ConfidentialityLevel,
    ScreeningOutcome,
    ScreeningResult,
)
from src.platform.errors import CapabilityDeniedError


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


def effective_confidentiality(
    party_level: ConfidentialityLevel,
    screenings: list[ScreeningResult],
) -> ConfidentialityLevel:
    """Maximum of party setting and any restricted screening outcome."""
    order = {
        ConfidentialityLevel.STANDARD: 0,
        ConfidentialityLevel.PRIVATE_MATTER: 1,
        ConfidentialityLevel.RESTRICTED_COMPLIANCE: 2,
    }
    level = party_level
    for result in screenings:
        if result.outcome in (
            ScreeningOutcome.POTENTIAL_MATCH,
            ScreeningOutcome.CONFIRMED_MATCH,
        ):
            candidate = ConfidentialityLevel.RESTRICTED_COMPLIANCE
            if order[candidate] > order[level]:
                level = candidate
    return level


def identifier_last4(value: str) -> str:
    stripped = value.strip()
    if len(stripped) <= 4:
        return stripped
    return stripped[-4:]


def normalise_name_for_probe(name: str) -> str:
    return " ".join(name.lower().split())
