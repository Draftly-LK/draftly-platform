"""SQLAlchemy ORM models for the auth module.

Every row that belongs to a customer carries organisation_id (plan §5.3 #10).
The ORM models are infrastructure detail — application services work with domain
entities from domain/models.py and never import from here directly.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.platform.db.session import Base


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notary_registration: Mapped[str | None] = mapped_column(String(64), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    qualifications: Mapped[str | None] = mapped_column(String(512), nullable=True)
    professional_titles: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Practising certificate currency — checked by require_practising_notary
    certificate_valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    identities: Mapped[list[UserIdentityRow]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    org_memberships: Mapped[list[OrganisationMembershipRow]] = relationship(back_populates="user")


class UserIdentityRow(Base):
    """External identity link keyed by (issuer, subject).

    The unique key is (issuer, subject), never email alone.
    """

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_user_identity_issuer_subject"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # "clerk"
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[UserRow] = relationship(back_populates="identities")


class OrganisationRow(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="firm")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list[OrganisationMembershipRow]] = relationship(
        back_populates="organisation"
    )


class OrganisationMembershipRow(Base):
    """Maps a user to an organisation with an org-level role (owner | member).

    MVP: OrgRole is owner | member only.
    """

    __tablename__ = "organisation_memberships"
    __table_args__ = (
        UniqueConstraint("organisation_id", "user_id", name="uq_org_membership_org_user"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    org_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="member"
    )  # "owner" | "member"
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organisation: Mapped[OrganisationRow] = relationship(back_populates="memberships")
    user: Mapped[UserRow] = relationship(back_populates="org_memberships")


class MatterMembershipRow(Base):
    """Join: (user, matter, role) within one organisation.

    organisation_id is always stored so that cross-organisation queries can be
    prevented at the database level.
    """

    __tablename__ = "matter_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "matter_id",
            "user_id",
            name="uq_matter_membership_org_matter_user",
        ),
        Index("ix_matter_memberships_org_user", "organisation_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="assignee")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InvitationRow(Base):
    """Admin-issued invitation required to activate a pending account."""

    __tablename__ = "invitations"
    __table_args__ = (Index("ix_invitations_org_email", "organisation_id", "email"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_role: Mapped[str] = mapped_column(String(32), nullable=False)
    invited_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
