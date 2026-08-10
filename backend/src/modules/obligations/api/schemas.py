"""Obligations API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LawyerConfirmationRead(BaseModel):
    status: str
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    reason: str | None = None
    original_due_at: datetime | None = None


class ObligationRead(BaseModel):
    id: str
    organisation_id: str
    scope: str
    matter_id: str | None = None
    obligation_type: str
    obligation_class: str
    label_key: str
    due_at: datetime
    timezone: str
    hardness: str
    status: str
    assignee_user_id: str
    confidentiality_level: str
    lawyer_confirmation: LawyerConfirmationRead
    calculation_explanation: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class PageMeta(BaseModel):
    next_cursor: str | None = Field(serialization_alias="nextCursor", default=None)
    has_more: bool = Field(serialization_alias="hasMore")
    limit: int


class ObligationListResponse(BaseModel):
    items: list[ObligationRead]
    page: PageMeta


class CreateObligationRequest(BaseModel):
    scope: str
    obligation_type: str
    obligation_class: str
    label_key: str
    due_at: datetime
    timezone: str = "Asia/Colombo"
    hardness: str = "soft"
    assignee_user_id: str
    matter_id: str | None = None
    legal_authority_ref: str | None = None
    confidentiality_level: str = "standard"


class ConfirmDeadlineRequest(BaseModel):
    due_at: datetime | None = None
    reason: str | None = None


class CompleteObligationRequest(BaseModel):
    completion_evidence_ref: str | None = None


class CancelObligationRequest(BaseModel):
    reason: str
