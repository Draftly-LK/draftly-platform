"""A reviewed evidence set cannot retain authority through one stale active binding."""

from copy import deepcopy
from dataclasses import replace

import pytest

from src.modules.content_governance.contracts import (
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    ResolutionStatus,
)
from src.modules.document.contracts import OriginalSourcePin
from src.modules.task.tests.fakes import MATTER_ID, USER_ID, SyntheticRequirementEvidence
from src.modules.task.tests.test_checklist_service import WHO, Harness
from src.platform.errors import DomainRuleError


class ChangingEvidence(SyntheticRequirementEvidence):
    changed = None

    async def requirement_document(self, user_id, matter_id, document_id):
        document = replace(
            await super().requirement_document(user_id, matter_id, document_id),
            originals=(OriginalSourcePin("src_" + document_id, "a" * 64, "1"),),
        )
        if document_id != "doc_first":
            return document
        if self.changed == "unavailable":
            raise DomainRuleError("Synthetic bound original unavailable")
        if self.changed == "version":
            return replace(document, version=2)
        if self.changed == "generation":
            return replace(document, interpretation_generation=2)
        if self.changed == "original":
            return replace(
                document, originals=(OriginalSourcePin("src_replacement", "b" * 64, "2"),)
            )
        return document


async def received_original_requirement():
    h = Harness()
    h.service._documents = ChangingEvidence()
    await h.compile()
    item = h.item_for("R_C20_ORIGINAL_TITLE_CERTIFICATE_INSPECTED")
    for document_id in ("doc_first", "doc_second"):
        await h.service.link_document(
            **WHO,
            item_id=item.id,
            detected_document_id=document_id,
            expected_version=h.repo.items[item.id].version,
            document_version=1,
            interpretation_generation=1,
        )
    return h, item.id


@pytest.mark.parametrize(
    "change", ["version", "generation", "original", "unavailable", "superseded-history"]
)
@pytest.mark.parametrize("projection", ["checklist", "item"])
async def test_one_stale_member_withdraws_review_without_erasing_history(change, projection):
    h, item_id = await received_original_requirement()
    await h.service.decide_satisfaction(
        **WHO,
        item_id=item_id,
        expected_version=3,
        digital_review=DigitalReviewStatus.LAWYER_CONFIRMED,
        currency=CurrencyStatus.CURRENT,
        consistency=ConsistencyStatus.MATCHED,
    )
    before = await h.service.record_original_inspection(
        **WHO, item_id=item_id, expected_version=4, method="Synthetic original review"
    )
    assert before.computed_resolution is ResolutionStatus.SATISFIED
    if change == "superseded-history":
        await h.service.supersede_document_links(user_id=USER_ID, detected_document_id="doc_first")
    h.service._documents.changed = "version" if change == "superseded-history" else change
    stored, links = deepcopy((h.repo.items[item_id], h.repo.links))
    audit = tuple(h.audit.events)
    if projection == "checklist":
        checklist = await h.service.get_checklist(user_id=USER_ID, matter_id=MATTER_ID)
        view = next(row for row in checklist.items if row.item.id == item_id)
    else:
        view = await h.service._view(USER_ID, h.repo.items[item_id], before.requirement)
    assert view.live_link_count == 1
    if change == "superseded-history":
        assert view.computed_resolution is ResolutionStatus.SATISFIED
    else:
        assert view.item.digital_review is DigitalReviewStatus.UNREVIEWED
        assert view.computed_resolution is not ResolutionStatus.SATISFIED
        assert view.blocks_approval
    assert (h.repo.items[item_id], h.repo.links) == (stored, links)
    assert tuple(h.audit.events) == audit
    assert view.item.collection == stored.collection
    assert view.item.inspection_history == stored.inspection_history
    assert view.item.original_inspection == stored.original_inspection
