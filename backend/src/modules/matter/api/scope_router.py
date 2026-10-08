"""Bounded matter subject and transaction APIs; all identity values stay elsewhere."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.matter.application.scope_service import MatterScopeService
from src.modules.matter.contracts import SubjectKind, TransactionPartyRole, TransactionRole
from src.platform.api.pagination import Page, PageInfo, decode_cursor, encode_cursor
from src.platform.db.idempotency import IdempotencyKeyRequiredError
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.request_context import RequestContext

router = APIRouter(tags=["matter scope"])


class ScopeModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class SubjectRequest(ScopeModel):
    kind: SubjectKind


class SubjectRead(SubjectRequest):
    id: str
    user_id: str
    matter_id: str
    ordinal: int


class PartyRoleRequest(ScopeModel):
    subject_id: str = Field(max_length=64)
    role: TransactionRole


class TransactionRequest(ScopeModel):
    parcel_subject_ids: list[str] = Field(default_factory=list, max_length=100)
    party_roles: list[PartyRoleRequest] = Field(default_factory=list, max_length=100)


class TransactionRead(TransactionRequest):
    id: str
    user_id: str
    matter_id: str
    ordinal: int
    version: int


def get_scope_service(session: AsyncSession = Depends(get_db)) -> MatterScopeService:
    from src.bootstrap import build_matter_scope_service

    return build_matter_scope_service(session)


def require_scope_key(
    key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
) -> str:
    if not key:
        raise IdempotencyKeyRequiredError()
    return key


@router.get("/matters/{matter_id}/subjects", response_model=Page[SubjectRead])
async def list_subjects(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterScopeService = Depends(get_scope_service),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> Page[SubjectRead]:
    payload = decode_cursor(cursor) if cursor else {}
    items = await service.list_subjects(ctx, matter_id, limit=limit, after=payload.get("id"))
    return Page(
        items=[SubjectRead.model_validate(asdict(item)) for item in items],
        page=PageInfo(
            limit=limit,
            has_more=len(items) == limit,
            next_cursor=encode_cursor({"id": items[-1].id}) if len(items) == limit else None,
        ),
    )


@router.post("/matters/{matter_id}/subjects", response_model=SubjectRead, status_code=201)
async def create_subject(
    matter_id: str,
    body: SubjectRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterScopeService = Depends(get_scope_service),
    key: str = Depends(require_scope_key),
    uow: UnitOfWork = Depends(get_uow),
) -> SubjectRead:
    _ = uow
    item = await service.create_subject(ctx, matter_id, kind=body.kind, key=key)
    return SubjectRead.model_validate(asdict(item))


@router.get("/matters/{matter_id}/transactions", response_model=Page[TransactionRead])
async def list_transactions(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterScopeService = Depends(get_scope_service),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> Page[TransactionRead]:
    payload = decode_cursor(cursor) if cursor else {}
    items = await service.list_transactions(ctx, matter_id, limit=limit, after=payload.get("id"))
    return Page(
        items=[TransactionRead.model_validate(asdict(item)) for item in items],
        page=PageInfo(
            limit=limit,
            has_more=len(items) == limit,
            next_cursor=encode_cursor({"id": items[-1].id}) if len(items) == limit else None,
        ),
    )


@router.post("/matters/{matter_id}/transactions", response_model=TransactionRead, status_code=201)
async def create_transaction(
    matter_id: str,
    body: TransactionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterScopeService = Depends(get_scope_service),
    key: str = Depends(require_scope_key),
    uow: UnitOfWork = Depends(get_uow),
) -> TransactionRead:
    _ = uow
    item = await service.create_transaction(
        ctx,
        matter_id,
        key=key,
        parcel_subject_ids=tuple(body.parcel_subject_ids),
        party_roles=tuple(TransactionPartyRole(r.subject_id, r.role) for r in body.party_roles),
    )
    response.headers["ETag"] = f'"{item.version}"'
    return TransactionRead.model_validate(asdict(item))


@router.post(
    "/matters/{matter_id}/transactions/{transaction_id}/associations",
    response_model=TransactionRead,
)
async def associate_transaction(
    matter_id: str,
    transaction_id: str,
    body: TransactionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterScopeService = Depends(get_scope_service),
    expected_version: int = Depends(require_if_match),
    key: str = Depends(require_scope_key),
    uow: UnitOfWork = Depends(get_uow),
) -> TransactionRead:
    _ = uow
    item = await service.create_transaction(
        ctx,
        matter_id,
        key=key,
        parcel_subject_ids=tuple(body.parcel_subject_ids),
        party_roles=tuple(TransactionPartyRole(r.subject_id, r.role) for r in body.party_roles),
        transaction_id=transaction_id,
        expected_version=expected_version,
    )
    response.headers["ETag"] = f'"{item.version}"'
    return TransactionRead.model_validate(asdict(item))
