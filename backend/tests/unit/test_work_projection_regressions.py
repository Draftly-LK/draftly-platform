"""Review regressions exercise the real composition seam with synthetic owner reads."""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import bootstrap
from src.modules.auth.domain.models import Role
from src.modules.draft.contracts import FormScope
from src.modules.task.contracts import ReadinessReference
from src.platform.request_context import RequestContext


def owner_service(monkeypatch, *, forms=(), snapshots=None, source=None):
    ctx = RequestContext("usr_synthetic", Role.APPROVER, "synthetic-projection")
    scope = FormScope("tx_synthetic", 1, "parcel_synthetic", "party_a", "party_b")
    draft_reader = SimpleNamespace(
        list_forms=AsyncMock(return_value=(list(forms), None)),
        get_form_snapshot=AsyncMock(side_effect=lambda user, ref: snapshots[ref]),
    )
    monkeypatch.setattr(bootstrap, "build_draft_service", lambda session: draft_reader)
    monkeypatch.setattr(
        bootstrap,
        "build_readiness_service",
        lambda session: SimpleNamespace(
            evaluate=AsyncMock(return_value=SimpleNamespace(dependencies=()))
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "build_ingestion_service",
        lambda session: SimpleNamespace(
            get_source_file=AsyncMock(return_value=SimpleNamespace(source_file=source))
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "build_check_service",
        lambda session: SimpleNamespace(
            list_issues=AsyncMock(return_value=([], None)),
            gates=AsyncMock(return_value=SimpleNamespace(stale_check_ids=())),
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "build_matter_scope_service",
        lambda session: SimpleNamespace(list_transactions=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(bootstrap, "build_fact_review_service", lambda session: SimpleNamespace())
    monkeypatch.setattr(bootstrap, "build_source_file_storage", lambda: SimpleNamespace())
    monkeypatch.setattr(bootstrap, "build_checklist_service", lambda session: SimpleNamespace())
    monkeypatch.setattr(
        bootstrap,
        "build_matter_service",
        lambda session: SimpleNamespace(
            get_access_summary=AsyncMock(
                return_value=SimpleNamespace(
                    user_id=ctx.actor_id, responsible_lawyer_id=ctx.actor_id
                )
            )
        ),
    )
    monkeypatch.setattr(
        bootstrap, "_build_document_matter_lock", lambda session: SimpleNamespace(lock=AsyncMock())
    )
    return bootstrap.build_work_task_service(None), ctx, scope


async def test_reviewed_template_does_not_hide_unreviewed_form8_in_same_scope(monkeypatch):
    scope = FormScope("tx_synthetic", 1, "parcel_synthetic", "party_a", "party_b")
    forms = [
        SimpleNamespace(
            id="frm_tire31", scope=scope, template_id="Ti.Re31", predecessor_form_id=None
        ),
        SimpleNamespace(id="frm_form8", scope=scope, template_id="Form8", predecessor_form_id=None),
    ]
    snapshots = {
        form.id: SimpleNamespace(
            form_id=form.id,
            scope=scope,
            scope_current=True,
            stale_reason=None,
            version=1,
            unreviewed_field_ids=() if form.id == "frm_tire31" else ("critical_synthetic",),
            unresolved_field_ids=(),
            approval_id="apr_synthetic" if form.id == "frm_tire31" else None,
            approved_artifact_hash="synthetic-hash" if form.id == "frm_tire31" else None,
        )
        for form in forms
    }
    service, ctx, _ = owner_service(monkeypatch, forms=forms, snapshots=snapshots)
    tasks = await service._projection.projected_tasks(ctx, "mat_synthetic")
    assert (
        next(row for row in tasks if row.title_key == "matterChecklist.tasks.draft.title").state
        == "in-progress"
    )
    assert (
        next(row for row in tasks if row.title_key == "matterChecklist.tasks.approval.title").state
        == "not-started"
    )


@pytest.mark.parametrize(
    "state,stored", [("REJECTED", False), ("REJECTED", True), ("STORED", False)]
)
async def test_rejected_or_unstored_source_is_not_task_support(monkeypatch, state, stored):
    source = SimpleNamespace(
        id="src_synthetic",
        matter_id="mat_synthetic",
        state=SimpleNamespace(value=state),
        version=1,
        has_stored_bytes=stored,
    )
    service, ctx, _ = owner_service(monkeypatch, source=source)
    assert (
        await service._refs.current_reference(
            ctx, "mat_synthetic", ReadinessReference("source-file", source.id, 1)
        )
        is None
    )


async def test_nonapplicable_requirement_is_excluded_even_when_old_link_is_stale(monkeypatch):
    service, ctx, _ = owner_service(monkeypatch)
    item = SimpleNamespace(
        id="cli_synthetic",
        version=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        assigned_to=None,
        applicability=SimpleNamespace(value="NOT_APPLICABLE"),
        applicability_decided_by=ctx.actor_id,
    )
    row = SimpleNamespace(
        item=item,
        has_invalid_support=True,
        computed_resolution=SimpleNamespace(value="CLOSED"),
        lifecycle=SimpleNamespace(value="NOT_TRIGGERED"),
        requirement=SimpleNamespace(
            label_key="synthetic.title", explanation_key="synthetic.reason"
        ),
        blocks_approval=False,
    )
    service._projection = SimpleNamespace(projected_tasks=AsyncMock(return_value=()))
    service._checklist = SimpleNamespace(
        get_checklist=AsyncMock(
            return_value=SimpleNamespace(
                items=(row,), snapshot=SimpleNamespace(created_by=ctx.actor_id)
            )
        ),
        list_links=AsyncMock(return_value=()),
    )
    service._repo = SimpleNamespace(list_tasks=AsyncMock(return_value=[]))
    tasks, _, progress, next_id = await service.checklist(ctx, "mat_synthetic")
    assert next(row for row in tasks if row.id == item.id).state == "not-applicable"
    assert progress[0] == 3 and next_id != item.id


async def test_draft_review_precedes_approval_in_rows_and_next_action(monkeypatch):
    service, ctx, _ = owner_service(monkeypatch)
    projected = await service._projection.projected_tasks(ctx, "mat_synthetic")
    service._projection = SimpleNamespace(
        projected_tasks=AsyncMock(
            return_value=tuple(
                row if row.group == "drafting" else replace(row, state="complete")
                for row in projected
            )
        )
    )
    service._checklist = SimpleNamespace(
        get_checklist=AsyncMock(
            return_value=SimpleNamespace(
                items=(), snapshot=SimpleNamespace(created_by=ctx.actor_id)
            )
        )
    )
    service._repo = SimpleNamespace(list_tasks=AsyncMock(return_value=[]))
    tasks, _, _, next_id = await service.checklist(ctx, "mat_synthetic")
    drafting = [row for row in tasks if row.group == "drafting"]
    assert [row.title_key for row in drafting] == [
        "matterChecklist.tasks.draft.title",
        "matterChecklist.tasks.approval.title",
    ]
    assert next_id == drafting[0].id
