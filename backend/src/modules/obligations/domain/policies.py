"""Obligation lifecycle and confirmation policies."""

from __future__ import annotations

from datetime import UTC, datetime

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import is_capability_granted
from src.modules.obligations.domain.errors import (
    ConfirmationRequiredError,
    InvalidTransitionError,
    LawyerConfirmationDeniedError,
)
from src.modules.obligations.domain.models import (
    ConfidentialityLevel,
    LawyerConfirmationStatus,
    Obligation,
    ObligationClass,
    ObligationHardness,
    ObligationStatus,
)


def solo_organisation_id(user_id: str) -> str:
    """Derive organisation scope for single-user Gmail accounts (auth phase)."""
    return f"org_{user_id}"


def is_lawyer_role(role: Role) -> bool:
    return role in {Role.APPROVER, Role.ADMINISTRATOR}


def can_confirm_deadline(role: Role) -> bool:
    return is_lawyer_role(role) and is_capability_granted(role, "deadline.confirm")


def requires_lawyer_confirmation(obligation: Obligation) -> bool:
    if obligation.hardness != ObligationHardness.HARD:
        return False
    return obligation.obligation_class in {
        ObligationClass.LEGAL_DEADLINE,
        ObligationClass.COMPLIANCE_DEADLINE,
    }


def is_authoritative(obligation: Obligation) -> bool:
    if not requires_lawyer_confirmation(obligation):
        return obligation.status not in {
            ObligationStatus.DRAFT,
            ObligationStatus.AWAITING_CONFIRMATION,
            ObligationStatus.CANCELLED,
            ObligationStatus.SUSPENDED,
        }
    return obligation.lawyer_confirmation.status in {
        LawyerConfirmationStatus.CONFIRMED,
        LawyerConfirmationStatus.CORRECTED,
    }


def initial_status_for_create(obligation: Obligation) -> ObligationStatus:
    if requires_lawyer_confirmation(obligation):
        if obligation.lawyer_confirmation.status in {
            LawyerConfirmationStatus.CONFIRMED,
            LawyerConfirmationStatus.CORRECTED,
        }:
            return ObligationStatus.UPCOMING
        return ObligationStatus.AWAITING_CONFIRMATION
    return ObligationStatus.UPCOMING


def project_time_status(obligation: Obligation, now: datetime) -> ObligationStatus:
    """Map active obligations to upcoming/due/overdue from due_at."""
    if obligation.status in {
        ObligationStatus.DRAFT,
        ObligationStatus.AWAITING_CONFIRMATION,
        ObligationStatus.COMPLETE,
        ObligationStatus.CANCELLED,
        ObligationStatus.SUSPENDED,
    }:
        return obligation.status
    if not is_authoritative(obligation):
        return obligation.status

    due = obligation.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    now_aware = now if now.tzinfo else now.replace(tzinfo=UTC)
    if now_aware < due:
        return ObligationStatus.UPCOMING
    if now_aware.date() == due.date():
        return ObligationStatus.DUE
    return ObligationStatus.OVERDUE


def assert_can_complete(obligation: Obligation) -> None:
    if obligation.status in {ObligationStatus.COMPLETE, ObligationStatus.CANCELLED}:
        raise InvalidTransitionError("Obligation is already terminal.")
    if requires_lawyer_confirmation(obligation) and not is_authoritative(obligation):
        raise ConfirmationRequiredError()


def assert_can_cancel(obligation: Obligation) -> None:
    if obligation.status in {ObligationStatus.COMPLETE, ObligationStatus.CANCELLED}:
        raise InvalidTransitionError("Obligation is already terminal.")


def assert_can_confirm(obligation: Obligation, *, role: Role) -> None:
    if obligation.status != ObligationStatus.AWAITING_CONFIRMATION:
        raise InvalidTransitionError("Only awaiting-confirmation obligations can be confirmed.")
    if not can_confirm_deadline(role):
        raise LawyerConfirmationDeniedError()


def reminders_allowed(obligation: Obligation) -> bool:
    if obligation.status in {
        ObligationStatus.DRAFT,
        ObligationStatus.AWAITING_CONFIRMATION,
        ObligationStatus.COMPLETE,
        ObligationStatus.CANCELLED,
        ObligationStatus.SUSPENDED,
    }:
        return False
    return is_authoritative(obligation)


def can_view_obligation(
    obligation: Obligation,
    *,
    actor_id: str,
    actor_role: Role,
    has_compliance_access: bool,
) -> bool:
    if obligation.confidentiality_level == ConfidentialityLevel.RESTRICTED_COMPLIANCE:
        if not has_compliance_access:
            return False
    if obligation.assignee_user_id == actor_id:
        return True
    if obligation.owner_user_id == actor_id:
        return True
    if obligation.backup_assignee_user_id == actor_id:
        return True
    if actor_role == Role.ADMINISTRATOR:
        return True
    return False
