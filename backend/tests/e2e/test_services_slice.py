"""Cross-service slice E2E using in-memory fakes (no live Postgres).

Covers the V0 services in this delivery: billing entitlements → party identity →
obligations confirmation → notification delivery → notarial register
attestation. Document-processing remains out of scope.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.modules.auth.domain.models import Role
from src.modules.billing.application.billing_service import BillingService
from src.modules.billing.domain.models import PlanEntitlement
from src.modules.billing.infrastructure.stub_adapter import StubBillingAdapter
from src.modules.notarial_register.domain.errors import UnapprovedInstrumentError
from src.modules.notification.domain.models import NotificationChannel, NotificationLocale
from src.modules.obligations.application.obligations_service import (
    ConfirmDeadlineCommand,
    CreateObligationCommand,
)
from src.modules.obligations.domain.models import (
    ObligationClass,
    ObligationHardness,
    ObligationScope,
    ObligationStatus,
    ObligationType,
)
from src.modules.party.ports import CreatePartyInput, RecordIdentityEvidenceInput
from src.platform.request_context import RequestContext
from tests.fixtures.party_synthetic import SYNTHETIC_NIC, SYNTHETIC_PARTY_A
from tests.unit.test_billing_service import (
    FakeAudit,
    FakeClock,
    FakeEventPort,
    FakePlanRepo,
    FakeSubscriptionRepo,
    FakeUsageRepo,
    FakeWebhookRepo,
    _plan,
    _subscription,
)
from tests.unit.test_notarial_register_service import build_service, make_attestation_input, make_ctx
from tests.unit.test_notification_service import make_service as make_notification_service
from tests.unit.test_obligations_service import _service as make_obligations
from tests.unit.test_party_service import _service as make_party_service

_NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
_ACTOR = "usr_synthetic_a"


@pytest.mark.asyncio
async def test_shipped_services_happy_path_slice() -> None:
    ctx = RequestContext(actor_id=_ACTOR, account_role=Role.APPROVER, correlation_id="e2e-1")

    plan = _plan()
    ents = [
        PlanEntitlement(
            plan_version_id=plan.id,
            feature_key="drafting.enabled",
            limit_value=None,
            enabled=True,
        )
    ]
    billing = BillingService(
        plan_repo=FakePlanRepo([plan], {plan.id: ents}),
        subscription_repo=FakeSubscriptionRepo({_ACTOR: _subscription(user_id=_ACTOR)}),
        usage_repo=FakeUsageRepo(),
        webhook_repo=FakeWebhookRepo(),
        billing_provider=StubBillingAdapter(),
        audit_port=FakeAudit(),
        event_port=FakeEventPort(),
        clock=FakeClock(),
    )
    decision = await billing.require_feature(_ACTOR, "drafting.enabled")
    assert decision.allowed is True

    party_svc = make_party_service()
    party_read = await party_svc.create_party(ctx, CreatePartyInput(**{**SYNTHETIC_PARTY_A}))
    evidence_read = await party_svc.record_identity_evidence(
        ctx,
        party_read.party.id,
        RecordIdentityEvidenceInput(
            evidence_kind="nic",
            identifier_value=SYNTHETIC_NIC,
            issued_on=None,
            expires_on=None,
            issuing_authority=None,
            document_id=None,
            document_version_id="docver-synthetic-001",
            evidence_span=None,
            supersedes_evidence_id=None,
        ),
    )
    assert evidence_read.evidence.identifier_last4 == SYNTHETIC_NIC[-4:]

    obligations = make_obligations()
    obligation = await obligations.create_obligation(
        ctx,
        CreateObligationCommand(
            scope=ObligationScope.MATTER,
            obligation_type=ObligationType.NOTARIAL_REGISTRATION,
            obligation_class=ObligationClass.LEGAL_DEADLINE,
            label_key="obligation.test.registration",
            due_at=_NOW + timedelta(days=30),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.HARD,
            assignee_user_id=_ACTOR,
            matter_id="matter-e2e-001",
        ),
    )
    assert obligation.status == ObligationStatus.AWAITING_CONFIRMATION
    confirmed = await obligations.confirm_deadline(
        ctx,
        obligation.id,
        ConfirmDeadlineCommand(reason="Synthetic lawyer confirm"),
    )
    assert confirmed.status in (
        ObligationStatus.UPCOMING,
        ObligationStatus.DUE,
        ObligationStatus.OVERDUE,
    )

    notification = make_notification_service()
    await notification.patch_preferences(
        ctx,
        channel=NotificationChannel.EMAIL,
        enabled=True,
        locale=NotificationLocale.EN,
    )
    delivery_args = {
        "organisation_id": _ACTOR,
        "source_event_id": "evt-e2e-01",
        "obligation_id": obligation.id,
        "matter_id": "matter-e2e-001",
        "recipient_user_id": _ACTOR,
        "channel": NotificationChannel.EMAIL,
        "reminder_type": "due-in-24-hours",
        "obligation_class": "legal-deadline",
        "urgency": "critical",
        "confidentiality_level": "private-matter",
        "template_key": "obligation.reminder.due_in_24_hours",
        "delivery_policy_key": "legal-deadline.standard",
        "locale": NotificationLocale.EN,
    }
    first = await notification.create_delivery_idempotent(**delivery_args)
    second = await notification.create_delivery_idempotent(**delivery_args)
    assert first.id == second.id

    service, _, _ = build_service()
    notary_ctx = make_ctx(_ACTOR)
    with pytest.raises(UnapprovedInstrumentError):
        await service.record_attestation(
            notary_ctx,
            "mat_demo_001",
            make_attestation_input(approved_instrument_fixture=False),
        )
    attestation = await service.record_attestation(
        notary_ctx,
        "mat_demo_001",
        make_attestation_input(approved_instrument_fixture=True),
    )
    assert attestation.id
