"""SQLAlchemy ORM models for the auth module.

The ORM models are infrastructure detail — application services work with domain
entities from domain/models.py and never import from here directly.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
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


class UserIdentityRow(Base):
    """External identity link keyed by (issuer, subject).

    The unique key is (issuer, subject), never email alone.
    """

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_user_identity_issuer_subject"),
        Index(
            "uq_user_identities_verified_email",
            "verified_email",
            unique=True,
            postgresql_where=text("verified_email IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[UserRow] = relationship(back_populates="identities")
