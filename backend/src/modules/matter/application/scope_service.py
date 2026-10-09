"""Explicit, audited matter subject and transaction associations."""

from dataclasses import asdict

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import CAP_AUDIT_READ, CAP_MATTER_ROUTE
from src.modules.matter.contracts import (
    MatterReadPort,
    MatterSubjectReference,
    MatterTransactionReference,
    ScopeAssociationInvalidationPort,
    SubjectKind,
    TransactionPartyRole,
    require_rta_capability,
)
from src.modules.matter.ports import MatterScopeRepository
from src.platform.errors import DomainRuleError, NotFoundError
from src.platform.idempotency import IdempotencyPort, fingerprint
from src.platform.ids import new_id
from src.platform.request_context import RequestContext


class MatterScopeService:
    def __init__(
        self,
        repository: MatterScopeRepository,
        matters: MatterReadPort,
        audit: AuditPort,
        replay: IdempotencyPort,
        invalidation: ScopeAssociationInvalidationPort | None = None,
    ) -> None:
        self._repo, self._matters, self._audit, self._replay = repository, matters, audit, replay
        self._invalidation = invalidation

    async def authorize(
        self, ctx: RequestContext, matter_id: str, capability: str = CAP_AUDIT_READ
    ) -> None:
        matter = await self._matters.get_access_summary(ctx.actor_id, matter_id)
        if matter is None:
            raise NotFoundError()
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=matter,
            capability=capability,
        )

    async def lock(self, ctx: RequestContext, matter_id: str) -> None:
        await self.authorize(ctx, matter_id)
        await self._repo.lock(ctx.actor_id, matter_id)

    async def validate_scope(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        transaction_id: str | None,
        subject_id: str | None,
        subject_kind: SubjectKind | None = None,
    ) -> None:
        await self.authorize(ctx, matter_id)
        if transaction_id:
            await self.get_transaction(ctx, matter_id, transaction_id)
        if subject_id:
            subject = await self._repo.subject(ctx.actor_id, matter_id, subject_id)
            if subject is None:
                raise NotFoundError()
            if subject_kind is not None and subject.kind != subject_kind:
                raise DomainRuleError("The subject kind does not match this fact.")

    async def get_transaction(
        self, ctx: RequestContext, matter_id: str, transaction_id: str
    ) -> MatterTransactionReference:
        await self.authorize(ctx, matter_id)
        result = await self._repo.transaction(ctx.actor_id, matter_id, transaction_id)
        if result is None:
            raise NotFoundError()
        return result

    async def list_subjects(
        self, ctx: RequestContext, matter_id: str, *, limit: int = 50, after: str | None = None
    ) -> list[MatterSubjectReference]:
        await self.authorize(ctx, matter_id)
        if not 1 <= limit <= 100:
            raise DomainRuleError()
        return await self._repo.subjects(ctx.actor_id, matter_id, limit, after)

    async def list_transactions(
        self, ctx: RequestContext, matter_id: str, *, limit: int = 50, after: str | None = None
    ) -> list[MatterTransactionReference]:
        await self.authorize(ctx, matter_id)
        if not 1 <= limit <= 100:
            raise DomainRuleError()
        return await self._repo.transactions(ctx.actor_id, matter_id, limit, after)

    async def create_subject(
        self, ctx: RequestContext, matter_id: str, *, kind: SubjectKind, key: str
    ) -> MatterSubjectReference:
        await self.authorize(ctx, matter_id, CAP_MATTER_ROUTE)
        await self.lock(ctx, matter_id)
        if kind not in ("party", "parcel") or not key:
            raise DomainRuleError()
        route = f"/matters/{matter_id}/subjects"
        request_hash = fingerprint({"kind": kind})
        replay = await self._replay.find(
            user_id=ctx.actor_id, route=route, key=key, request_hash=request_hash
        )
        if replay:
            result = await self._repo.subject(ctx.actor_id, matter_id, str(replay["id"]))
            if result is None:
                raise NotFoundError()
            return result
        result = await self._repo.create_subject(ctx.actor_id, matter_id, kind)
        await self._record(ctx, matter_id, result.id, "subject@1")
        await self._replay.store(
            record_id=new_id("idem"),
            user_id=ctx.actor_id,
            route=route,
            key=key,
            request_hash=request_hash,
            response={"id": result.id},
        )
        return result

    async def create_transaction(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        key: str,
        parcel_subject_ids: tuple[str, ...] = (),
        party_roles: tuple[TransactionPartyRole, ...] = (),
        transaction_id: str | None = None,
        expected_version: int | None = None,
    ) -> MatterTransactionReference:
        await self.authorize(ctx, matter_id, CAP_MATTER_ROUTE)
        await self.lock(ctx, matter_id)
        if (
            not key
            or len(set(parcel_subject_ids)) != len(parcel_subject_ids)
            or len(set(party_roles)) != len(party_roles)
        ):
            raise DomainRuleError()
        for subject_id in parcel_subject_ids:
            await self.validate_scope(
                ctx, matter_id, transaction_id=None, subject_id=subject_id, subject_kind="parcel"
            )
        for role in party_roles:
            if role.role not in (
                "transferor",
                "transferee",
                "owner",
                "donor",
                "donee",
                "lessor",
                "lessee",
                "mortgagor",
                "mortgagee",
                "other",
            ):
                raise DomainRuleError()
            await self.validate_scope(
                ctx,
                matter_id,
                transaction_id=None,
                subject_id=role.subject_id,
                subject_kind="party",
            )
        route = f"/matters/{matter_id}/transactions/{transaction_id or 'new'}"
        request_hash = fingerprint(
            {
                "parcels": parcel_subject_ids,
                "roles": [asdict(role) for role in party_roles],
                "expectedVersion": expected_version,
            }
        )
        replay = await self._replay.find(
            user_id=ctx.actor_id, route=route, key=key, request_hash=request_hash
        )
        if replay:
            return MatterTransactionReference(
                id=str(replay["id"]),
                user_id=ctx.actor_id,
                matter_id=matter_id,
                ordinal=int(replay["ordinal"]),
                parcel_subject_ids=parcel_subject_ids,
                party_roles=party_roles,
                version=int(replay["version"]),
            )
        previous = (
            await self.get_transaction(ctx, matter_id, transaction_id) if transaction_id else None
        )
        result = await self._repo.save_transaction(
            ctx.actor_id,
            matter_id,
            parcel_subject_ids,
            party_roles,
            transaction_id,
            expected_version,
        )
        if self._invalidation and previous and result.version != previous.version:
            await self._invalidation.invalidate_scope(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                transaction_id=result.id,
                actor_id=ctx.actor_id,
                correlation_id=ctx.correlation_id,
            )
        await self._record(ctx, matter_id, result.id, f"transaction@{result.version}")
        await self._replay.store(
            record_id=new_id("idem"),
            user_id=ctx.actor_id,
            route=route,
            key=key,
            request_hash=request_hash,
            response={"id": result.id, "ordinal": result.ordinal, "version": result.version},
        )
        return result

    async def _record(
        self, ctx: RequestContext, matter_id: str, target_id: str, after: str
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="matter.scope-associated",
                target_type="matter",
                target_id=target_id,
                after_ref=after,
                correlation_id=ctx.correlation_id,
            )
        )
