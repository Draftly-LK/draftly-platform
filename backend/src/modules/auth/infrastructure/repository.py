"""SQLAlchemy repository implementations for the auth module.

Repositories convert between ORM rows and domain entities. They never expose
ORM objects outside this file — the application layer sees only domain types.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.domain.models import (
    AccountStatus,
    Invitation,
    MatterMembership,
    MatterMembershipRole,
    Organisation,
    OrganisationMembership,
    OrgRole,
    OrgStatus,
    OrgType,
    Role,
    User,
    UserIdentity,
)
from src.modules.auth.infrastructure.orm import (
    InvitationRow,
    MatterMembershipRow,
    OrganisationMembershipRow,
    OrganisationRow,
    UserIdentityRow,
    UserRow,
)

# ── Mapper helpers ────────────────────────────────────────────────────────────


def _row_to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        display_name=row.display_name,
        account_status=AccountStatus(row.account_status),
        role=Role(row.role) if row.role else None,
        notary_registration=row.notary_registration,
        jurisdiction=row.jurisdiction,
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


def _row_to_org(row: OrganisationRow) -> Organisation:
    return Organisation(
        id=row.id,
        name=row.name,
        type=OrgType(row.type),
        status=OrgStatus(row.status),
        created_at=row.created_at,
    )


def _row_to_org_membership(row: OrganisationMembershipRow) -> OrganisationMembership:
    return OrganisationMembership(
        organisation_id=row.organisation_id,
        user_id=row.user_id,
        org_role=OrgRole(row.org_role),
        joined_at=row.joined_at,
    )


def _row_to_matter_membership(row: MatterMembershipRow) -> MatterMembership:
    return MatterMembership(
        organisation_id=row.organisation_id,
        matter_id=row.matter_id,
        user_id=row.user_id,
        role=MatterMembershipRole(row.role),
        assigned_at=row.assigned_at,
    )


# ── Repository classes ────────────────────────────────────────────────────────


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return _row_to_user(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        # Email lookup is only used as a secondary index; identity resolution
        # uses (issuer, subject) as the primary key (auth-service.md §3).
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


class SqlOrganisationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, org_id: str) -> Organisation | None:
        row = await self._session.get(OrganisationRow, org_id)
        return _row_to_org(row) if row else None


class SqlOrganisationMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(self, org_id: str, user_id: str) -> OrganisationMembership | None:
        stmt = select(OrganisationMembershipRow).where(
            OrganisationMembershipRow.organisation_id == org_id,
            OrganisationMembershipRow.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_org_membership(row) if row else None

    async def create(self, membership: OrganisationMembership) -> OrganisationMembership:
        row = OrganisationMembershipRow(
            id=str(uuid.uuid4()),
            organisation_id=membership.organisation_id,
            user_id=membership.user_id,
            org_role=membership.org_role.value,
        )
        self._session.add(row)
        await self._session.flush()
        return membership

    async def count_owners(self, org_id: str) -> int:
        stmt = select(OrganisationMembershipRow).where(
            OrganisationMembershipRow.organisation_id == org_id,
            OrganisationMembershipRow.org_role == OrgRole.OWNER.value,
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())


class SqlMatterMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, org_id: str, user_id: str) -> list[MatterMembership]:
        stmt = select(MatterMembershipRow).where(
            MatterMembershipRow.organisation_id == org_id,
            MatterMembershipRow.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return [_row_to_matter_membership(r) for r in result.scalars()]

    async def find(self, org_id: str, matter_id: str, user_id: str) -> MatterMembership | None:
        stmt = select(MatterMembershipRow).where(
            MatterMembershipRow.organisation_id == org_id,
            MatterMembershipRow.matter_id == matter_id,
            MatterMembershipRow.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_matter_membership(row) if row else None

    async def create(self, membership: MatterMembership) -> MatterMembership:
        row = MatterMembershipRow(
            id=str(uuid.uuid4()),
            organisation_id=membership.organisation_id,
            matter_id=membership.matter_id,
            user_id=membership.user_id,
            role=membership.role.value,
        )
        self._session.add(row)
        await self._session.flush()
        return membership

    async def update(self, membership: MatterMembership) -> MatterMembership:
        stmt = select(MatterMembershipRow).where(
            MatterMembershipRow.organisation_id == membership.organisation_id,
            MatterMembershipRow.matter_id == membership.matter_id,
            MatterMembershipRow.user_id == membership.user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError("Matter membership not found for update")
        row.role = membership.role.value
        await self._session.flush()
        return membership


class SqlInvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_active(self, org_id: str, email: str) -> Invitation | None:
        stmt = select(InvitationRow).where(
            InvitationRow.organisation_id == org_id,
            InvitationRow.email == email,
            InvitationRow.accepted_at.is_(None),
            InvitationRow.is_expired.is_(False),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return Invitation(
            id=row.id,
            organisation_id=row.organisation_id,
            email=row.email,
            assigned_role=Role(row.assigned_role),
            invited_by=row.invited_by,
            expires_at=row.expires_at,
            accepted_at=row.accepted_at,
        )

    async def mark_accepted(self, invitation_id: str) -> None:
        row = await self._session.get(InvitationRow, invitation_id)
        if row:
            row.accepted_at = datetime.now(tz=UTC)
            await self._session.flush()
