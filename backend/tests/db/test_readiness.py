"""Readiness never turns missing or unavailable prerequisites into cleared work."""

import pytest

from src.bootstrap import build_checklist_service
from src.modules.auth.domain.models import Role
from src.modules.content_governance.contracts import TRANSFER_SALE_SUBTYPE_ID, CompilerInput
from src.platform.request_context import RequestContext
from tests.db.test_scoped_fact_review import matter as matter


@pytest.mark.parametrize("condition", ["no-checklist", "grouping", "failure", "unavailable"])
async def test_readiness_keeps_pending_and_unknown_dependencies(db_session, matter, condition):
    from sqlalchemy import select

    from src.bootstrap import build_readiness_service
    from src.modules.document.infrastructure.orm import SourceFileRow

    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-readiness")
    if condition != "no-checklist":
        await build_checklist_service(db_session).compile_snapshot(
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            compiler_input=CompilerInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID),
            actor_id=ctx.actor_id,
            correlation_id=ctx.correlation_id,
        )
    if condition in {"grouping", "failure"}:
        source = (
            (
                await db_session.execute(
                    select(SourceFileRow).where(SourceFileRow.matter_id == matter.matter_id)
                )
            )
            .scalars()
            .first()
        )
        source.state = "PROCESSED" if condition == "grouping" else "PROCESSING_FAILED"
        source.page_count = 1
        await db_session.flush()
    service = build_readiness_service(db_session)
    if condition == "unavailable":

        class Broken:
            async def readiness_dependencies(self, ctx, matter_id):
                raise RuntimeError("synthetic unavailable")

        service._sources = {"documents": Broken()}
    view = await service.evaluate(ctx, matter.matter_id)
    assert view.state in {"blocked", "unknown"}
    assert view.next_action != "draft-review"
    if condition in {"no-checklist", "unavailable"}:
        assert view.state == "unknown"
        assert any(dep.state == "unknown" for dep in view.dependencies)
    else:
        assert any(
            dep.category == ("grouping" if condition == "grouping" else "processing")
            for dep in view.dependencies
        )


async def test_detached_check_readiness_keeps_issues_without_actionable_rerun(db_session, matter):
    from src.bootstrap import build_check_service, build_matter_scope_service
    from src.modules.check.application.readiness import CheckReadinessReader
    from tests.db.test_scoped_checks import scopes, seed_blocking_issue

    ctx, tx, first, second = await scopes(db_session, matter)
    checks = build_check_service(db_session)
    run = await checks.run_checks(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-detached-readiness",
        transaction_id=tx.id,
        subject_id=first,
        association_version=tx.version,
    )
    await seed_blocking_issue(checks, run)
    await build_matter_scope_service(db_session).create_transaction(
        ctx,
        matter.matter_id,
        transaction_id=tx.id,
        expected_version=tx.version,
        parcel_subject_ids=(second,),
        party_roles=(),
        key="synthetic-detach-readiness",
    )
    deps = await CheckReadinessReader(checks, checks._scopes).readiness_dependencies(
        ctx, matter.matter_id
    )
    assert any(dep.category == "checks" and dep.state == "pending" for dep in deps)
    assert any(dep.category == "issues" and dep.references for dep in deps)
    assert not any(
        ref.kind == "check" and ref.subject_id == first for dep in deps for ref in dep.references
    )


@pytest.mark.parametrize("category", ["classification", "facts"])
@pytest.mark.parametrize("checklist_state", ["absent", "unavailable"])
async def test_known_pending_work_remains_actionable_without_checklist(
    db_session, matter, category, checklist_state
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from src.bootstrap import build_readiness_service
    from src.modules.task.contracts import ReadinessDependency, ReadinessReference

    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-next-action")
    service = build_readiness_service(db_session)
    service._sources = {
        "documents" if category == "classification" else "facts": SimpleNamespace(
            readiness_dependencies=AsyncMock(
                return_value=(
                    ReadinessDependency(
                        category,
                        "pending",
                        (
                            ReadinessReference(
                                "document" if category == "classification" else "fact",
                                "synthetic-pending",
                                version=2,
                            ),
                        ),
                    ),
                )
            )
        )
    }
    if checklist_state == "unavailable":
        service._checklist.get_checklist = AsyncMock(
            side_effect=RuntimeError("Synthetic checklist outage")
        )
    view = await service.evaluate(ctx, matter.matter_id)
    assert (
        view.state == "unknown"
        and view.requirement_total is None
        and view.requirement_completed is None
    )
    assert view.next_action == category
    assert any(
        dep.category == "requirements" and dep.state == "unknown" for dep in view.dependencies
    )


async def test_pure_unavailable_work_has_unknown_recovery_action(db_session, matter):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from src.bootstrap import build_readiness_service

    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-unknown-action")
    service = build_readiness_service(db_session)
    service._sources = {
        "documents": SimpleNamespace(
            readiness_dependencies=AsyncMock(side_effect=RuntimeError("Synthetic unavailable"))
        )
    }
    view = await service.evaluate(ctx, matter.matter_id)
    assert view.state == "unknown" and view.next_action == "unknown"
    assert view.requirement_total is None and view.requirement_completed is None
