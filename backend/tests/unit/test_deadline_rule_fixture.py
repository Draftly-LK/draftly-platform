"""Tests for fixture deadline rule port."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.obligations.domain.models import TriggerType
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort


@pytest.mark.asyncio
async def test_deed_within_jurisdiction_30_day_fixture() -> None:
    port = FixtureDeadlineRulePort()
    trigger = datetime(2026, 1, 1, tzinfo=UTC)
    rules = await port.find_applicable_rules(
        trigger_type=TriggerType.ATTESTATION,
        trigger_date=trigger,
        context={"registration_regime": "deed", "registration_jurisdiction": "within"},
    )
    assert len(rules) == 1
    calc = await port.calculate(rules[0], trigger_date=trigger, context={})
    assert calc is not None
    assert calc.raw_due_at.day == 31
    assert "Fixture" in calc.explanation


@pytest.mark.asyncio
async def test_unknown_regime_returns_no_rules() -> None:
    port = FixtureDeadlineRulePort()
    rules = await port.find_applicable_rules(
        trigger_type=TriggerType.ATTESTATION,
        trigger_date=datetime(2026, 1, 1, tzinfo=UTC),
        context={"registration_regime": "unknown"},
    )
    assert rules == []
