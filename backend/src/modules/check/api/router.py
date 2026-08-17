"""Check and legal-issue API router.

```text
POST /api/v1/matters/{id}/checks/run                  run every V0 check
GET  /api/v1/matters/{id}/checks                      results, newest first
GET  /api/v1/matters/{id}/issues                      filter by severity/state
POST /api/v1/matters/{id}/issues/{issueId}/decisions  record a disposition
```

A run is synchronous and returns its results directly. It is not the
long-running kind of work api-conventions §6 defers to a job: the checks are
pure comparisons over facts a lawyer has already confirmed, and no OCR,
retrieval, or rendering happens here.

Reading results and issues needs `rta.audit.read`, which every workflow role
with standing on the matter holds. Running the checks needs `rta.issue.triage`,
because a run creates legal issues on the file. Accepting risk needs the
narrower capability the blocker kind implies, which is why the decisions route
loads the issue before it authorizes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.check.api.schemas import (
    CheckResultListRead,
    CheckResultRead,
    CheckRunRead,
    FactVersionPinRead,
    IssueDecisionRequest,
    IssueGatesRead,
    LegalIssueListRead,
    LegalIssueRead,
    PageInfo,
    RunChecksRequest,
)
from src.modules.check.application.check_service import CheckRunResult, CheckService
from src.modules.check.contracts import IssueGateSummary
from src.modules.check.domain.models import CheckResult, LegalIssue
from src.modules.check.domain.policies import permitted_states
from src.modules.check.domain.runners import is_provisional
from src.modules.content_governance.contracts import (
    CAP_AUDIT_READ,
    CAP_ISSUE_ACCEPT_RISK,
    CAP_ISSUE_OVERRIDE_OFFICE_POLICY,
    CAP_ISSUE_TRIAGE,
    BlockerKind,
    IssueSeverity,
    IssueState,
    RtaWorkflowRole,
    get_check,
)
from src.modules.matter.contracts import MatterAccessSummary, require_rta_capability
from src.modules.matter.domain.errors import MatterNotFoundError
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["checks"])


def get_check_service(session: AsyncSession = Depends(get_db)) -> CheckService:
    from src.bootstrap import build_check_service

    return build_check_service(session)


async def _matter(
    ctx: RequestContext, matter_id: str, session: AsyncSession
) -> MatterAccessSummary:
    """Resolve the matter through its own module. Absent or foreign is 404."""
    from src.bootstrap import build_matter_service

    summary = await build_matter_service(session).get_access_summary(ctx.actor_id, matter_id)
    if summary is None:
        raise MatterNotFoundError()
    return summary


async def _authorize(
    ctx: RequestContext, matter_id: str, session: AsyncSession, capability: str
) -> RtaWorkflowRole:
    return require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=await _matter(ctx, matter_id, session),
        capability=capability,
    )


def _decision_capability(issue: LegalIssue, target_state: IssueState) -> str:
    """The capability this particular disposition needs (§7.3).

    Accepting an office-policy blocker is the office administrator's call;
    accepting a professional-judgment one is the responsible lawyer's. Everything
    else is ordinary triage. A statutory blocker has no capability at all — the
    domain refuses it after this point, whatever the caller holds.
    """
    if target_state is not IssueState.ACCEPTED_RISK:
        return CAP_ISSUE_TRIAGE
    if issue.blocker_kind is BlockerKind.OFFICE_POLICY:
        return CAP_ISSUE_OVERRIDE_OFFICE_POLICY
    return CAP_ISSUE_ACCEPT_RISK


def _issue_state(raw: str) -> IssueState:
    try:
        return IssueState(raw)
    except ValueError:
        raise DomainRuleError(
            f"'{raw}' is not a legal-issue state.",
            field="state",
            permitted=sorted(state.value for state in IssueState),
        )


def _optional_state(raw: str | None) -> IssueState | None:
    return _issue_state(raw) if raw is not None else None


def _optional_severity(raw: str | None) -> IssueSeverity | None:
    if raw is None:
        return None
    try:
        return IssueSeverity(raw)
    except ValueError:
        raise DomainRuleError(
            f"'{raw}' is not an issue severity.",
            field="severity",
            permitted=sorted(severity.value for severity in IssueSeverity),
        )


def _to_result_read(result: CheckResult) -> CheckResultRead:
    definition = get_check(result.check_definition_id)
    return CheckResultRead(
        id=result.id,
        check_definition_id=result.check_definition_id,
        check_definition_version=result.check_definition_version,
        run_id=result.run_id,
        outcome=result.outcome.value,
        default_severity=result.default_severity.value,
        explanation_key=result.explanation_key,
        # A definition retired between runs leaves the result readable without
        # its catalogue metadata, rather than hiding the run that produced it.
        safety_rule_key=definition.safety_rule_key if definition else None,
        label_key=definition.label_key if definition else None,
        comparison_key=definition.comparison_key if definition else None,
        source_record_ids=(
            [citation.source_record_id for citation in definition.sources] if definition else []
        ),
        failure_blocker_kind=definition.failure_blocker_kind.value if definition else None,
        input_fact_versions=[
            FactVersionPinRead(fact_id=pin.fact_id, version=pin.version)
            for pin in result.input_fact_versions
        ],
        evidence_reference_ids=list(result.evidence_reference_ids),
        requires_human_conclusion=result.requires_human_conclusion,
        provisional=is_provisional(result.explanation_key),
        created_at=result.created_at.isoformat(),
    )


def _to_issue_read(issue: LegalIssue) -> LegalIssueRead:
    return LegalIssueRead(
        id=issue.id,
        matter_id=issue.matter_id,
        check_id=issue.check_id,
        issue_type_id=issue.issue_type_id,
        severity=issue.severity.value,
        blocker_kind=issue.blocker_kind.value,
        state=issue.state.value,
        summary_key=issue.summary_key,
        source_record_ids=list(issue.source_record_ids),
        evidence_reference_ids=list(issue.evidence_reference_ids),
        assigned_to=issue.assigned_to,
        resolution_decision_id=issue.resolution_decision_id,
        resolution_reason=issue.resolution_reason,
        permitted_states=sorted(state.value for state in permitted_states(issue.blocker_kind)),
        created_at=issue.created_at.isoformat(),
        updated_at=issue.updated_at.isoformat(),
        version=issue.version,
    )


def _to_gates_read(gates: IssueGateSummary) -> IssueGatesRead:
    return IssueGatesRead(
        blocks_draft_generation=gates.blocks_draft_generation,
        blocks_approval=gates.blocks_approval,
        blocks_registration_ready_export=gates.blocks_registration_ready_export,
        open_statutory_blocker_ids=list(gates.open_statutory_blocker_ids),
        open_blocking_issue_ids=list(gates.open_blocking_issue_ids),
    )


def _to_run_read(run: CheckRunResult) -> CheckRunRead:
    return CheckRunRead(
        run_id=run.run_id,
        results=[_to_result_read(result) for result in run.results],
        raised_issues=[_to_issue_read(issue) for issue in run.raised_issues],
        gates=_to_gates_read(run.gates),
    )


@router.post("/matters/{matter_id}/checks/run", response_model=CheckRunRead, status_code=201)
async def run_checks(
    matter_id: str,
    body: RunChecksRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: CheckService = Depends(get_check_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
) -> CheckRunRead:
    """Run the V0 checks, pinning the rule pack and the input fact versions.

    A 201 means the run was recorded, not that the matter is sound: §7.1 makes a
    ``PASS`` a statement about one encoded comparison and nothing more.
    """
    _ = uow
    matter = await _matter(ctx, matter_id, session)
    require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=matter,
        capability=CAP_ISSUE_TRIAGE,
    )
    run = await service.run_checks(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        subtype_id=matter.subtype_id,
        search_currency_max_age_days=body.search_currency_max_age_days,
    )
    return _to_run_read(run)


@router.get("/matters/{matter_id}/checks", response_model=CheckResultListRead)
async def list_checks(
    matter_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: CheckService = Depends(get_check_service),
    session: AsyncSession = Depends(get_db),
) -> CheckResultListRead:
    """Every result of every run, newest first. Superseded runs stay readable."""
    await _authorize(ctx, matter_id, session, CAP_AUDIT_READ)
    results, next_cursor = await service.list_results(
        user_id=ctx.actor_id, matter_id=matter_id, limit=limit, cursor=cursor
    )
    return CheckResultListRead(
        items=[_to_result_read(result) for result in results],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
    )


@router.get("/matters/{matter_id}/issues", response_model=LegalIssueListRead)
async def list_issues(
    matter_id: str,
    severity: str | None = None,
    state: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: CheckService = Depends(get_check_service),
    session: AsyncSession = Depends(get_db),
) -> LegalIssueListRead:
    """The gates are returned beside the page so a filtered view cannot mislead.

    Filtering to ``WARNING`` must not make the screen look unblocked, so the
    three gates are always computed over every issue on the matter.
    """
    await _authorize(ctx, matter_id, session, CAP_AUDIT_READ)
    issues, next_cursor = await service.list_issues(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        severity=_optional_severity(severity),
        state=_optional_state(state),
        limit=limit,
        cursor=cursor,
    )
    return LegalIssueListRead(
        items=[_to_issue_read(issue) for issue in issues],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
        gates=_to_gates_read(await service.gates(ctx.actor_id, matter_id)),
    )


@router.post(
    "/matters/{matter_id}/issues/{issue_id}/decisions",
    response_model=LegalIssueRead,
)
async def decide_issue(
    matter_id: str,
    issue_id: str,
    body: IssueDecisionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: CheckService = Depends(get_check_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> LegalIssueRead:
    """Record one disposition. The deciding lawyer is the authenticated actor.

    The issue is loaded before the capability is chosen because the capability
    depends on the blocker kind — and a statutory blocker is refused by the
    domain after that, so no capability grants it.
    """
    _ = uow
    matter = await _matter(ctx, matter_id, session)
    issue = await service.get_issue(user_id=ctx.actor_id, matter_id=matter_id, issue_id=issue_id)
    target_state = _issue_state(body.state)
    role = require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=matter,
        capability=_decision_capability(issue, target_state),
    )
    saved = await service.decide_issue(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        issue_id=issue_id,
        actor_id=ctx.actor_id,
        actor_workflow_role=role,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        target_state=target_state,
        reason=body.reason,
        new_evidence_reference_ids=tuple(body.evidence_reference_ids),
        assigned_to=body.assigned_to,
    )
    response.headers["ETag"] = f'"{saved.version}"'
    return _to_issue_read(saved)
