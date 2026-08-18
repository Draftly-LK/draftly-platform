"""Unit tests for obligation policies."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.obligations.domain.errors import ConfirmationRequiredError
from src.modules.obligations.domain.models import (
    ConfidentialityLevel,
    LawyerConfirmation,
    LawyerConfirmationStatus,
    Obligation,
    ObligationClass,
    ObligationHardness,
    ObligationScope,
    ObligationStatus,
    ObligationType,
    SourceType,
    TriggerType,
)
from src.modules.obligations.domain.policies import (
    assert_can_complete,
    is_authoritative,
    project_time_status,
    requires_lawyer_confirmation,
)


def _obligation(**overrides: object) -> Obligation:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    base = Obligation(
        id="obl_test",
        organisation_id="org_user_a",
        scope=ObligationScope.MATTER,
        obligation_type=ObligationType.DOCUMENT_REQUEST,
        obligation_class=ObligationClass.CLIENT_COMMITMENT,
        label_key="obligation.test",
        source_type=SourceType.MANUAL,
        source_id="manual",
        trigger_type=TriggerType.MANUAL,
        trigger_date=now,
        due_at=datetime(2026, 4, 1, tzinfo=UTC),
        timezone="Asia/Colombo",
        hardness=ObligationHardness.SOFT,
        status=ObligationStatus.UPCOMING,
        assignee_user_id="usr_a",
        reminder_policy_id="default-reminders-v1",
        confidentiality_level=ConfidentialityLevel.STANDARD,
        lawyer_confirmation=LawyerConfirmation(status=LawyerConfirmationStatus.NOT_REQUIRED),
        version=1,
        created_at=now,
        updated_at=now,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_hard_legal_deadline_requires_confirmation() -> None:
    obligation = _obligation(
        hardness=ObligationHardness.HARD,
        obligation_class=ObligationClass.LEGAL_DEADLINE,
        lawyer_confirmation=LawyerConfirmation(status=LawyerConfirmationStatus.PENDING),
        status=ObligationStatus.AWAITING_CONFIRMATION,
    )
    assert requires_lawyer_confirmation(obligation)
    assert not is_authoritative(obligation)


def test_confirmed_hard_deadline_is_authoritative() -> None:
    obligation = _obligation(
        hardness=ObligationHardness.HARD,
        obligation_class=ObligationClass.LEGAL_DEADLINE,
        lawyer_confirmation=LawyerConfirmation(status=LawyerConfirmationStatus.CONFIRMED),
        status=ObligationStatus.UPCOMING,
    )
    assert is_authoritative(obligation)


def test_complete_blocked_without_confirmation() -> None:
    obligation = _obligation(
        hardness=ObligationHardness.HARD,
        obligation_class=ObligationClass.COMPLIANCE_DEADLINE,
        lawyer_confirmation=LawyerConfirmation(status=LawyerConfirmationStatus.PENDING),
        status=ObligationStatus.AWAITING_CONFIRMATION,
    )
    with pytest.raises(ConfirmationRequiredError):
        assert_can_complete(obligation)


def test_project_overdue_from_due_at() -> None:
    obligation = _obligation(
        due_at=datetime(2026, 1, 1, tzinfo=UTC),
        status=ObligationStatus.UPCOMING,
    )
    projected = project_time_status(obligation, datetime(2026, 2, 1, tzinfo=UTC))
    assert projected == ObligationStatus.OVERDUE
