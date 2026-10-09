"""Matter-owned scope persistence and transaction-level serialization."""

from dataclasses import asdict
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.matter.contracts import (
    MatterSubjectReference,
    MatterTransactionReference,
    SubjectKind,
    TransactionPartyRole,
    TransactionRole,
)
from src.modules.matter.infrastructure.orm import (
    MatterRow,
    MatterSubjectRow,
    MatterTransactionRevisionRow,
    MatterTransactionRow,
)
from src.platform.errors import NotFoundError, PreconditionFailedError
from src.platform.ids import new_id


def _subject(row: MatterSubjectRow) -> MatterSubjectReference:
    return MatterSubjectReference(
        row.id, row.user_id, row.matter_id, cast(SubjectKind, row.kind), row.ordinal
    )


def _transaction(row: MatterTransactionRow) -> MatterTransactionReference:
    return MatterTransactionReference(
        row.id,
        row.user_id,
        row.matter_id,
        row.ordinal,
        tuple(row.parcel_subject_ids),
        tuple(
            TransactionPartyRole(role["subject_id"], cast(TransactionRole, role["role"]))
            for role in row.party_roles
        ),
        row.version,
    )


class SqlMatterScopeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock(self, user_id: str, matter_id: str) -> None:
        row = (
            await self._session.execute(
                select(MatterRow.id)
                .where(MatterRow.user_id == user_id, MatterRow.id == matter_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError()

    async def subject(
        self, user_id: str, matter_id: str, subject_id: str
    ) -> MatterSubjectReference | None:
        row = (
            await self._session.execute(
                select(MatterSubjectRow).where(
                    MatterSubjectRow.user_id == user_id,
                    MatterSubjectRow.matter_id == matter_id,
                    MatterSubjectRow.id == subject_id,
                )
            )
        ).scalar_one_or_none()
        return _subject(row) if row else None

    async def transaction(
        self, user_id: str, matter_id: str, transaction_id: str
    ) -> MatterTransactionReference | None:
        row = (
            await self._session.execute(
                select(MatterTransactionRow).where(
                    MatterTransactionRow.user_id == user_id,
                    MatterTransactionRow.matter_id == matter_id,
                    MatterTransactionRow.id == transaction_id,
                )
            )
        ).scalar_one_or_none()
        return _transaction(row) if row else None

    async def subjects(
        self, user_id: str, matter_id: str, limit: int, after: str | None
    ) -> list[MatterSubjectReference]:
        query = select(MatterSubjectRow).where(
            MatterSubjectRow.user_id == user_id, MatterSubjectRow.matter_id == matter_id
        )
        if after:
            query = query.where(MatterSubjectRow.id > after)
        return [
            _subject(row)
            for row in (
                await self._session.execute(query.order_by(MatterSubjectRow.id).limit(limit))
            ).scalars()
        ]

    async def transactions(
        self, user_id: str, matter_id: str, limit: int, after: str | None
    ) -> list[MatterTransactionReference]:
        query = select(MatterTransactionRow).where(
            MatterTransactionRow.user_id == user_id, MatterTransactionRow.matter_id == matter_id
        )
        if after:
            query = query.where(MatterTransactionRow.id > after)
        return [
            _transaction(row)
            for row in (
                await self._session.execute(query.order_by(MatterTransactionRow.id).limit(limit))
            ).scalars()
        ]

    async def create_subject(
        self, user_id: str, matter_id: str, kind: SubjectKind
    ) -> MatterSubjectReference:
        ordinal = (
            await self._session.execute(
                select(func.max(MatterSubjectRow.ordinal)).where(
                    MatterSubjectRow.user_id == user_id,
                    MatterSubjectRow.matter_id == matter_id,
                    MatterSubjectRow.kind == kind,
                )
            )
        ).scalar_one_or_none() or 0
        row = MatterSubjectRow(
            id=new_id("subject"),
            user_id=user_id,
            matter_id=matter_id,
            kind=kind,
            ordinal=ordinal + 1,
            created_by=user_id,
        )
        self._session.add(row)
        await self._session.flush()
        return _subject(row)

    async def save_transaction(
        self,
        user_id: str,
        matter_id: str,
        parcels: tuple[str, ...],
        roles: tuple[TransactionPartyRole, ...],
        transaction_id: str | None = None,
        expected_version: int | None = None,
    ) -> MatterTransactionReference:
        if transaction_id:
            row = (
                await self._session.execute(
                    select(MatterTransactionRow).where(
                        MatterTransactionRow.user_id == user_id,
                        MatterTransactionRow.matter_id == matter_id,
                        MatterTransactionRow.id == transaction_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise NotFoundError()
            if row.version != expected_version:
                raise PreconditionFailedError(currentVersion=row.version)
            row.version += 1
        else:
            ordinal = (
                await self._session.execute(
                    select(func.max(MatterTransactionRow.ordinal)).where(
                        MatterTransactionRow.user_id == user_id,
                        MatterTransactionRow.matter_id == matter_id,
                    )
                )
            ).scalar_one_or_none() or 0
            row = MatterTransactionRow(
                id=new_id("transaction"),
                user_id=user_id,
                matter_id=matter_id,
                ordinal=ordinal + 1,
                version=1,
                created_by=user_id,
            )
            self._session.add(row)
        row.parcel_subject_ids = list(parcels)
        row.party_roles = [asdict(role) for role in roles]
        await self._session.flush()
        self._session.add(
            MatterTransactionRevisionRow(
                id=new_id("scope_revision"),
                user_id=user_id,
                matter_id=matter_id,
                transaction_id=row.id,
                version=row.version,
                parcel_subject_ids=row.parcel_subject_ids,
                party_roles=row.party_roles,
                actor_id=user_id,
            )
        )
        await self._session.flush()
        return _transaction(row)
