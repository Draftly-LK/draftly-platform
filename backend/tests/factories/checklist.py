"""Checklist snapshots and items, complete by default."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from src.modules.content_governance.contracts import (
    ApplicabilityStatus,
    CollectionStatus,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    ResolutionStatus,
)
from src.modules.task.domain.models import ChecklistItem, ChecklistSnapshot
from tests.factories.constants import MATTER_A, NOW, USER_A

REQUIREMENT = "R_C00_MATTER_AND_CLIENT_REFERENCE"
MODULE = "C00_MATTER_ADMIN"


def checklist_snapshot(**overrides: Any) -> ChecklistSnapshot:
    snapshot = ChecklistSnapshot(
        id="cls_synthetic_0001",
        user_id=USER_A,
        matter_id=MATTER_A,
        compiler_version="synthetic",
        taxonomy_version="synthetic",
        checklist_version="synthetic",
        rule_pack_version="synthetic",
        fingerprint="fp_synthetic_0001",
        module_definition_ids=(MODULE,),
        created_at=NOW,
        created_by=USER_A,
    )
    return replace(snapshot, **overrides)


def checklist_item(**overrides: Any) -> ChecklistItem:
    created_at: datetime = overrides.pop("created_at", NOW)
    item = ChecklistItem(
        id="cli_synthetic_0001",
        user_id=USER_A,
        matter_id=MATTER_A,
        snapshot_id="cls_synthetic_0001",
        requirement_definition_id=REQUIREMENT,
        module_definition_id=MODULE,
        inclusion_reason="OFFICE_ADDED",
        inclusion_trigger_id=None,
        applicability=ApplicabilityStatus.REQUIRED,
        collection=CollectionStatus.REQUESTED,
        digital_review=DigitalReviewStatus.UNREVIEWED,
        physical_original=PhysicalOriginalStatus.NOT_REQUIRED,
        currency=CurrencyStatus.CURRENT,
        consistency=ConsistencyStatus.MATCHED,
        resolution=ResolutionStatus.OPEN,
        created_at=created_at,
        updated_at=created_at,
    )
    return replace(item, **overrides)
