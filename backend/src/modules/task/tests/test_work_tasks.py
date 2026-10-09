"""Operational work is recorded, never a shortcut through legal policy."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from src.modules.task.domain.work import WorkTask, progress_for, task_decision
from src.platform.errors import DomainRuleError, PreconditionFailedError


def task(**changes):
    return replace(
        WorkTask(
            id="work_synthetic",
            user_id="usr_synthetic",
            matter_id="mat_synthetic",
            group="execution",
            origin="lawyer",
            state="not-started",
            title="Synthetic work",
            created_by="usr_synthetic",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        **changes,
    )


def test_progress_counts_only_current_applicable_leaf_tasks():
    rows = [
        task(id="complete", state="complete"),
        task(id="stale", state="stale"),
        task(id="unknown", state="pending-applicability"),
        task(id="excluded", state="not-applicable"),
        task(id="cancelled", state="cancelled"),
    ]
    assert progress_for(rows) == (2, 1, 50, True)
    assert progress_for([]) == (0, 0, 0, True)


def test_governed_or_projection_completion_cannot_be_manufactured():
    with pytest.raises(DomainRuleError):
        task_decision(task(origin="governed"), "complete", actor="usr_synthetic", current=True)


def test_completion_pins_actor_and_correction_preserves_prior_completion():
    completed = task_decision(task(), "complete", actor="usr_synthetic", current=True)
    assert completed.state == "complete" and completed.completed_by == "usr_synthetic"
    with pytest.raises(PreconditionFailedError):
        task_decision(completed, "complete", actor="usr_synthetic", current=False)
    reviewed = task_decision(
        replace(completed, state="stale"), "review", actor="usr_synthetic", current=True
    )
    assert reviewed.state == "not-started"
    assert reviewed.completed_at == completed.completed_at


def test_cancelled_task_cannot_be_completed_again():
    with pytest.raises(DomainRuleError):
        task_decision(task(state="cancelled"), "complete", actor="usr_synthetic", current=True)
