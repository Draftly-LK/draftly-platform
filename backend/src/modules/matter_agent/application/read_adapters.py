"""Adapters from other modules' application services to the agent's read ports.

Each one calls the service that owns the concept and reshapes its result into a
plain dictionary. Nothing here reaches a repository, and nothing re-derives a
rule another service already owns.

Reshaping is deliberate rather than lazy: handing the model a domain object
would leak internal ids and storage references it has no business seeing, and
would couple the prompt surface to every future field added upstream.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.modules.document.domain.errors import DocumentReviewNotFoundError


class _MatterServiceLike(Protocol):
    async def get_access_summary(self, user_id: str, matter_id: str) -> Any: ...


class MatterSummaryAdapter:
    """Matter identity and routing state, from ``matter_service``."""

    def __init__(self, matters: Any) -> None:
        self._matters = matters

    async def summary_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]:
        summary = await self._matters.get_access_summary(user_id, matter_id)
        if summary is None:
            return {"matterId": matter_id, "found": False}
        return {
            "matterId": summary.id,
            "reference": getattr(summary, "reference", ""),
            "responsibleLawyerId": summary.responsible_lawyer_id,
            "regimeId": summary.regime_id,
            "subtypeId": getattr(summary, "subtype_id", None),
            "rtaState": _enum_value(getattr(summary, "rta_state", None)),
            "lifecycleStatus": _enum_value(getattr(summary, "lifecycle_status", None)),
            "found": True,
        }


class ChecklistSummaryAdapter:
    """Checklist items and their seven statuses, from ``checklist_service``."""

    def __init__(self, checklist: Any) -> None:
        self._checklist = checklist

    async def checklist_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]:
        view = await self._checklist.get_checklist(user_id=user_id, matter_id=matter_id)
        return {
            "snapshotId": view.snapshot.id,
            "blockingRequirementIds": list(view.blocking_requirement_ids),
            "items": [
                {
                    "itemId": entry.item.id,
                    "requirementDefinitionId": entry.item.requirement_definition_id,
                    "version": entry.item.version,
                    "applicability": _enum_value(entry.item.applicability),
                    "collection": _enum_value(entry.item.collection),
                    "digitalReview": _enum_value(entry.item.digital_review),
                    "physicalOriginal": _enum_value(entry.item.physical_original),
                    "currency": _enum_value(entry.item.currency),
                    "consistency": _enum_value(entry.item.consistency),
                    # Computed, never settable. Shown so the model can explain
                    # what is outstanding without ever trying to write it.
                    "resolution": _enum_value(entry.computed_resolution),
                    "blocksApproval": entry.blocks_approval,
                    "liveLinkCount": entry.live_link_count,
                    "assignedTo": entry.item.assigned_to,
                    "dueAt": _iso(entry.item.due_at),
                }
                for entry in view.items
            ],
        }


class DocumentReadAdapter:
    """Documents, extraction and OCR, from the document services."""

    def __init__(self, *, ingestion: Any, review: Any) -> None:
        self._ingestion = ingestion
        self._review = review

    async def documents_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]:
        sources, _ = await self._ingestion.list_source_files(
            user_id=user_id, matter_id=matter_id, limit=50
        )
        return {
            "sourceFiles": [
                {
                    "sourceFileId": view.source_file.id,
                    "filename": view.source_file.filename,
                    "state": _enum_value(getattr(view.source_file, "state", None)),
                    "detectedDocumentIds": list(view.detected_document_ids),
                    "containsMultipleDocuments": view.contains_multiple_documents,
                    "duplicateOfSourceFileId": view.duplicate_of_source_file_id,
                }
                for view in sources
            ]
        }

    async def extraction_for_agent(
        self, *, user_id: str, detected_document_id: str
    ) -> dict[str, Any]:
        review = await self._review.get_review(
            user_id=user_id, detected_document_id=detected_document_id
        )
        return {
            "detectedDocumentId": review.detected_document_id,
            "typeId": review.type_id,
            "suggestedName": review.suggested_name,
            "candidates": [
                {
                    "candidateId": candidate.id,
                    "key": candidate.key,
                    "value": candidate.edited_value or candidate.candidate_value,
                    "pageNo": candidate.page_no,
                    "modelReportedConfidence": candidate.model_reported_confidence,
                    # Every candidate is unverified until a lawyer approves it.
                    "reviewState": candidate.review_state,
                    "version": candidate.version,
                }
                for candidate in review.candidates
            ],
            "pages": [
                {
                    "pageId": page.id,
                    "pageNo": page.page_no,
                    "qualityStatus": page.quality_status,
                    "classificationTypeId": page.classification_type_id,
                    "classificationConfidence": page.classification_confidence,
                }
                for page in review.pages
            ],
        }

    async def ocr_pages_for_agent(
        self, *, user_id: str, detected_document_id: str, page_no: int | None
    ) -> dict[str, Any]:
        review = await self._review.get_review(
            user_id=user_id, detected_document_id=detected_document_id
        )
        wanted = [page for page in review.pages if page_no is None or page.page_no == page_no]
        pages: list[dict[str, Any]] = []
        for page in wanted:
            try:
                raw = await self._review.get_artifact(user_id=user_id, page_id=page.id, kind="ocr")
            except DocumentReviewNotFoundError:
                # A missing derivative is reported, not silently dropped: an
                # absent page must not read as an empty page.
                pages.append({"pageNo": page.page_no, "text": "", "available": False})
                continue
            pages.append(
                {
                    "pageNo": page.page_no,
                    "text": _ocr_text(raw),
                    "available": True,
                }
            )
        return {"detectedDocumentId": detected_document_id, "pages": pages}


class FactReadAdapter:
    """Verified facts, from ``FactQueryService``."""

    def __init__(self, facts: Any) -> None:
        self._facts = facts

    async def facts_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]:
        views = await self._facts.list_facts(user_id=user_id, matter_id=matter_id)
        return {
            "facts": [
                {
                    "factId": view.fact.id,
                    "factTypeId": view.fact.fact_type_id,
                    "value": view.fact.value,
                    "status": _enum_value(view.fact.status),
                    "version": view.fact.version,
                    "evidenceReferenceIds": list(view.fact.evidence_reference_ids),
                }
                for view in views
            ]
        }


class DraftReadAdapter:
    """Working forms, from ``draft_service``."""

    def __init__(self, drafts: Any) -> None:
        self._drafts = drafts

    async def drafts_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]:
        forms, _ = await self._drafts.list_forms(user_id=user_id, matter_id=matter_id, limit=50)
        return {
            "forms": [
                {
                    "formId": form.id,
                    "templateId": getattr(form, "template_id", None),
                    "status": _enum_value(getattr(form, "status", None)),
                    "version": getattr(form, "version", None),
                }
                for form in forms
            ]
        }


class InventoryAdapter:
    """Parties and documents. Parcels are not modelled in this release."""

    def __init__(self, *, matters: Any, documents: DocumentReadAdapter) -> None:
        self._matters = matters
        self._documents = documents

    async def inventory_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]:
        documents = await self._documents.documents_for_agent(user_id=user_id, matter_id=matter_id)
        summary = await self._matters.get_access_summary(user_id, matter_id)
        party_ids = list(getattr(summary, "party_ids", ()) or ()) if summary else []
        return {
            "parties": [{"partyId": party_id} for party_id in party_ids],
            "documents": documents["sourceFiles"],
            "parcels": [],
            "parcelsSupported": False,
        }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _ocr_text(raw: bytes) -> str:
    """Pull page text out of the stored OCR JSON.

    The artefact is the ``schemaVersion 1.0`` payload written by the V1
    pipeline. Anything unparseable yields empty text rather than an exception:
    a broken derivative must not take down a chat turn.
    """
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    text = parsed.get("fullText")
    return str(text) if isinstance(text, str) else ""
