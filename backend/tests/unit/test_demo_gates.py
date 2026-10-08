"""The DEMO_RELAXED_GATES switch (src/demo_gates.py, src/bootstrap.py).

Off by default, refused outside the stub environments, and when on it sets
aside only the two matter-wide approval rules — never the form's own fields.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import src.platform.config as config
from src import bootstrap
from src.demo_gates import FormScopedFactReader, NonBlockingChecklist
from src.modules.matter.infrastructure.workflow_commands import (
    DemoMatterWorkflowCommandAdapter,
    SqlMatterWorkflowCommandAdapter,
)
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary
from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader
from src.platform.errors import ServiceMisconfiguredError

SESSION = cast(AsyncSession, object())


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    config._settings = None


def test_the_switch_defaults_to_off() -> None:
    assert config.Settings.model_fields["demo_relaxed_gates"].default is False


def test_switched_off_the_real_gates_are_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set explicitly: a developer's own .env may have the demo switch on.
    _configure(monkeypatch, ENVIRONMENT="local", DEMO_RELAXED_GATES="false")
    service = bootstrap.build_approval_service(SESSION)
    assert isinstance(service._facts, SqlConfirmedFactReader)
    assert not isinstance(service._checklist, NonBlockingChecklist)
    assert type(service._matter_commands) is SqlMatterWorkflowCommandAdapter


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_the_switch_is_refused_on_a_deployed_environment(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, DEMO_RELAXED_GATES="true")
    with pytest.raises(ServiceMisconfiguredError) as excinfo:
        bootstrap.build_approval_service(SESSION)
    assert environment in excinfo.value.reason


def test_drafting_and_approval_both_get_the_overrides_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, ENVIRONMENT="local", DEMO_RELAXED_GATES="true")
    approval = bootstrap.build_approval_service(SESSION)
    draft = bootstrap.build_draft_service(SESSION)
    for facts, checklist in (
        (approval._facts, approval._checklist),
        (draft._facts, draft._checklist),
    ):
        assert isinstance(facts, FormScopedFactReader)
        assert isinstance(checklist, NonBlockingChecklist)
    assert isinstance(approval._matter_commands, DemoMatterWorkflowCommandAdapter)
    assert isinstance(draft._matter_workflow, DemoMatterWorkflowCommandAdapter)


class _Facts:
    def __init__(self, summary: FactTierSummary) -> None:
        self.summary = summary

    async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary:
        return self.summary


async def test_confirmed_facts_and_conflicts_pass_through_untouched() -> None:
    confirmed = {
        "lk.rta.fact.parcel_no": ConfirmedFactValue(
            fact_id="fct_1", fact_type_id="lk.rta.fact.parcel_no", value="0020", version=1
        )
    }
    inner = FactTierSummary(
        confirmed=confirmed,
        unconfirmed_critical_fact_type_ids=("lk.rta.fact.company_registration_no",),
        conflicted_fact_type_ids=("lk.rta.fact.transferor_nic",),
        has_current_search_evidence=True,
    )
    summary = await FormScopedFactReader(_Facts(inner)).summarise("usr_1", "mat_1")
    assert summary.unconfirmed_critical_fact_type_ids == ()
    assert summary.confirmed == confirmed
    assert summary.conflicted_fact_type_ids == ("lk.rta.fact.transferor_nic",)
    assert summary.has_current_search_evidence is True


async def test_open_checklist_items_block_nothing() -> None:
    blocking = await NonBlockingChecklist().blocking_requirement_ids(
        user_id="usr_1", matter_id="mat_1"
    )
    assert blocking == ()
