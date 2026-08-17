"""Source governance — every rule points at the authority it rests on.

Spec §13. A requirement, check, or template that cannot name its source is not
shippable: the UI shows the source class beside the requirement, and a source
that cannot be verified blocks any calculation or submission claim that depends
on it (§13.2.6).

Nothing here is lawyer-approved. ``lawyer_approval`` is ``None`` on every seed
record, which is the accurate state of the repository today, and the compiler
surfaces that as ``SOURCE REVERIFICATION REQUIRED`` rather than pretending
otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.modules.content_governance.domain.enums import (
    SourceClass,
    SourceConfidence,
    SourceCurrencyStatus,
)


@dataclass(frozen=True)
class LawyerApproval:
    """A named lawyer's recorded approval of a rule and its scope (§13.2.2)."""

    lawyer_id: str
    approved_at: str
    scope: str


@dataclass(frozen=True)
class RequirementSourceRecord:
    """§13.1. ``effective_from`` is nullable on purpose: unknown is not
    "current forever" (§13.2.4)."""

    id: str
    source_class: SourceClass
    title: str
    jurisdiction: str
    citation: str
    confidence: SourceConfidence
    currency_status: SourceCurrencyStatus
    issuing_authority: str | None = None
    local_authority_id: str | None = None
    section_regulation_form: str | None = None
    canonical_url: str | None = None
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    retrieved_at: date | None = None
    verified_at: date | None = None
    verified_by: str | None = None
    supersedes_source_record_id: str | None = None
    lawyer_approval: LawyerApproval | None = None
    notes: str | None = None
    version: int = 1

    @property
    def requires_reverification(self) -> bool:
        """True when a rule depending on this source must display a warning.

        A source is safe to rely on only when a named lawyer approved it *and*
        its currency is ``CURRENT``. Everything in the seed register fails at
        least one of those, which is the point.
        """
        return (
            self.lawyer_approval is None or self.currency_status is not SourceCurrencyStatus.CURRENT
        )


# ── Seed register (§13.3) ────────────────────────────────────────────────────
#
# Retrieval dates come from the specification's own source table. They are
# recorded, not invented, and none of these records is approved for production
# legal output.

_RETRIEVED = date(2026, 8, 16)

SRC_RTA_ACT = RequirementSourceRecord(
    id="src.lk.rta.act.1998",
    source_class=SourceClass.LAW,
    title="Registration of Title Act No. 21 of 1998",
    issuing_authority="Parliament of Sri Lanka",
    jurisdiction="LK",
    citation="Registration of Title Act No. 21 of 1998",
    confidence=SourceConfidence.HIGH,
    currency_status=SourceCurrencyStatus.REVERIFY,
    retrieved_at=_RETRIEVED,
    notes=(
        "Verify amendments and the current consolidated text with counsel before production use."
    ),
)

SRC_GAZETTE_2022 = RequirementSourceRecord(
    id="src.lk.rta.gazette.2308_27.2022",
    source_class=SourceClass.REG,
    title="Gazette Extraordinary No. 2308/27 of 1 December 2022",
    issuing_authority="Government of Sri Lanka",
    jurisdiction="LK",
    citation="Gazette Extraordinary No. 2308/27, 1 Dec. 2022, amendment to regulation 15(1)",
    section_regulation_form="regulation 15(1), items (i)-(xxii)",
    confidence=SourceConfidence.HIGH,
    currency_status=SourceCurrencyStatus.REVERIFY,
    publication_date=date(2022, 12, 1),
    retrieved_at=_RETRIEVED,
    notes=(
        "Current supplied 22-form mapping. The English form text contains "
        "apparent typographical defects; a production rendering needs a "
        "recorded variance decision (§1.2, §9.5)."
    ),
)

SRC_GAZETTE_2014 = RequirementSourceRecord(
    id="src.lk.rta.gazette.1886_58.2014",
    source_class=SourceClass.REG,
    title="Gazette Extraordinary No. 1886/58 of 31 October 2014",
    issuing_authority="Government of Sri Lanka",
    jurisdiction="LK",
    citation="Gazette Extraordinary No. 1886/58, 31 Oct. 2014",
    confidence=SourceConfidence.HIGH,
    currency_status=SourceCurrencyStatus.SUPERSEDED,
    publication_date=date(2014, 10, 31),
    retrieved_at=_RETRIEVED,
    notes="Earlier RTA regulation amendments/forms; extracted text needs Sinhala validation.",
)

SRC_RGD_TRANSACTIONS = RequirementSourceRecord(
    id="src.lk.rgd.ops.transactions",
    source_class=SourceClass.OPS,
    title="RGD — Title registration transactions",
    issuing_authority="Registrar General's Department",
    jurisdiction="LK",
    citation="RGD Transactions page",
    canonical_url=(
        "https://www.rgd.gov.lk/web/index.php/en/services/"
        "document-land-registration/title/transactions"
    ),
    confidence=SourceConfidence.HIGH,
    currency_status=SourceCurrencyStatus.REVERIFY,
    retrieved_at=_RETRIEVED,
    notes=(
        "No displayed Last Modified date, so currency is versioned and "
        "re-verified rather than assumed (§13.2.5: at least every 90 days)."
    ),
)

