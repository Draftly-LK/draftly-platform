"""Party API router — authenticates and parses only.

No authorisation decision is made here and nothing in a request body is ever
treated as identity: `user_id` comes from the `RequestContext` the auth
dependency built, so a forged `userId`, `role`, or capability in a body is
simply never read.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from src.api.deps import get_party_service, get_request_context
from src.modules.party.api.schemas import (
    BeneficialOwnerReadSchema,
    CddAssessmentReadSchema,
    CreatePartyRequest,
    DuplicateCandidateSchema,
    DuplicateProbeRequest,
    DuplicateProbeResponse,
    IdentityEvidenceReadSchema,
    IdentityValueReadSchema,
    MatterPartyReadSchema,
    MergePartiesRequest,
    PagedResponse,
    PageSchema,
    PartyListItemSchema,
    PartyReadSchema,
    PatchPartyRequest,
    RecordBeneficialOwnerRequest,
    RecordCddRequest,
    RecordIdentityEvidenceRequest,
    RecordScreeningRequest,
    ScreeningResultListItemSchema,
    ScreeningResultReadSchema,
)
from src.modules.party.application.party_service import PartyRead, PartyService
from src.modules.party.domain.models import IdentityEvidence, ScreeningMatchDetail
from src.modules.party.ports import (
    CreatePartyInput,
    PartyListFilter,
    RecordCddInput,
    RecordIdentityEvidenceInput,
    RecordScreeningInput,
)
from src.platform.errors import PreconditionFailedError, PreconditionRequiredError
from src.platform.pagination import decode_cursor
from src.platform.request_context import RequestContext

router = APIRouter(tags=["parties"])


def _require_if_match(if_match: str | None) -> int:
    """428 when absent, 412 when unparseable — never a 500 (api-conventions.md §3)."""
    if if_match is None:
        raise PreconditionRequiredError("If-Match header is required.")
    candidate = if_match.strip().removeprefix("W/").strip('"')
    try:
        return int(candidate)
    except ValueError as exc:
        raise PreconditionFailedError("If-Match must be the integer resource version.") from exc


def _party_to_read(read: PartyRead) -> PartyReadSchema:
    party = read.party
    return PartyReadSchema(
        id=party.id,
        party_kind=party.party_kind.value,
        display_name=party.display_name,
        name_parts=party.name_parts,
        former_names=party.former_names,
        date_of_birth=party.date_of_birth,
        registration_number=party.registration_number,
        nationality=party.nationality,
        residency_status=party.residency_status,
        addresses=party.addresses,
        contact_points=party.contact_points,
        risk_rating=party.risk_rating.value,
        screening_status=read.screening_status.value if read.screening_status else None,
        confidentiality_level=party.confidentiality_level.value,
        effective_confidentiality=read.effective_confidentiality.value,
        merged_into_party_id=party.merged_into_party_id,
        version=party.version,
        created_at=party.created_at,
        updated_at=party.updated_at,
        duplicate_candidates=[
            DuplicateCandidateSchema(
                party_id=c.party_id,
                display_name=c.display_name,
                match_reason=c.match_reason,
                strength=c.strength,
            )
            for c in read.duplicate_candidates
        ],
    )


def _evidence_to_read(evidence: IdentityEvidence) -> IdentityEvidenceReadSchema:
    return IdentityEvidenceReadSchema(
        id=evidence.id,
        party_id=evidence.party_id,
        evidence_kind=evidence.evidence_kind.value,
        identifier_last4=evidence.identifier_last4,
        issued_on=evidence.issued_on,
        expires_on=evidence.expires_on,
        issuing_authority=evidence.issuing_authority,
        document_id=evidence.document_id,
        document_version_id=evidence.document_version_id,
        evidence_span=evidence.evidence_span,
        state=evidence.state.value,
        supersedes_evidence_id=evidence.supersedes_evidence_id,
        version=evidence.version,
    )


@router.get("/parties", response_model=PagedResponse[PartyListItemSchema])
async def list_parties(
    q: str | None = Query(default=None),
    limit: int = Query(default=50),
    cursor: str | None = Query(default=None),
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> PagedResponse[PartyListItemSchema]:
    result = await service.list_parties(
        ctx,
        PartyListFilter(query=q, limit=limit, cursor=decode_cursor(cursor)),
    )
    return PagedResponse[PartyListItemSchema](
        items=[
            PartyListItemSchema(
                id=p.id,
                display_name=p.display_name,
                party_kind=p.party_kind.value,
                # A list never carries a compliance signal, and never a full
                # identifier — only `identifierLast4` on the evidence endpoints.
                screening_status=None,
                version=p.version,
            )
            for p in result.items
        ],
        page=PageSchema(
            next_cursor=result.page.next_cursor,
            has_more=result.page.has_more,
            limit=result.page.limit,
        ),
    )


@router.post("/parties", response_model=PartyReadSchema)
async def create_party(
    body: CreatePartyRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> PartyReadSchema:
    read = await service.create_party(
        ctx,
        CreatePartyInput(
            party_kind=body.party_kind,
            display_name=body.display_name,
            name_parts=body.name_parts,
            former_names=body.former_names,
            date_of_birth=body.date_of_birth,
            registration_number=body.registration_number,
            nationality=body.nationality,
            residency_status=body.residency_status,
            addresses=body.addresses,
            contact_points=body.contact_points,
            confidentiality_level=body.confidentiality_level,
        ),
    )
    return _party_to_read(read)


@router.get("/parties/{party_id}", response_model=PartyReadSchema)
async def get_party(
    party_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> PartyReadSchema:
    read = await service.get_party(ctx, party_id)
    return _party_to_read(read)


@router.patch("/parties/{party_id}", response_model=PartyReadSchema)
async def patch_party(
    party_id: str,
    body: PatchPartyRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> PartyReadSchema:
    read = await service.update_party(
        ctx,
        party_id,
        display_name=body.display_name,
        expected_version=_require_if_match(if_match),
    )
    return _party_to_read(read)


@router.post("/parties/{party_id}/identity-evidence", response_model=IdentityEvidenceReadSchema)
async def record_identity_evidence(
    party_id: str,
    body: RecordIdentityEvidenceRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> IdentityEvidenceReadSchema:
    result = await service.record_identity_evidence(
        ctx,
        party_id,
        RecordIdentityEvidenceInput(
            evidence_kind=body.evidence_kind,
            identifier_value=body.identifier_value,
            issued_on=body.issued_on,
            expires_on=body.expires_on,
            issuing_authority=body.issuing_authority,
            document_id=body.document_id,
            document_version_id=body.document_version_id,
            evidence_span=body.evidence_span,
            supersedes_evidence_id=body.supersedes_evidence_id,
        ),
    )
    return _evidence_to_read(result.evidence)


@router.get(
    "/parties/{party_id}/identity-evidence", response_model=list[IdentityEvidenceReadSchema]
)
async def list_identity_evidence(
    party_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> list[IdentityEvidenceReadSchema]:
    items = await service.list_identity_evidence(ctx, party_id)
    return [_evidence_to_read(item) for item in items]


@router.post(
    "/parties/{party_id}/identity-evidence/{evidence_id}/verification",
    response_model=IdentityEvidenceReadSchema,
)
async def verify_identity_evidence(
    party_id: str,
    evidence_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> IdentityEvidenceReadSchema:
    result = await service.verify_identity_evidence(
        ctx,
        party_id,
        evidence_id,
        expected_version=_require_if_match(if_match),
    )
    return _evidence_to_read(result.evidence)


@router.get(
    "/parties/{party_id}/identity-evidence/{evidence_id}/identifier",
    response_model=IdentityValueReadSchema,
)
async def read_identity_value(
    party_id: str,
    evidence_id: str,
    purpose: str = Query(..., min_length=1),
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> IdentityValueReadSchema:
    result = await service.read_identity_value(ctx, party_id, evidence_id, purpose=purpose)
    return IdentityValueReadSchema(
        evidence_id=result.evidence_id,
        identifier_value=result.identifier_value,
    )


@router.post("/parties/{party_id}/beneficial-owners", response_model=BeneficialOwnerReadSchema)
async def record_beneficial_owner(
    party_id: str,
    body: RecordBeneficialOwnerRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> BeneficialOwnerReadSchema:
    owner = await service.record_beneficial_owner(
        ctx,
        party_id,
        owner_party_id=body.owner_party_id,
        ownership_kind=body.ownership_kind,
        percentage=body.percentage,
        evidence_refs=body.evidence_refs,
    )
    return BeneficialOwnerReadSchema(
        id=owner.id,
        party_id=owner.party_id,
        owner_party_id=owner.owner_party_id,
        ownership_kind=owner.ownership_kind.value,
        percentage=owner.percentage,
        evidence_refs=owner.evidence_refs,
        state=owner.state.value,
    )


@router.post("/parties/{party_id}/cdd", response_model=CddAssessmentReadSchema)
async def record_cdd(
    party_id: str,
    body: RecordCddRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> CddAssessmentReadSchema:
    assessment = await service.record_cdd(
        ctx,
        party_id,
        RecordCddInput(
            matter_id=body.matter_id,
            level=body.level,
            risk_factors=body.risk_factors,
            outcome=body.outcome,
            review_due_on=body.review_due_on,
            policy_version=body.policy_version,
        ),
    )
    return CddAssessmentReadSchema(
        id=assessment.id,
        party_id=assessment.party_id,
        matter_id=assessment.matter_id,
        level=assessment.level.value,
        risk_factors=assessment.risk_factors,
        outcome=assessment.outcome.value,
        assessed_by=assessment.assessed_by,
        assessed_at=assessment.assessed_at,
        review_due_on=assessment.review_due_on,
        policy_version=assessment.policy_version,
        version=assessment.version,
    )


@router.post("/parties/{party_id}/screening", response_model=ScreeningResultReadSchema)
async def record_screening(
    party_id: str,
    body: RecordScreeningRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> ScreeningResultReadSchema:
    match_detail = None
    if body.match_detail is not None:
        match_detail = ScreeningMatchDetail(
            screening_result_id="",
            provider_payload=body.match_detail.provider_payload,
            match_narrative=body.match_detail.match_narrative,
            list_entry_ref=body.match_detail.list_entry_ref,
        )
    result = await service.record_screening(
        ctx,
        party_id,
        RecordScreeningInput(
            list_version=body.list_version,
            provider_ref=body.provider_ref,
            outcome=body.outcome,
            match_count=body.match_count,
            match_detail=match_detail,
        ),
    )
    return ScreeningResultReadSchema(
        id=result.id,
        party_id=result.party_id,
        list_version=result.list_version,
        provider_ref=result.provider_ref,
        outcome=result.outcome.value,
        match_count=result.match_count,
        created_at=result.created_at,
    )


@router.get(
    "/parties/{party_id}/screening",
    response_model=list[ScreeningResultListItemSchema],
)
async def list_screening_results(
    party_id: str,
    include_detail: bool = Query(default=False),
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> list[ScreeningResultListItemSchema]:
    """404 for anyone without `compliance.view` — restricted rows are invisible."""
    results = await service.list_screening_results(
        ctx,
        party_id,
        include_restricted_detail=include_detail,
    )
    return [
        ScreeningResultListItemSchema(
            id=item["id"],
            outcome=item["outcome"],
            match_count=item["match_count"],
            list_version=item["list_version"],
            created_at=item["created_at"],
        )
        for item in results
    ]


@router.post("/parties/duplicate-probe", response_model=DuplicateProbeResponse)
async def duplicate_probe(
    body: DuplicateProbeRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> DuplicateProbeResponse:
    """Surfaces candidates. Nothing here merges anything — see POST /parties/merges."""
    result = await service.detect_duplicates(
        ctx,
        body.party_id,
        identifier_value=body.identifier_value,
    )
    return DuplicateProbeResponse(
        candidates=[
            DuplicateCandidateSchema(
                party_id=c.party_id,
                display_name=c.display_name,
                match_reason=c.match_reason,
                strength=c.strength,
            )
            for c in result.candidates
        ]
    )


@router.post("/parties/merges", response_model=PartyReadSchema)
async def merge_parties(
    body: MergePartiesRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> PartyReadSchema:
    """Administrator-only, pointer-based, never a delete (party-service.md §5)."""
    read = await service.merge_parties(
        ctx,
        body.source_party_id,
        body.target_party_id,
        body.reason,
        expected_version=_require_if_match(if_match),
    )
    return _party_to_read(read)


@router.get("/matters/{matter_id}/parties", response_model=list[MatterPartyReadSchema])
async def list_matter_parties(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: PartyService = Depends(get_party_service),
) -> list[MatterPartyReadSchema]:
    parties = await service.list_matter_parties(ctx, matter_id)
    return [
        MatterPartyReadSchema(
            id=p.id,
            display_name=p.display_name,
            party_kind=p.party_kind.value,
        )
        for p in parties
    ]
