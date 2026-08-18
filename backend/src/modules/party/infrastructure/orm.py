"""SQLAlchemy ORM models for the party module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class PartyRow(Base):
    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    party_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    name_parts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    former_names: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(128), nullable=True)
    residency_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    addresses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    contact_points: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    risk_rating: Mapped[str] = mapped_column(String(32), nullable=False, default="unassessed")
    screening_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not-run")
    confidentiality_level: Mapped[str] = mapped_column(
        String(32), nullable=False, default="standard"
    )
    merged_into_party_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_parties_user_display_name", "user_id", "display_name"),
        Index("ix_parties_user_registration", "user_id", "registration_number"),
    )


class IdentityEvidenceRow(Base):
    __tablename__ = "identity_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    party_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised tenant key: every party-owned row carries it so that every
    # query can filter on user_id first (party-service.md §9).
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    identifier_blind_index: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    identifier_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_span: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="recorded")
    supersedes_evidence_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    __table_args__ = (
        Index("ix_identity_evidence_user_blind", "user_id", "identifier_blind_index"),
    )


class BeneficialOwnerRow(Base):
    __tablename__ = "beneficial_owners"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    party_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised tenant key: every party-owned row carries it so that every
    # query can filter on user_id first (party-service.md §9).
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_party_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ownership_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    percentage: Mapped[float | None] = mapped_column(nullable=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    determined_by: Mapped[str] = mapped_column(String(64), nullable=False)
    determined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="recorded")


class CddAssessmentRow(Base):
    __tablename__ = "cdd_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    party_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised tenant key: every party-owned row carries it so that every
    # query can filter on user_id first (party-service.md §9).
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    matter_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_factors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class ScreeningResultRow(Base):
    __tablename__ = "screening_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    party_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised tenant key: every party-owned row carries it so that every
    # query can filter on user_id first (party-service.md §9).
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    list_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    match_count: Mapped[int] = mapped_column(nullable=False, default=0)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disposition_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidentiality_level: Mapped[str] = mapped_column(
        String(32), nullable=False, default="restricted-compliance"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScreeningMatchDetailRow(Base):
    __tablename__ = "screening_match_detail"

    screening_result_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("screening_results.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    match_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    list_entry_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
