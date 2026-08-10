"""Fixture deadline rules — synthetic approved rules for tests and local dev."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.modules.obligations.domain.models import (
    ApprovedDeadlineRule,
    DeadlineCalculation,
    ObligationClass,
    ObligationType,
    ReminderScheduleSpec,
    ReminderType,
    TriggerType,
)
from src.modules.obligations.ports import DeadlineRulePort

_COLOMBO = ZoneInfo("Asia/Colombo")

_DEFAULT_REMINDER_POLICY = "default-reminders-v1"

_FIXTURE_RULES: list[ApprovedDeadlineRule] = [
    ApprovedDeadlineRule(
        id="fixture-notarial-annual-v1",
        version="1",
        obligation_type=ObligationType.NOTARIAL_ANNUAL_CERTIFICATE,
        obligation_class=ObligationClass.COMPLIANCE_DEADLINE,
        trigger_type=TriggerType.ANNUAL,
        timezone="Asia/Colombo",
        explanation_template="Fixture: annual certificate due 1 April (lawyer review pending).",
        reminder_policy_id=_DEFAULT_REMINDER_POLICY,
        label_key="obligation.notarial.annual-certificate",
    ),
    ApprovedDeadlineRule(
        id="fixture-notarial-monthly-return-v1",
        version="1",
        obligation_type=ObligationType.NOTARIAL_MONTHLY_RETURN,
        obligation_class=ObligationClass.COMPLIANCE_DEADLINE,
        trigger_type=TriggerType.MONTHLY_CLOSE,
        timezone="Asia/Colombo",
        explanation_template="Fixture: monthly return due 15th of following month (lawyer review pending).",
        reminder_policy_id=_DEFAULT_REMINDER_POLICY,
        label_key="obligation.notarial.monthly-return",
    ),
    ApprovedDeadlineRule(
        id="fixture-deed-registration-local-v1",
        version="1",
        obligation_type=ObligationType.NOTARIAL_REGISTRATION,
        obligation_class=ObligationClass.LEGAL_DEADLINE,
        trigger_type=TriggerType.ATTESTATION,
        timezone="Asia/Colombo",
        explanation_template="Fixture: deed registration within jurisdiction — 30-day candidate.",
        reminder_policy_id=_DEFAULT_REMINDER_POLICY,
        label_key="obligation.notarial.registration",
    ),
    ApprovedDeadlineRule(
        id="fixture-deed-registration-outside-v1",
        version="1",
        obligation_type=ObligationType.NOTARIAL_REGISTRATION,
        obligation_class=ObligationClass.LEGAL_DEADLINE,
        trigger_type=TriggerType.ATTESTATION,
        timezone="Asia/Colombo",
        explanation_template="Fixture: deed registration outside jurisdiction — 60-day candidate.",
        reminder_policy_id=_DEFAULT_REMINDER_POLICY,
        label_key="obligation.notarial.registration",
    ),
    ApprovedDeadlineRule(
        id="fixture-aml-sanctions-v1",
        version="1",
        obligation_type=ObligationType.AML_SANCTIONS_REPORT,
        obligation_class=ObligationClass.COMPLIANCE_DEADLINE,
        trigger_type=TriggerType.DESIGNATED_PERSON,
        timezone="Asia/Colombo",
        explanation_template="Fixture: restricted compliance escalation — 24-hour candidate.",
        reminder_policy_id=_DEFAULT_REMINDER_POLICY,
        label_key="obligation.aml.sanctions-report",
    ),
]

_REMINDER_SCHEDULES: dict[str, list[ReminderScheduleSpec]] = {
    _DEFAULT_REMINDER_POLICY: [
        ReminderScheduleSpec(reminder_type=ReminderType.ADVANCE, offset_days=-7),
        ReminderScheduleSpec(reminder_type=ReminderType.DUE_DAY, offset_days=0),
        ReminderScheduleSpec(reminder_type=ReminderType.OVERDUE, offset_days=1),
    ],
}


class FixtureDeadlineRulePort(DeadlineRulePort):
    """Approved-rule fixture port — not production legal authority."""

    async def find_applicable_rules(
        self,
        *,
        trigger_type: TriggerType,
        trigger_date: datetime,
        context: dict[str, str],
    ) -> list[ApprovedDeadlineRule]:
        matches = [r for r in _FIXTURE_RULES if r.trigger_type == trigger_type]
        if trigger_type == TriggerType.ATTESTATION:
            regime = context.get("registration_regime", "")
            jurisdiction = context.get("registration_jurisdiction", "")
            if regime != "deed" or not jurisdiction:
                return []
            if jurisdiction == "within":
                return [r for r in matches if r.id == "fixture-deed-registration-local-v1"]
            if jurisdiction == "outside":
                return [r for r in matches if r.id == "fixture-deed-registration-outside-v1"]
            return []
        if trigger_type == TriggerType.MONTHLY_CLOSE:
            return [r for r in matches if r.id == "fixture-notarial-monthly-return-v1"]
        if trigger_type == TriggerType.ANNUAL:
            return [r for r in matches if r.id == "fixture-notarial-annual-v1"]
        if trigger_type == TriggerType.DESIGNATED_PERSON:
            return [r for r in matches if r.id == "fixture-aml-sanctions-v1"]
        return matches

    async def calculate(
        self,
        rule: ApprovedDeadlineRule,
        *,
        trigger_date: datetime,
        context: dict[str, str],
    ) -> DeadlineCalculation | None:
        local = (
            trigger_date.astimezone(_COLOMBO)
            if trigger_date.tzinfo
            else trigger_date.replace(tzinfo=UTC).astimezone(_COLOMBO)
        )

        if rule.id == "fixture-notarial-annual-v1":
            year = local.year
            if local.month > 4 or (local.month == 4 and local.day > 1):
                year += 1
            due = datetime(year, 4, 1, 23, 59, 59, tzinfo=_COLOMBO)
        elif rule.id == "fixture-notarial-monthly-return-v1":
            month = local.month + 1
            year = local.year
            if month > 12:
                month = 1
                year += 1
            due = datetime(year, month, 15, 23, 59, 59, tzinfo=_COLOMBO)
        elif rule.id == "fixture-deed-registration-local-v1":
            due = local + timedelta(days=30)
        elif rule.id == "fixture-deed-registration-outside-v1":
            due = local + timedelta(days=60)
        elif rule.id == "fixture-aml-sanctions-v1":
            due = local + timedelta(hours=24)
        else:
            return None

        return DeadlineCalculation(
            trigger_date=trigger_date,
            rule_id=rule.id,
            rule_version=rule.version,
            raw_due_at=due,
            explanation=rule.explanation_template,
        )

    async def reminder_schedule(self, policy_id: str) -> list[ReminderScheduleSpec]:
        return list(
            _REMINDER_SCHEDULES.get(policy_id, _REMINDER_SCHEDULES[_DEFAULT_REMINDER_POLICY])
        )
