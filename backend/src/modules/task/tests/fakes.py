"""In-memory checklist repository and audit double. No database; synthetic values only.

The double keeps the real repository's contract where the service relies on it:
tenant-scoped reads, a version check on ``update_item``, newest-first
``latest_snapshot``, and link supersession that preserves history.
"""

from __future__ import annotations

from dataclasses import replace

from src.modules.auth.ports import AuditEventInput
from src.modules.content_governance.contracts import DigitalReviewStatus
from src.modules.task.domain.errors import ChecklistItemStaleError
from src.modules.task.domain.models import ChecklistItem, ChecklistSnapshot, SatisfactionLink

USER_ID = "usr_synthetic"
MATTER_ID = "mat_synthetic"
CORRELATION = "corr_synthetic"


class InMemoryChecklistRepository:
    def __init__(self) -> None:
        self.snapshots: list[ChecklistSnapshot] = []
        self.items: dict[str, ChecklistItem] = {}
        self.links: list[SatisfactionLink] = []

    async def create_snapshot(self, snapshot: ChecklistSnapshot) -> ChecklistSnapshot:
        self.snapshots.append(snapshot)
        return snapshot

    async def get_snapshot(self, user_id: str, snapshot_id: str) -> ChecklistSnapshot | None:
        return next(
            (s for s in self.snapshots if s.user_id == user_id and s.id == snapshot_id), None
        )

    async def latest_snapshot(self, user_id: str, matter_id: str) -> ChecklistSnapshot | None:
        owned = [s for s in self.snapshots if s.user_id == user_id and s.matter_id == matter_id]
        return owned[-1] if owned else None

    async def find_snapshot_by_fingerprint(
        self, user_id: str, matter_id: str, fingerprint: str
    ) -> ChecklistSnapshot | None:
        return next(
            (
                s
                for s in self.snapshots
                if (s.user_id, s.matter_id, s.fingerprint) == (user_id, matter_id, fingerprint)
            ),
            None,
        )

    async def create_items(self, items: list[ChecklistItem]) -> list[ChecklistItem]:
        for item in items:
            self.items[item.id] = replace(item)
        return items

    async def list_items(self, user_id: str, snapshot_id: str) -> list[ChecklistItem]:
        return [
            replace(i)
            for i in self.items.values()
            if i.user_id == user_id and i.snapshot_id == snapshot_id
        ]

    async def get_item(self, user_id: str, item_id: str) -> ChecklistItem | None:
        item = self.items.get(item_id)
        return replace(item) if item is not None and item.user_id == user_id else None

    async def update_item(self, item: ChecklistItem, expected_version: int) -> ChecklistItem:
        stored = self.items[item.id]
        if stored.version != expected_version:
            raise ChecklistItemStaleError(expectedVersion=expected_version)
        saved = replace(item, version=expected_version + 1)
        self.items[item.id] = saved
        return replace(saved)

    async def reviewed_requirement_ids(self, user_id: str, matter_id: str) -> list[str]:
        return sorted(
            {
                i.requirement_definition_id
                for i in self.items.values()
                if i.user_id == user_id
                and i.matter_id == matter_id
                and i.digital_review is not DigitalReviewStatus.UNREVIEWED
            }
        )

    async def create_link(self, link: SatisfactionLink) -> SatisfactionLink:
        self.links.append(link)
        return link

    async def list_links_for_item(self, user_id: str, item_id: str) -> list[SatisfactionLink]:
        return [l for l in self.links if l.user_id == user_id and l.checklist_item_id == item_id]  # noqa: E741

    async def list_links_for_items(
        self, user_id: str, item_ids: list[str]
    ) -> list[SatisfactionLink]:
        wanted = set(item_ids)
        return [l for l in self.links if l.user_id == user_id and l.checklist_item_id in wanted]  # noqa: E741

    async def supersede_item_document_links(
        self, user_id: str, item_id: str, document_id: str, replacement_id: str
    ) -> None:
        for link in self.links:
            if (
                link.user_id == user_id
                and link.checklist_item_id == item_id
                and link.detected_document_id == document_id
                and link.id != replacement_id
            ):
                link.digital_review = DigitalReviewStatus.SUPERSEDED
                link.superseded_by_link_id = replacement_id

    async def supersede_links_for_document(
        self, user_id: str, detected_document_id: str, *, replacement_link_id: str | None
    ) -> int:
        count = 0
        for link in self.links:
            if (
                link.user_id == user_id
                and link.detected_document_id == detected_document_id
                and link.superseded_by_link_id is None
                and link.digital_review is not DigitalReviewStatus.SUPERSEDED
            ):
                link.superseded_by_link_id = replacement_link_id
                link.digital_review = DigitalReviewStatus.SUPERSEDED
                count += 1
        return count


class RecordingAudit:
    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)


class SyntheticRequirementEvidence:
    """Explicit synthetic document port; scope/eligibility use migrated DB tests."""

    async def requirement_document(self, user_id, matter_id, document_id):
        from src.modules.document.contracts import (
            FactEvidenceLocator,
            OriginalSourcePin,
            RequirementDocument,
        )

        return RequirementDocument(
            document_id,
            1,
            1,
            "rta.doc.title_certificate",
            True,
            (OriginalSourcePin("src_synthetic", "a" * 64, "1", document_id, 1, (1,)),),
            (
                FactEvidenceLocator(
                    "src_synthetic",
                    1,
                    "a" * 64,
                    detected_document_id=document_id,
                    interpretation_generation=1,
                ),
            ),
        )

    async def requirement_locators(self, user_id, matter_id, evidence_reference_ids):
        from src.modules.document.contracts import FactEvidenceLocator

        return tuple(
            FactEvidenceLocator(
                "src_synthetic",
                1,
                "a" * 64,
                detected_document_id="doc_2",
                interpretation_generation=1,
            )
            for _ in evidence_reference_ids
        )

    async def validate_evidence(self, user_id, matter_id, locator):
        return None
