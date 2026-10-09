"""Form drafting API router.

```text
POST /api/v1/matters/{id}/forms                 generate a working draft
GET  /api/v1/matters/{id}/forms                 paginated, newest first
GET  /api/v1/forms/{id}                         ETag = version
POST /api/v1/forms/{id}/field-decisions         confirm / correct / clear one binding
POST /api/v1/forms/{id}/preflight               deterministic gate report
POST /api/v1/forms/{id}/mark-stale              re-evaluate against current inputs
```

Generation is synchronous. It is not the long-running kind of work
api-conventions §6 defers to a job: nothing here rasterizes, extracts, or
renders — a draft is a binding record over facts a lawyer has already confirmed.

Forms are addressed without their matter in the path (§12.4), so those routes
resolve the form under the caller's ``user_id`` first and authorise against the
matter it turns out to belong to. A 404 covers both "absent" and "not yours".

A 2xx from any of these routes means a record was written, never that the draft
may be executed or registered: `preflight.registrationReady` is false for every
form in this repository, because no template here is a lawyer-approved
production rendering (§9.5).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.content_governance.contracts import (
    CAP_AUDIT_READ,
    CAP_FORM_FIELD_DECIDE,
    CAP_FORM_GENERATE,
)
from src.modules.draft.api.schemas import (
    FactCandidateRead,
    FieldDecisionRequest,
    FormFieldRead,
    FormScopeRead,
    GeneratedFormListRead,
    GeneratedFormRead,
    GeneratedFormSummaryRead,
    GenerateFormRequest,
    MarkStaleRequest,
    PageInfo,
    PreflightItemRead,
    PreflightRead,
)
from src.modules.draft.application.draft_service import DraftService, FormFieldView, FormView
from src.modules.draft.contracts import FormScope
from src.modules.draft.domain.models import GeneratedForm, StaleReason
from src.modules.draft.domain.policies import FieldDecisionAction, PreflightResult
from src.modules.matter.contracts import MatterAccessSummary, require_rta_capability
from src.modules.matter.domain.errors import MatterNotFoundError
from src.platform.db.idempotency import (
    IdempotencyKeyRequiredError,
    SqlIdempotencyStore,
    request_fingerprint,
)
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DomainRuleError
from src.platform.ids import new_id
from src.platform.request_context import RequestContext

router = APIRouter(tags=["forms"])


def get_draft_service(session: AsyncSession = Depends(get_db)) -> DraftService:
    from src.bootstrap import build_draft_service

    return build_draft_service(session)


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
) -> MatterAccessSummary:
    matter = await _matter(ctx, matter_id, session)
    require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=matter,
        capability=capability,
    )
    return matter


def _action(raw: str) -> FieldDecisionAction:
    try:
        return FieldDecisionAction(raw)
    except ValueError:
        raise DomainRuleError(
            f"'{raw}' is not a field-decision action.",
            field="action",
            permitted=sorted(action.value for action in FieldDecisionAction),
        )


def _stale_reason(raw: str | None) -> StaleReason | None:
    if raw is None:
        return None
    try:
        return StaleReason(raw)
    except ValueError:
        raise DomainRuleError(
            f"'{raw}' is not a staleness reason.",
            field="reason",
            permitted=sorted(reason.value for reason in StaleReason),
        )


def _to_field_read(view: FormFieldView, missing_cause: str | None = None) -> FormFieldRead:
    form_field, mapping = view.field, view.mapping
    return FormFieldRead(
        id=form_field.id,
        missing_cause=missing_cause
        if form_field.is_unresolved or missing_cause == "stale"
        else None,
        field_id=form_field.field_id,
        label_key=mapping.label_key,
        section_key=mapping.section_key,
        order=form_field.order,
        critical=form_field.critical,
        required=form_field.required,
        display_value=view.display_value,
        rendered_value=form_field.rendered_value,
        unresolved_reason=(
            form_field.unresolved_reason.value if form_field.unresolved_reason else None
        ),
        fact_id=form_field.fact_id,
        fact_version=form_field.fact_version,
        evidence_reference_ids=list(form_field.evidence_reference_ids),
        transformation_id=form_field.transformation_id,
        allowed_transformation_ids=list(mapping.allowed_transformation_ids),
        validation_rule_ids=list(mapping.validation_rule_ids),
        lawyer_authored_allowed=mapping.lawyer_authored_allowed,
        human_confirmation_required=mapping.human_confirmation_required,
        ai_suggested=view.ai_suggested,
        awaiting_confirmation=form_field.awaiting_confirmation,
        review_decision_id=form_field.review_decision_id,
        reviewed_by=form_field.reviewed_by,
        reviewed_at=form_field.reviewed_at.isoformat() if form_field.reviewed_at else None,
        conflicting_candidates=[
            FactCandidateRead(
                fact_id=candidate.fact_id,
                fact_type_id=candidate.fact_type_id,
                value=candidate.value,
                version=candidate.version,
                status=candidate.status.value,
                evidence_reference_ids=list(candidate.evidence_reference_ids),
                model_reported_confidence=candidate.model_reported_confidence,
            )
            for candidate in view.conflicting_candidates
        ],
    )


def _to_preflight_read(result: PreflightResult) -> PreflightRead:
    return PreflightRead(
        form_id=result.form_id,
        template_id=result.template_id,
        template_version=result.template_version,
        rule_pack_version=result.rule_pack_version,
        blocking=[
            PreflightItemRead(
                code=item.code.value,
                subject_id=item.subject_id,
                explanation_key=item.explanation_key,
                gate=item.gate.value,
                blocking=item.blocking,
            )
            for item in result.blocking
        ],
        warnings=[
            PreflightItemRead(
                code=item.code.value,
                subject_id=item.subject_id,
                explanation_key=item.explanation_key,
                gate=item.gate.value,
                blocking=item.blocking,
            )
            for item in result.warnings
        ],
        review_ready=result.review_ready,
        approval_ready=result.approval_ready,
        registration_ready=result.registration_ready,
        template_registration_ready_capable=result.template_registration_ready_capable,
        watermark_key=result.watermark_key,
        evaluated_at=result.evaluated_at.isoformat(),
    )


def _to_form_read(view: FormView) -> GeneratedFormRead:
    form, template = view.form, view.template
    return GeneratedFormRead(
        id=form.id,
        matter_id=form.matter_id,
        template_id=form.template_id,
        template_version=form.template_version,
        title_key=template.title_key,
        form_number=template.form_number,
        namespace=template.namespace.value,
        form_version=form.form_version,
        state=form.state.value,
        subtype_id=form.subtype_id,
        rule_pack_version=form.rule_pack_version,
        draft_artifact_hash=form.draft_artifact_hash,
        approved_artifact_hash=form.approved_artifact_hash,
        approval_id=form.approval_id,
        stale_reason=form.stale_reason,
        scope=FormScopeRead(**asdict(form.scope)) if form.scope else None,
        predecessor_form_id=form.predecessor_form_id,
        # §9.5 — the recorded defects of the source text travel with the draft,
        # so a lawyer approving one sees the variance rather than discovering it.
        known_source_defect_keys=list(template.known_source_defect_keys),
        fields=[
            _to_field_read(field_view, form.missing_causes.get(field_view.field.field_id))
            for field_view in view.fields
        ],
        preflight=_to_preflight_read(view.preflight),
        created_at=form.created_at.isoformat(),
        updated_at=form.updated_at.isoformat(),
        version=form.version,
    )


def _to_summary_read(form: GeneratedForm) -> GeneratedFormSummaryRead:
    return GeneratedFormSummaryRead(
        id=form.id,
        matter_id=form.matter_id,
        template_id=form.template_id,
        template_version=form.template_version,
        form_version=form.form_version,
        state=form.state.value,
        subtype_id=form.subtype_id,
        rule_pack_version=form.rule_pack_version,
        draft_artifact_hash=form.draft_artifact_hash,
        approved_artifact_hash=form.approved_artifact_hash,
        approval_id=form.approval_id,
        stale_reason=form.stale_reason,
        scope=FormScopeRead(**asdict(form.scope)) if form.scope else None,
        predecessor_form_id=form.predecessor_form_id,
        created_at=form.created_at.isoformat(),
        updated_at=form.updated_at.isoformat(),
        version=form.version,
    )


@router.post("/matters/{matter_id}/forms", response_model=GeneratedFormRead, status_code=201)
async def generate_form(
    matter_id: str,
    body: GenerateFormRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    ctx: RequestContext = Depends(get_request_context),
    service: DraftService = Depends(get_draft_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
) -> GeneratedFormRead:
    """Generate a working draft from the confirmed subtype and the fact tier.

    The subtype must be lawyer-confirmed and the template must be one the
    subtype selects; both are read from the server's own record, never from the
    body. A 201 records a draft for internal review — it is not a statement that
    the instrument is fit to execute or register (§9.4).
    """
    _ = uow
    matter = await _authorize(ctx, matter_id, session, CAP_FORM_GENERATE)
    if not idempotency_key:
        raise IdempotencyKeyRequiredError()
    store = SqlIdempotencyStore(session)
    route = f"forms:create:{matter_id}"
    digest = request_fingerprint(body.model_dump(mode="json"))
    prior = await store.find(
        user_id=ctx.actor_id, route=route, key=idempotency_key, request_hash=digest
    )
    if prior:
        result = GeneratedFormRead.model_validate(prior)
        response.headers["ETag"] = f'"{result.version}"'
        return result
    view = await service.generate_form(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        subtype_id=matter.subtype_id,
        subtype_decision_status=matter.subtype_decision_status,
        template_id=body.template_id,
        scope=FormScope(**body.scope.model_dump()) if body.scope else None,
        predecessor_form_id=body.predecessor_form_id,
    )
    result = _to_form_read(view)
    await store.store(
        record_id=new_id("idem"),
        user_id=ctx.actor_id,
        route=route,
        key=idempotency_key,
        request_hash=digest,
        response=result.model_dump(mode="json", by_alias=True),
    )
    response.headers["ETag"] = f'"{view.form.version}"'
    return result


@router.get("/matters/{matter_id}/forms", response_model=GeneratedFormListRead)
async def list_forms(
    matter_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: DraftService = Depends(get_draft_service),
    session: AsyncSession = Depends(get_db),
) -> GeneratedFormListRead:
    """Every form version on the matter, newest first. Nothing is ever deleted."""
    await _authorize(ctx, matter_id, session, CAP_AUDIT_READ)
    forms, next_cursor = await service.list_forms(
        user_id=ctx.actor_id, matter_id=matter_id, limit=limit, cursor=cursor
    )
    return GeneratedFormListRead(
        items=[_to_summary_read(form) for form in forms],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
    )


@router.get("/forms/{form_id}", response_model=GeneratedFormRead)
async def get_form(
    form_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: DraftService = Depends(get_draft_service),
    session: AsyncSession = Depends(get_db),
) -> GeneratedFormRead:
    """The whole binding record, with a freshly evaluated preflight beside it."""
    view = await service.get_form(user_id=ctx.actor_id, form_id=form_id)
    await _authorize(ctx, view.form.matter_id, session, CAP_AUDIT_READ)
    response.headers["ETag"] = f'"{view.form.version}"'
    return _to_form_read(view)


@router.post("/forms/{form_id}/field-decisions", response_model=GeneratedFormRead)
async def decide_field(
    form_id: str,
    body: FieldDecisionRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    ctx: RequestContext = Depends(get_request_context),
    service: DraftService = Depends(get_draft_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> GeneratedFormRead:
    """Confirm, correct, or clear one field binding.

    A critical field is never corrected here: its value comes from a
    lawyer-confirmed canonical fact with evidence, and the domain refuses the
    attempt with its own code (§9.3).
    """
    _ = uow
    view = await service.get_form(user_id=ctx.actor_id, form_id=form_id)
    await _authorize(ctx, view.form.matter_id, session, CAP_FORM_FIELD_DECIDE)
    if not idempotency_key:
        raise IdempotencyKeyRequiredError()
    store = SqlIdempotencyStore(session)
    route = f"forms:decide:{form_id}"
    digest = request_fingerprint(
        {**body.model_dump(mode="json"), "expectedVersion": expected_version}
    )
    prior = await store.find(
        user_id=ctx.actor_id, route=route, key=idempotency_key, request_hash=digest
    )
    if prior:
        result = GeneratedFormRead.model_validate(prior)
        response.headers["ETag"] = f'"{result.version}"'
        return result
    updated = await service.decide_field(
        user_id=ctx.actor_id,
        form_id=form_id,
        field_id=body.field_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        action=_action(body.action),
        value=body.value,
        reason=body.reason,
    )
    result = _to_form_read(updated)
    await store.store(
        record_id=new_id("idem"),
        user_id=ctx.actor_id,
        route=route,
        key=idempotency_key,
        request_hash=digest,
        response=result.model_dump(mode="json", by_alias=True),
    )
    response.headers["ETag"] = f'"{updated.form.version}"'
    return result


@router.post("/forms/{form_id}/preflight", response_model=GeneratedFormRead)
async def run_preflight(
    form_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: DraftService = Depends(get_draft_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
) -> GeneratedFormRead:
    """Run the deterministic gate report over all four sources plus the template.

    A POST because the run is recorded as an audit event, not because it changes
    the form: the report never advances a state, and `registrationReady` is
    false for every template in this repository whatever the fields say.
    """
    _ = uow
    view = await service.get_form(user_id=ctx.actor_id, form_id=form_id)
    await _authorize(ctx, view.form.matter_id, session, CAP_FORM_GENERATE)
    result = await service.run_preflight(
        user_id=ctx.actor_id,
        form_id=form_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
    )
    response.headers["ETag"] = f'"{result.form.version}"'
    return _to_form_read(result)


@router.post("/forms/{form_id}/mark-stale", response_model=GeneratedFormRead)
async def mark_stale(
    form_id: str,
    body: MarkStaleRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: DraftService = Depends(get_draft_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> GeneratedFormRead:
    """Re-evaluate the form against its current inputs (§9.5, §10.5, §10.7).

    An approved form is never rewritten: it records that it went stale and keeps
    its bindings exactly as approved. Amending it is a new form version.
    """
    _ = uow
    view = await service.get_form(user_id=ctx.actor_id, form_id=form_id)
    await _authorize(ctx, view.form.matter_id, session, CAP_FORM_GENERATE)
    updated = await service.mark_stale(
        user_id=ctx.actor_id,
        form_id=form_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        declared=_stale_reason(body.reason),
    )
    response.headers["ETag"] = f'"{updated.form.version}"'
    return _to_form_read(updated)