SRC_RGD_CHARGES = RequirementSourceRecord(
    id="src.lk.rgd.ops.charges",
    source_class=SourceClass.OPS,
    title="RGD — Title registration charges",
    issuing_authority="Registrar General's Department",
    jurisdiction="LK",
    citation="RGD Charges page",
    canonical_url=(
        "https://www.rgd.gov.lk/web/index.php/en/services/document-land-registration/title/charges"
    ),
    confidence=SourceConfidence.MEDIUM,
    currency_status=SourceCurrencyStatus.REVERIFY,
    retrieved_at=_RETRIEVED,
    notes=(
        "Official issuer, MEDIUM currency because Last Modified is blank. "
        "Fees are never permanently hard-coded (§13.4)."
    ),
)

SRC_TIRE_31_SCAN = RequirementSourceRecord(
    id="src.lk.rgd.ops.tire31",
    source_class=SourceClass.UNVERIFIED,
    title="Ti.Re.31 operational application for a new Title Certificate",
    issuing_authority="Registrar General's Department",
    jurisdiction="LK",
    citation="Uploaded Sinhala Ti.Re.31 scan",
    confidence=SourceConfidence.LOW,
    currency_status=SourceCurrencyStatus.UNKNOWN,
    retrieved_at=_RETRIEVED,
    notes=(
        "Operational form example only. Exact translation, revision, and "
        "current acceptance require registry/lawyer confirmation. This is NOT "
        "Gazette Form 31 (§1.2, §Executive 11)."
    ),
)

SRC_UDA_APPROVALS = RequirementSourceRecord(
    id="src.lk.uda.ops.approvals",
    source_class=SourceClass.OPS,
    title="UDA — Building plan and land subdivision approvals",
    issuing_authority="Urban Development Authority",
    jurisdiction="LK",
    citation="UDA approval process page",
    canonical_url="https://www.uda.gov.lk/approval-process.html",
    confidence=SourceConfidence.MEDIUM,
    currency_status=SourceCurrencyStatus.REVERIFY,
    retrieved_at=_RETRIEVED,
    notes="Official issuer; applicability to a given conveyance is not universal.",
)

SRC_LAWYER_PRACTICE = RequirementSourceRecord(
    id="src.practice.examination_of_title",
    source_class=SourceClass.PRACTICE,
    title="Examination-of-title checklist and practical-aspects deck",
    jurisdiction="LK",
    citation="Pilot lawyer's professional checklist",
    confidence=SourceConfidence.MEDIUM,
    currency_status=SourceCurrencyStatus.UNKNOWN,
    notes=(
        "Professional risk-control practice. A named lawyer must approve each "
        "generalised rule and its scope before it gates anything (§13.2.2)."
    ),
)

SRC_LOCAL_AUTHORITY = RequirementSourceRecord(
    id="src.local_ops.council_records",
    source_class=SourceClass.LOCAL_OPS,
    title="Local-authority certificate practice",
    jurisdiction="LK",
    citation="Named municipal/urban/pradeshiya authority instruction",
    confidence=SourceConfidence.LOW,
    currency_status=SourceCurrencyStatus.UNKNOWN,
    notes=(
        "Jurisdiction-specific. A rule for one council must not activate "
        "globally; requirements carry local_authority_id (§13.2.8). Council "
        "records are contextual evidence, never title (§Executive 9)."
    ),
)

SRC_PRODUCT_SAFETY = RequirementSourceRecord(
    id="src.product.draftly_safety",
    source_class=SourceClass.PRODUCT,
    title="Draftly product-safety rule",
    jurisdiction="LK",
    citation="Draftly RTA matter workflow v1",
    confidence=SourceConfidence.HIGH,
    currency_status=SourceCurrencyStatus.CURRENT,
    lawyer_approval=None,
    notes=(
        "Software safety and auditability rules: evidence immutability, "
        "human-only original inspection, V0 scope gates, confidence policy."
    ),
)

SEED_SOURCE_RECORDS: tuple[RequirementSourceRecord, ...] = (
    SRC_RTA_ACT,
    SRC_GAZETTE_2022,
    SRC_GAZETTE_2014,
    SRC_RGD_TRANSACTIONS,
    SRC_RGD_CHARGES,
    SRC_TIRE_31_SCAN,
    SRC_UDA_APPROVALS,
    SRC_LAWYER_PRACTICE,
    SRC_LOCAL_AUTHORITY,
    SRC_PRODUCT_SAFETY,
)

_BY_ID: dict[str, RequirementSourceRecord] = {r.id: r for r in SEED_SOURCE_RECORDS}


def get_source_record(source_id: str) -> RequirementSourceRecord | None:
    return _BY_ID.get(source_id)


def all_source_records() -> tuple[RequirementSourceRecord, ...]:
    return SEED_SOURCE_RECORDS


@dataclass(frozen=True)
class SourceCitation:
    """A rule's pointer at one source, with the part of it that applies.

    ``locator`` is the section, regulation, form, or page inside the source —
    "s. 47", "Form 8 item 1(j)", "Transactions page, transfer pack".
    """

    source_record_id: str
    locator: str = ""
    note: str = ""

    def resolve(self) -> RequirementSourceRecord | None:
        return get_source_record(self.source_record_id)
