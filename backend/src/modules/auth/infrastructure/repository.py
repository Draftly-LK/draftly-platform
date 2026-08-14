"""SQLAlchemy repository implementations for the auth module.

Repositories convert between ORM rows and domain entities. They never expose
ORM objects outside this file — the application layer sees only domain types.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.domain.models import AccountStatus, Role, User, UserIdentity
from src.modules.auth.infrastructure.orm import UserIdentityRow, UserRow


def _row_to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        display_name=row.display_name,
        account_status=AccountStatus(row.account_status),
        role=Role(row.role) if row.role else None,
        notary_registration=row.notary_registration,
        jurisdiction=row.jurisdiction,
        certificate_valid_until=row.certificate_valid_until,
        created_at=row.created_at,
        updated_at=row.updated_at,
        qualifications=row.qualifications,
        professional_titles=row.professional_titles,
        address_line1=row.address_line1,
        address_line2=row.address_line2,
        phone=row.phone,
    )


def _row_to_identity(row: UserIdentityRow) -> UserIdentity:
    return UserIdentity(
        user_id=row.user_id,
        provider=row.provider,
        issuer=row.issuer,
        subject=row.subject,
        verified_email=row.verified_email,
        linked_at=row.linked_at,
    )


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return _row_to_user(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(UserRow)
            .join(UserIdentityRow, UserIdentityRow.user_id == UserRow.id)
            .where(UserIdentityRow.verified_email == email)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_user(row) if row else None

    async def create(self, user: User) -> User:
        row = UserRow(
            id=user.id,
            display_name=user.display_name,
            account_status=user.account_status.value,
            role=user.role.value if user.role else None,
            notary_registration=user.notary_registration,
            jurisdiction=user.jurisdiction,
            certificate_valid_until=user.certificate_valid_until,
            qualifications=user.qualifications,
            professional_titles=user.professional_titles,
            address_line1=user.address_line1,
            address_line2=user.address_line2,
            phone=user.phone,
        )
        self._session.add(row)
        await self._session.flush()
        return user

    async def update(self, user: User) -> User:
        row = await self._session.get(UserRow, user.id)
        if row is None:
            raise ValueError(f"User {user.id} not found for update")
        row.display_name = user.display_name
        row.account_status = user.account_status.value
        row.role = user.role.value if user.role else None
        row.notary_registration = user.notary_registration
        row.jurisdiction = user.jurisdiction
        row.certificate_valid_until = user.certificate_valid_until
        row.qualifications = user.qualifications
        row.professional_titles = user.professional_titles
        row.address_line1 = user.address_line1
        row.address_line2 = user.address_line2
        row.phone = user.phone
        await self._session.flush()
        return user


class SqlUserIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_subject(self, issuer: str, subject: str) -> UserIdentity | None:
        stmt = select(UserIdentityRow).where(
            UserIdentityRow.issuer == issuer,
            UserIdentityRow.subject == subject,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_identity(row) if row else None

    async def find_by_verified_email(self, email: str) -> UserIdentity | None:
        stmt = select(UserIdentityRow).where(UserIdentityRow.verified_email == email).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_identity(row) if row else None

    async def create(self, identity: UserIdentity) -> UserIdentity:
        row = UserIdentityRow(
            id=str(uuid.uuid4()),
            user_id=identity.user_id,
            provider=identity.provider,
            issuer=identity.issuer,
            subject=identity.subject,
            verified_email=identity.verified_email,
        )
        self._session.add(row)
        await self._session.flush()
        return identity
