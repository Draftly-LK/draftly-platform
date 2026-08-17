"""RTA checklist modules, item requirements, and registration packs.

The compiler assembles a matter checklist from base administration, the regime
and title-status module, the exact-instrument module, condition-triggered
scenario modules, and office/lawyer additions (§5.1). This file holds the
catalogue those layers are drawn from: 23 modules (C00-C22, §5.2), the
item-level requirements and the authority each rests on (§5.3), and the
registration-pack shorthand used by the matrix for all 22 instruments
(§5.5, §5.6).

Two rules matter more than the rest:

- No requirement exists without a source citation, and the source class stays
  visible so a lawyer can tell a statute from an office habit (§5.1, §13).
- ``waivable=False`` means no lawyer waiver, ever. A ``STATUTORY`` blocker
  cannot be overridden inside Draftly at all (§5.4, §7.3), so the invariant is
  enforced at construction rather than left to the caller.

Applicability, collection, digital review, physical original, currency,
consistency, and resolution are orthogonal per-matter statuses (§5.4) owned by
the matter module. What lives here is the *policy* each requirement sets for
them, not the state itself.

Document-class ids (``rta.doc.*``) are referenced, not defined, here; the
class catalogue belongs to the document module (§14.4). Labels and
explanations are translation keys — this module never carries legal prose.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.content_governance.domain.enums import (
    ApplicabilityStatus,
    BlockerKind,
    IssueSeverity,
    MandatoryBasis,
    PhysicalOriginalStatus,
    RequirementGroup,
)
from src.modules.content_governance.domain.sources import (
    SRC_GAZETTE_2022,
    SRC_LAWYER_PRACTICE,
    SRC_LOCAL_AUTHORITY,
    SRC_PRODUCT_SAFETY,
    SRC_RGD_CHARGES,
    SRC_RGD_TRANSACTIONS,
    SRC_RTA_ACT,
    SRC_TIRE_31_SCAN,
    SRC_UDA_APPROVALS,
    SourceCitation,
)

#: Bumped whenever a requirement or module changes. Pinned into every checklist
#: snapshot so a rule change is never retroactive (§5.1, §12.2).
CHECKLIST_VERSION = "1.0.0"


# ── Definitions ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RequirementDefinition:
    """One checklist item's rule: why it is required and how it is satisfied.

    ``physical_original_policy`` is the level the requirement demands, not the
    matter's current state. ``ORIGINAL_INSPECTED`` can only ever be reached by
    a named human recording the inspection (§5.4).
    """

    id: str
    module_id: str
    label_key: str
    explanation_key: str
    mandatory_basis: MandatoryBasis
    group: RequirementGroup
    sources: tuple[SourceCitation, ...]
    accepted_document_class_ids: tuple[str, ...] = ()
    may_be_satisfied_by_combined_document: bool = True
    may_require_multiple_documents: bool = False
    default_applicability: ApplicabilityStatus = ApplicabilityStatus.REQUIRED
    physical_original_policy: PhysicalOriginalStatus = PhysicalOriginalStatus.NOT_REQUIRED
    currency_max_age_days: int | None = None
    unsatisfied_severity: IssueSeverity = IssueSeverity.WARNING
    unsatisfied_blocker_kind: BlockerKind = BlockerKind.EVIDENCE
    waivable: bool = True
    local_authority_scoped: bool = False
    order: int = 0

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError(f"Requirement '{self.id}' asserts a rule with no source (§13.2).")
        if self.unsatisfied_blocker_kind is BlockerKind.STATUTORY and self.waivable:
            raise ValueError(
                f"Requirement '{self.id}' is STATUTORY; a lawyer waiver cannot "
                "reach it (§5.4, §7.3)."
            )
        if (
            self.local_authority_scoped
            and self.mandatory_basis is not MandatoryBasis.LOCAL_AUTHORITY
        ):
            raise ValueError(
                f"Requirement '{self.id}' is local-authority scoped but does not "
                "carry LOCAL_AUTHORITY basis; a council rule must not activate "
                "globally (§13.2.8)."
            )


@dataclass(frozen=True)
class ChecklistModuleDefinition:
    """One module of the standard catalogue (§5.2).

    ``requirement_ids`` is derived from ``REQUIREMENTS`` at import so the two
    cannot drift. Activation rules live in the compiler, not here.
    """

    id: str
    version: str
    label_key: str
    description_key: str
    requirement_ids: tuple[str, ...]
    sources: tuple[SourceCitation, ...]
    order: int


@dataclass(frozen=True)
class RegistrationPack:
    """Configurable operational submission shorthand (§5.5).

    A pack is not a new legal instrument. It groups requirements the registry
    currently expects together, and it is versioned because the RGD pages that
    state it carry no reliable last-modified date (§13.2.5).
    """

    id: str
    label_key: str
    requirement_ids: tuple[str, ...]
    sources: tuple[SourceCitation, ...]


# ── Citation helpers ─────────────────────────────────────────────────────────


def _act(section: str) -> SourceCitation:
    return SourceCitation(SRC_RTA_ACT.id, locator=f"s. {section}")


def _form(number: str) -> SourceCitation:
    return SourceCitation(SRC_GAZETTE_2022.id, locator=f"Form {number}")


_REG_FORMS = SourceCitation(SRC_GAZETTE_2022.id, locator="regulation 15(1) amendment")
_RGD_PACK = SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page, submission pack")
_RGD_SEARCH = SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page, title services")
_RGD_FEES = SourceCitation(SRC_RGD_CHARGES.id, locator="Charges page")
_PRACTICE = SourceCitation(SRC_LAWYER_PRACTICE.id, locator="examination-of-title checklist")
_UDA = SourceCitation(SRC_UDA_APPROVALS.id, locator="approval process page")
_PRODUCT = SourceCitation(SRC_PRODUCT_SAFETY.id, locator="Draftly RTA matter workflow v1")


def _local(locator: str) -> SourceCitation:
    return SourceCitation(
        SRC_LOCAL_AUTHORITY.id,
        locator=locator,
        note="Jurisdiction-specific; activates only for the named authority (§13.2.8).",
    )


# ── Module ids ───────────────────────────────────────────────────────────────

_C00 = "C00_MATTER_ADMIN"
_C01 = "C01_IDENTITY_CAPACITY"
_C02 = "C02_RTA_TITLE"
_C03 = "C03_REGISTRY_SEARCH"
_C04 = "C04_SURVEY_CADASTRAL"
_C05 = "C05_TITLE_HISTORY"
_C06 = "C06_ENCUMBRANCES"
_C07 = "C07_MORTGAGE_RELEASE"
_C08 = "C08_LEASE_OCCUPATION"
_C09 = "C09_PROBATE_TRANSMISSION"
_C10 = "C10_COMPANY_AUTHORITY"
_C11 = "C11_LOCAL_AUTHORITY"
_C12 = "C12_BUILDING_COMPLIANCE"
_C13 = "C13_SUBDIVISION_AMALGAMATION"
_C14 = "C14_CONDOMINIUM_STRATA"
_C15 = "C15_LIFE_INTEREST"
_C16 = "C16_SERVITUDE_ACCESS"
_C17 = "C17_CAVEAT_LITIGATION"
_C18 = "C18_CANCELLATION_RELEASE"
_C19 = "C19_COURT_STATUTORY_SALE"
_C20 = "C20_STAMP_REGISTRATION"
_C21 = "C21_POWER_OF_ATTORNEY"
_C22 = "C22_COOWNERS"


def _req(
    requirement_id: str,
    module_id: str,
    *,
    basis: MandatoryBasis,
    group: RequirementGroup,
    sources: tuple[SourceCitation, ...],
    order: int,
    explanation_slot: str = "explanation",
    accepted_document_class_ids: tuple[str, ...] = (),
    may_be_satisfied_by_combined_document: bool = True,
    may_require_multiple_documents: bool = False,
    default_applicability: ApplicabilityStatus = ApplicabilityStatus.REQUIRED,
    physical_original_policy: PhysicalOriginalStatus = PhysicalOriginalStatus.NOT_REQUIRED,
    currency_max_age_days: int | None = None,
    unsatisfied_severity: IssueSeverity = IssueSeverity.WARNING,
    unsatisfied_blocker_kind: BlockerKind = BlockerKind.EVIDENCE,
    waivable: bool = True,
    local_authority_scoped: bool = False,
) -> RequirementDefinition:
    """Build a requirement, deriving its translation keys from its stable id."""
    return RequirementDefinition(
        id=requirement_id,
        module_id=module_id,
        label_key=f"rta.requirement.{requirement_id}.label",
        explanation_key=f"rta.requirement.{requirement_id}.{explanation_slot}",
        mandatory_basis=basis,
        group=group,
        sources=sources,
        accepted_document_class_ids=accepted_document_class_ids,
        may_be_satisfied_by_combined_document=may_be_satisfied_by_combined_document,
        may_require_multiple_documents=may_require_multiple_documents,
        default_applicability=default_applicability,
        physical_original_policy=physical_original_policy,
        currency_max_age_days=currency_max_age_days,
        unsatisfied_severity=unsatisfied_severity,
        unsatisfied_blocker_kind=unsatisfied_blocker_kind,
        waivable=waivable,
        local_authority_scoped=local_authority_scoped,
        order=order,
    )


# ── Requirement catalogue (§5.3) ─────────────────────────────────────────────
#
# `currency_max_age_days` stays None almost everywhere on purpose: no supplied
# source states a validity period for registry or council evidence, and
# inventing one would manufacture a rule (§1.2, §13.2). The one exception is
# the operational source re-verification interval §13.2.5 states outright.

_C00_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C00_MATTER_AND_CLIENT_REFERENCE",
        _C00,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(_PRODUCT, _PRACTICE),
        order=1,
    ),
    _req(
        "R_C00_RESPONSIBLE_LAWYER_ASSIGNED",
        _C00,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(SourceCitation(SRC_PRODUCT_SAFETY.id, locator="§12.5 authorization minimum"),),
        order=2,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
    _req(
        "R_C00_ENGAGEMENT_AND_PARTY_ROLES",
        _C00,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(_PRACTICE,),
        order=3,
    ),
    _req(
        "R_C00_CONFLICT_CHECK_RECORDED",
        _C00,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(_PRACTICE, _PRODUCT),
        order=4,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        waivable=False,
    ),
    _req(
        "R_C00_CLIENT_INSTRUCTIONS_SCOPE",
        _C00,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(_PRACTICE,),
        order=5,
    ),
    _req(
        "R_C00_WORKING_AND_DOCUMENT_LANGUAGE",
        _C00,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(
            _RGD_PACK,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§11.2",
                note="Source-script names are never replaced by transliteration.",
            ),
        ),
        order=6,
    ),
    _req(
        "R_C00_REGISTRY_OFFICE_AND_JURISDICTION",
        _C00,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(_RGD_PACK, _act("1")),
        order=7,
    ),
    _req(
        "R_C00_SOURCE_CURRENCY_VERIFIED",
        _C00,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§13.2.5, §13.2.6",
                note="A source that cannot be verified blocks the claim depending on it.",
            ),
        ),
        order=8,
        currency_max_age_days=90,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        waivable=False,
    ),
    _req(
        "R_C00_FEE_SCHEDULE_VERSION_RECORDED",
        _C00,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.OFFICE_ADDED,
        sources=(
            _RGD_FEES,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id, locator="§13.4", note="Fees are never hard-coded."
            ),
        ),
        order=9,
        currency_max_age_days=90,
    ),
)


# Identity and capacity keeps the notary's statutory verification duty (s. 44)
# apart from the certified copies the registry currently wants in the pack.
# Collapsing them would turn an office habit into a statute.
_C01_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C01_PARTY_IDENTITY_VERIFIED",
        _C01,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("44"), _act("45(2)")),
        order=1,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C01_PARTY_CAPACITY_CONFIRMED",
        _C01,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("44"), _act("45(2)"), _PRACTICE),
        order=2,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C01_TRANSFEROR_CERTIFIED_ID",
        _C01,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_RGD_PACK, _act("44")),
        order=3,
        accepted_document_class_ids=(
            "rta.doc.nic",
            "rta.doc.passport",
            "rta.doc.driving_licence",
        ),
        may_require_multiple_documents=True,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C01_TRANSFEREE_CERTIFIED_ID",
        _C01,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_RGD_PACK, _act("44")),
        order=4,
        accepted_document_class_ids=(
            "rta.doc.nic",
            "rta.doc.passport",
            "rta.doc.driving_licence",
        ),
        may_require_multiple_documents=True,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C01_PARTY_ROLES_RECORDED",
        _C01,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_REG_FORMS, _act("43")),
        order=5,
    ),
    _req(
        "R_C01_TWO_WITNESSES_AT_EXECUTION",
        _C01,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("43"),),
        order=6,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C01_NOTARIAL_ATTESTATION",
        _C01,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("43"), _act("44")),
        order=7,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C01_REPRESENTATIVE_AUTHORITY",
        _C01,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_RGD_PACK, _PRACTICE),
        order=8,
        accepted_document_class_ids=(
            "rta.doc.power_of_attorney",
            "rta.doc.company_resolution",
        ),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C01_NAME_SCRIPT_CONSISTENCY",
        _C01,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§11.2",
                note="Transliteration is derived data, never the source-script name.",
            ),
        ),
        order=9,
    ),
)


_C02_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C02_RTA_COVERAGE_CONFIRMED",
        _C02,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 1",
                note="An address alone does not prove the parcel is under the RTA.",
            ),
            _RGD_SEARCH,
        ),
        order=1,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C02_TITLE_STATUS_NOT_INITIAL_COMPILATION",
        _C02,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            _act("10-27"),
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§Executive 1",
                note="Initial compilation is a different statutory process.",
            ),
        ),
        order=2,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.V0_SCOPE,
        waivable=False,
    ),
    _req(
        "R_C02_CURRENT_TITLE_CERTIFICATE",
        _C02,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("37"), _act("44"), _act("45(1)"), _RGD_PACK),
        order=3,
        accepted_document_class_ids=("rta.doc.title_certificate",),
        may_be_satisfied_by_combined_document=False,
        unsatisfied_severity=IssueSeverity.BLOCKING,
    ),
    _req(
        "R_C02_TITLE_REGISTER_REFERENCE",
        _C02,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("32"), _act("33"), _act("34")),
        order=4,
        accepted_document_class_ids=(
            "rta.doc.title_certificate",
            "rta.doc.title_register_extract",
        ),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C02_REGISTERED_OWNER_IDENTIFIED",
        _C02,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("32"), _act("44"), _act("45(2)")),
        order=5,
        accepted_document_class_ids=(
            "rta.doc.title_certificate",
            "rta.doc.title_register_extract",
        ),
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C02_TITLE_CLASS_RECORDED",
        _C02,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 14(a)-(d)",
                note="Second Class title is s. 14(b), not s. 14(a) (§1.2 correction).",
            ),
            _act("29-30"),
        ),
        order=6,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C02_PLACE_OF_REGISTRATION",
        _C02,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_RGD_PACK, _act("34")),
        order=7,
    ),
    _req(
        "R_C02_REGISTERED_INTEREST_HOLDERS",
        _C02,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("32"), _act("44")),
        order=8,
        accepted_document_class_ids=(
            "rta.doc.title_certificate",
            "rta.doc.title_register_extract",
        ),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C02_CERTIFICATE_MATCHES_REGISTER",
        _C02,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.3",
                note="Presence and extracted identifiers only; a scan establishes "
                "neither authenticity nor current legal status.",
            ),
        ),
        order=9,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C02_NEW_TITLE_CERTIFICATE_APPLICATION",
        _C02,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="new Title Certificate"),
            SourceCitation(
                SRC_TIRE_31_SCAN.id,
                note="Operational Ti.Re.31, not Gazette Form 31 (§Executive 11).",
            ),
        ),
        order=10,
        accepted_document_class_ids=("rta.doc.tire31_application",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
)


# Whether a current search is required is lawyer policy (§5.3), so the search
# items default to PROVISIONAL_REQUIRED until the pilot rule set settles them.
# No supplied source states how old a search may be; the max age stays None.
_C03_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C03_TITLE_REGISTER_INSPECTION",
        _C03,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("34"), _PRACTICE, _RGD_SEARCH),
        order=1,
        accepted_document_class_ids=("rta.doc.registry_search_result",),
        default_applicability=ApplicabilityStatus.PROVISIONAL_REQUIRED,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C03_CERTIFIED_REGISTER_EXTRACT",
        _C03,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("35"), _PRACTICE, _RGD_SEARCH),
        order=2,
        accepted_document_class_ids=("rta.doc.title_register_extract",),
        default_applicability=ApplicabilityStatus.PROVISIONAL_REQUIRED,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C03_SEARCH_DATETIME_RECORDED",
        _C03,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§7.2",
                note="A negative conclusion is meaningless without the search moment.",
            ),
        ),
        order=3,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C03_SEARCH_MATCHES_MATTER_PARCEL",
        _C03,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRODUCT, _PRACTICE),
        order=4,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C03_PENDING_AND_DAY_BOOK_ENTRIES",
        _C03,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_RGD_SEARCH, _act("34")),
        order=5,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C03_REGISTERED_INSTRUMENT_COPIES",
        _C03,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("35"), _PRACTICE),
        order=6,
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C03_PRE_ATTESTATION_SEARCH",
        _C03,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRACTICE, _act("45(1)")),
        order=7,
        accepted_document_class_ids=("rta.doc.registry_search_result",),
        default_applicability=ApplicabilityStatus.PROVISIONAL_REQUIRED,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C03_NO_LATER_ENTRY_ACKNOWLEDGED",
        _C03,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.3",
                note="A completed search is not a guarantee that no later entry exists.",
            ),
        ),
        order=8,
        explanation_slot="explanation_search_is_not_a_guarantee",
        unsatisfied_severity=IssueSeverity.INFORMATION,
        waivable=False,
    ),
)


_C04_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C04_PARCEL_IDENTIFIERS",
        _C04,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("4-5"), _act("44"), _act("45(2)")),
        order=1,
        accepted_document_class_ids=(
            "rta.doc.title_certificate",
            "rta.doc.title_register_extract",
            "rta.doc.cadastral_map_extract",
        ),
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
    _req(
        "R_C04_CADASTRAL_MAP_EXTRACT",
        _C04,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("10-11"), _PRACTICE),
        order=2,
        accepted_document_class_ids=("rta.doc.cadastral_map_extract",),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C04_SURVEY_PLAN",
        _C04,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 36",
                note="Legally specific for subdivision; office practice otherwise.",
            ),
        ),
        order=3,
        accepted_document_class_ids=("rta.doc.survey_plan",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C04_ADMINISTRATIVE_LOCATION",
        _C04,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_REG_FORMS, _act("44")),
        order=4,
    ),
    _req(
        "R_C04_REGISTERED_EXTENT",
        _C04,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("44"), _REG_FORMS),
        order=5,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C04_EXTENT_SUBJECT_TO_TRANSACTION",
        _C04,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 47",
                note="Part of a registered parcel cannot be dealt with before "
                "subdivision and new registration.",
            ),
        ),
        order=6,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C04_BOUNDARIES_RECORDED",
        _C04,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRACTICE, _REG_FORMS),
        order=7,
    ),
    _req(
        "R_C04_ACCESS_DEPICTED",
        _C04,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRACTICE, _act("75")),
        order=8,
    ),
    _req(
        "R_C04_PLAN_MATCHES_REGISTER",
        _C04,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            _PRODUCT,
            SourceCitation(
                SRC_LAWYER_PRACTICE.id,
                locator="examination-of-title checklist",
                note="Identifier comparison only; approval and authenticity need "
                "official or human evidence.",
            ),
        ),
        order=9,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C05_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C05_PRIOR_INSTRUMENT_CHAIN",
        _C05,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRACTICE,),
        order=1,
        accepted_document_class_ids=("rta.doc.prior_deed",),
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C05_CHAIN_TABLE_PREPARED",
        _C05,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRACTICE,),
        order=2,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C05_DEED_HISTORY_NOT_A_SUBSTITUTE",
        _C05,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            _act("32-33"),
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.2 C05",
                note="Deed history explains legacy entries; it never replaces the "
                "RTA Title Register.",
            ),
        ),
        order=3,
        explanation_slot="explanation_history_never_replaces_the_register",
        unsatisfied_severity=IssueSeverity.INFORMATION,
        waivable=False,
    ),
)


# Encumbrance work is where "no document" is most often misread as "no
# encumbrance". The last item exists to keep that inference illegal (§6.4, §7.2).
_C06_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C06_ENCUMBRANCE_SCHEDULE",
        _C06,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("44"), _act("32"), _PRACTICE),
        order=1,
        accepted_document_class_ids=(
            "rta.doc.title_register_extract",
            "rta.doc.registry_search_result",
        ),
        may_require_multiple_documents=True,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C06_MORTGAGE_STATUS_DETERMINED",
        _C06,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("44"), _form("11"), _PRACTICE),
        order=2,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C06_LEASE_STATUS_DETERMINED",
        _C06,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("44"), _form("10"), _PRACTICE),
        order=3,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C06_SALE_AGREEMENT_ENTRIES",
        _C06,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("44"), _form("23")),
        order=4,
        accepted_document_class_ids=("rta.doc.sale_agreement",),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C06_CAVEAT_SEIZURE_AND_NOTICE_ENTRIES",
        _C06,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("44"), _form("13"), _PRACTICE),
        order=5,
        accepted_document_class_ids=("rta.doc.caveat",),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C06_LIFE_INTEREST_ENTRIES",
        _C06,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("46"), _act("44")),
        order=6,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C06_SERVITUDE_ENTRIES",
        _C06,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_act("75"), _act("44")),
        order=7,
    ),
    _req(
        "R_C06_INSTRUMENT_COPIES_FOR_ENTRIES",
        _C06,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRACTICE, _act("35")),
        order=8,
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C06_ABSENCE_REQUIRES_CURRENT_SEARCH",
        _C06,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§6.4, §7.2",
                note="A missing document creates a task, never the negative fact.",
            ),
            _act("34"),
        ),
        order=9,
        explanation_slot="explanation_absence_is_not_a_finding",
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        waivable=False,
    ),
)


_C07_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C07_REGISTERED_MORTGAGE_INSTRUMENT",
        _C07,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("44"), _form("11"), _RGD_PACK),
        order=1,
        accepted_document_class_ids=("rta.doc.registered_mortgage_instrument",),
        may_be_satisfied_by_combined_document=False,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
    _req(
        "R_C07_MORTGAGE_ENTRY_STILL_ACTIVE",
        _C07,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_PRODUCT, _act("34")),
        order=2,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C07_MORTGAGEE_IDENTITY",
        _C07,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("44"), _form("12")),
        order=3,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C07_MORTGAGEE_SIGNING_AUTHORITY",
        _C07,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_PRACTICE, _act("43")),
        order=4,
        accepted_document_class_ids=("rta.doc.company_resolution",),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        unsatisfied_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
    ),
    _req(
        "R_C07_DISCHARGE_EVIDENCE",
        _C07,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_PRACTICE, _form("12")),
        order=5,
        accepted_document_class_ids=("rta.doc.mortgage_discharge_evidence",),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C07_RELEASE_OR_CANCELLED_BOND",
        _C07,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_RGD_PACK, _form("12")),
        order=6,
        accepted_document_class_ids=(
            "rta.doc.mortgage_discharge_evidence",
            "rta.doc.registered_mortgage_instrument",
        ),
        may_be_satisfied_by_combined_document=False,
        physical_original_policy=PhysicalOriginalStatus.ORIGINAL_REPORTED,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C07_INSTITUTIONAL_RELEASE_LETTER",
        _C07,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE,),
        order=7,
        accepted_document_class_ids=("rta.doc.mortgage_discharge_evidence",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C07_OTHER_CHARGES_AND_PRIORITY",
        _C07,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.TITLE_EXAMINATION,
        sources=(_PRACTICE, _act("44")),
        order=8,
    ),
    _req(
        "R_C07_CANCELLATION_REGISTERED",
        _C07,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            _act("38"),
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 49",
                note="The cancellation takes effect on registration, not on export.",
            ),
        ),
        order=9,
        unsatisfied_severity=IssueSeverity.BLOCKING,
    ),
)


_C08_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C08_LEASE_INSTRUMENT_AND_TERMS",
        _C08,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("10"), _act("44")),
        order=1,
        accepted_document_class_ids=("rta.doc.lease",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C08_OCCUPATION_STATUS",
        _C08,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE,),
        order=2,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C08_VACANT_POSSESSION_INSTRUCTION",
        _C08,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE,),
        order=3,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C08_LEASE_CANCELLATION_EVIDENCE",
        _C08,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("29"), _PRACTICE),
        order=4,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C09_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C09_DEATH_EVIDENCE",
        _C09,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("54"), _act("55")),
        order=1,
        accepted_document_class_ids=("rta.doc.death_certificate",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
    _req(
        "R_C09_TESTATE_PATH_EVIDENCE",
        _C09,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("54"), _PRACTICE),
        order=2,
        accepted_document_class_ids=("rta.doc.will", "rta.doc.probate_letters_of_administration"),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C09_INTESTATE_PATH_EVIDENCE",
        _C09,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("55"), _PRACTICE),
        order=3,
        accepted_document_class_ids=("rta.doc.probate_letters_of_administration",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C09_ESTATE_DISTRIBUTION_EVIDENCE",
        _C09,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE,),
        order=4,
        accepted_document_class_ids=("rta.doc.estate_inventory",),
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C09_TRANSMISSION_REGISTERED",
        _C09,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _act("54"),
            _act("55"),
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.3",
                note="Succession is never treated as complete until current "
                "registration confirms it.",
            ),
        ),
        order=5,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
)


# Company law sits outside the supplied RTA sources, so every item here is
# PRACTICE pending validation and none of it can be an automated conclusion.
_C10_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C10_INCORPORATION_EVIDENCE",
        _C10,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE,),
        order=1,
        accepted_document_class_ids=("rta.doc.company_incorporation_record",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C10_CURRENT_DIRECTORS_AND_OFFICERS",
        _C10,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE,),
        order=2,
        accepted_document_class_ids=("rta.doc.company_incorporation_record",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C10_BOARD_RESOLUTION",
        _C10,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE,),
        order=3,
        accepted_document_class_ids=("rta.doc.company_resolution",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C10_SIGNING_AUTHORITY_AND_SEAL",
        _C10,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.3",
                note="Authority indicators only; legal sufficiency is a lawyer conclusion.",
            ),
        ),
        order=4,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        unsatisfied_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
    ),
)


# Every item here is scoped to one named authority and may be satisfied by a
# single combined certificate — but street line and building line stay separate
# requirements with separate satisfaction decisions (§1.2, §5.4). Validity
# periods are jurisdiction-specific, so no max age is asserted.
_C11_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C11_STREET_LINE",
        _C11,
        basis=MandatoryBasis.LOCAL_AUTHORITY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_local("street line enquiry"), _PRACTICE),
        order=1,
        accepted_document_class_ids=(
            "rta.doc.street_line_certificate",
            "rta.doc.combined_local_authority_certificate",
        ),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        local_authority_scoped=True,
    ),
    _req(
        "R_C11_BUILDING_LINE",
        _C11,
        basis=MandatoryBasis.LOCAL_AUTHORITY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _local("building line enquiry"),
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§1.2",
                note="A deck slide titled 'building line' described a street-line "
                "issue; the two enquiries stay separate.",
            ),
        ),
        order=2,
        accepted_document_class_ids=(
            "rta.doc.building_line_certificate",
            "rta.doc.combined_local_authority_certificate",
        ),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        local_authority_scoped=True,
    ),
    _req(
        "R_C11_NON_VESTING",
        _C11,
        basis=MandatoryBasis.LOCAL_AUTHORITY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_local("non-vesting certificate"), _PRACTICE),
        order=3,
        accepted_document_class_ids=(
            "rta.doc.non_vesting_certificate",
            "rta.doc.combined_local_authority_certificate",
        ),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        local_authority_scoped=True,
    ),
    _req(
        "R_C11_ASSESSMENT_OWNERSHIP_CERTIFICATE",
        _C11,
        basis=MandatoryBasis.LOCAL_AUTHORITY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _local("assessment register / 'ownership' certificate"),
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§Executive 9, §1.2",
                note="Records local-authority assessment information only. It is "
                "never title and never overrides the RTA Title Register; a name "
                "mismatch is a review warning, not a finding about ownership.",
            ),
        ),
        order=4,
        explanation_slot="explanation_contextual_evidence_never_title",
        accepted_document_class_ids=(
            "rta.doc.assessment_certificate",
            "rta.doc.combined_local_authority_certificate",
        ),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        local_authority_scoped=True,
    ),
    _req(
        "R_C11_ASSESSMENT_NOTICE",
        _C11,
        basis=MandatoryBasis.LOCAL_AUTHORITY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _local("assessment notice"),
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§1.2",
                note="The deck's income-tax reading of an assessment notice is "
                "inapplicable to land rates and is not implemented.",
            ),
        ),
        order=5,
        accepted_document_class_ids=("rta.doc.assessment_notice",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        local_authority_scoped=True,
    ),
    _req(
        "R_C11_RATES_AND_TAXES_PAID",
        _C11,
        basis=MandatoryBasis.LOCAL_AUTHORITY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_local("rates and taxes receipts"), _PRACTICE),
        order=6,
        accepted_document_class_ids=("rta.doc.rates_receipt",),
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        local_authority_scoped=True,
    ),
)


_C12_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C12_APPROVED_BUILDING_PLAN",
        _C12,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_UDA, _PRACTICE),
        order=1,
        accepted_document_class_ids=("rta.doc.approved_building_plan",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C12_DEVELOPMENT_PERMIT",
        _C12,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_UDA,),
        order=2,
        accepted_document_class_ids=("rta.doc.development_permit",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C12_CERTIFICATE_OF_CONFORMITY",
        _C12,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_UDA, _PRACTICE),
        order=3,
        accepted_document_class_ids=("rta.doc.certificate_of_conformity",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C12_ALTERATIONS_REVIEWED",
        _C12,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.3",
                note="Presence and issue details only; not conclusive legality of "
                "all construction.",
            ),
        ),
        order=4,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C13_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C13_OWNER_APPLICATION",
        _C13,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("7"), _act("36")),
        order=1,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C13_ENCUMBRANCES_AND_ORDERS_DISCLOSED",
        _C13,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("36"), _act("44")),
        order=2,
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C13_AUTHORIZED_SURVEYOR_PLAN",
        _C13,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_RGD_PACK, _act("36")),
        order=3,
        accepted_document_class_ids=("rta.doc.survey_plan",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        physical_original_policy=PhysicalOriginalStatus.ORIGINAL_REPORTED,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C13_SURVEY_DEPARTMENT_CERTIFICATION",
        _C13,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_RGD_PACK, _act("36")),
        order=4,
        accepted_document_class_ids=("rta.doc.survey_department_certification",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C13_VALID_SALE_AGREEMENTS_CANCELLED",
        _C13,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("36"), _form("26")),
        order=5,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C14_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C14_PARENT_TITLE",
        _C14,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("50-52"), _act("32")),
        order=1,
        accepted_document_class_ids=("rta.doc.title_certificate",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C14_PRESCRIBED_APPLICATION",
        _C14,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("21"), _act("50-52")),
        order=2,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C14_CONDOMINIUM_DECLARATION",
        _C14,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_RGD_PACK, _act("50-52")),
        order=3,
        accepted_document_class_ids=("rta.doc.condominium_declaration",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C14_CONDOMINIUM_PLAN_AND_CERTIFICATION",
        _C14,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_RGD_PACK, _act("50-52")),
        order=4,
        accepted_document_class_ids=("rta.doc.condominium_plan",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C14_APARTMENT_OWNERSHIP_LAW_DOCUMENTS",
        _C14,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.2 C14",
                note="Requirements under the Apartment Ownership Law are outside "
                "the supplied RTA sources and need validation before they gate.",
            ),
        ),
        order=5,
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C15_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C15_HOLDER_AND_OWNER_IDENTIFIED",
        _C15,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("46"), _act("44")),
        order=1,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C15_REGISTRATION_REFERENCE",
        _C15,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("46"), _act("32")),
        order=2,
        accepted_document_class_ids=("rta.doc.life_interest_instrument",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C15_PERMITTED_CONDITIONS_REVIEWED",
        _C15,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("46"), _form("9"), _PRACTICE),
        order=3,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        unsatisfied_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
    ),
    _req(
        "R_C15_CONSENT_CANCELLATION_OR_DEATH_EVIDENCE",
        _C15,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("28"), _form("33"), _act("46")),
        order=4,
        accepted_document_class_ids=(
            "rta.doc.consent_letter",
            "rta.doc.death_certificate",
        ),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C16_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C16_DOMINANT_AND_SERVIENT_PARCELS",
        _C16,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("75"), _act("4-5")),
        order=1,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C16_REGISTERED_RIGHT_ENTRY",
        _C16,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("75"), _act("44")),
        order=2,
        accepted_document_class_ids=("rta.doc.servitude_instrument",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C16_ACCESS_DEPICTED_ON_PLAN",
        _C16,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE, _act("75")),
        order=3,
        accepted_document_class_ids=("rta.doc.survey_plan",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C16_AFFECTED_PARTIES_AND_TERMS",
        _C16,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("35"), _PRACTICE),
        order=4,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        unsatisfied_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
    ),
)


# A dispute is a stop condition, not a branch the software decides (§Executive
# 8). These items record what was found so the matter can be routed out.
_C17_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C17_CAVEAT_OR_NOTICE_DOCUMENT",
        _C17,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("13"), _form("30"), _act("44")),
        order=1,
        accepted_document_class_ids=("rta.doc.caveat",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C17_CLAIMANT_AND_REGISTERED_DATE",
        _C17,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("44"), _RGD_SEARCH),
        order=2,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C17_SEIZURE_INJUNCTION_OR_LIS_PENDENS",
        _C17,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("21-25"), _act("44"), _PRACTICE),
        order=3,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.BLOCKING,
    ),
    _req(
        "R_C17_COURT_PLEADINGS_AND_ORDERS",
        _C17,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("21-25"), _act("29-30")),
        order=4,
        accepted_document_class_ids=("rta.doc.court_order",),
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C17_TITLE_SETTLEMENT_STAGE_RECORDED",
        _C17,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _act("7-9"),
            _act("29-30"),
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§Executive 8, §8.2",
                note="A s. 12 notice is not proof of a dispute and a s. 14 "
                "declaration is not necessarily final registration.",
            ),
        ),
        order=5,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
)


_C18_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C18_PRIOR_INSTRUMENT_IDENTIFIED",
        _C18,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("44"), _act("32"), _RGD_SEARCH),
        order=1,
        may_be_satisfied_by_combined_document=False,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
    _req(
        "R_C18_CANCELLATION_FORM_MATCHES_PRIOR",
        _C18,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 39",
                note="Wrong-regime or wrong-form ambiguity blocks approval.",
            ),
            _REG_FORMS,
        ),
        order=2,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C18_ELIGIBLE_CANCELLING_PARTIES",
        _C18,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("43"), _act("44"), _REG_FORMS),
        order=3,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C18_GROUND_FOR_CANCELLATION",
        _C18,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_PRACTICE, _REG_FORMS),
        order=4,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        unsatisfied_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
    ),
    _req(
        "R_C18_GROUND_EVIDENCE",
        _C18,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE, _act("56")),
        order=5,
        accepted_document_class_ids=(
            "rta.doc.consent_letter",
            "rta.doc.court_order",
            "rta.doc.death_certificate",
        ),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C18_OPERATIVE_WORDING_LAWYER_AUTHORED",
        _C18,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§9.5, §Executive 12",
                note="Draftly never authors or silently corrects prescribed legal "
                "wording; the responsible lawyer owns it.",
            ),
            _REG_FORMS,
        ),
        order=6,
        explanation_slot="explanation_wording_is_lawyer_owned",
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        waivable=False,
    ),
    _req(
        "R_C18_ORIGINAL_TITLE_CERTIFICATE_HANDLING",
        _C18,
        basis=MandatoryBasis.CONDITIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _form("27"),
            SourceCitation(
                SRC_LAWYER_PRACTICE.id,
                locator="§5.6 cancel-gift row",
                note="The original Title Certificate exception needs a validated "
                "office rule before it can be relied on.",
            ),
        ),
        order=7,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C18_CANCELLATION_REGISTERED",
        _C18,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("38"), _act("49")),
        order=8,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C19_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C19_COURT_OR_AUTHORITY_IDENTIFIED",
        _C19,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("24-25"), _act("56")),
        order=1,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C19_ORDER_AND_DECREE",
        _C19,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("56"), _act("24-25")),
        order=2,
        accepted_document_class_ids=("rta.doc.court_order",),
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.BLOCKING,
    ),
    _req(
        "R_C19_CERTIFICATE_OF_SALE",
        _C19,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_form("25"), _form("34"), _act("56")),
        order=3,
        accepted_document_class_ids=("rta.doc.certificate_of_sale",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C19_FINALITY_AND_AUTHORITY_CONFIRMED",
        _C19,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE, _act("56")),
        order=4,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        unsatisfied_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
    ),
    _req(
        "R_C19_PURCHASER_AND_REGISTRATION_EVIDENCE",
        _C19,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("56"), _act("38")),
        order=5,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C20_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C20_PRESCRIBED_INSTRUMENT_FORM",
        _C20,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_REG_FORMS, _act("43"), _act("39")),
        order=1,
        accepted_document_class_ids=("rta.doc.prescribed_instrument",),
        may_be_satisfied_by_combined_document=False,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C20_CONSIDERATION_RECORDED",
        _C20,
        basis=MandatoryBasis.REGULATORY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_REG_FORMS, _act("40-42")),
        order=2,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C20_STAMP_DUTY_RECEIPT",
        _C20,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            _RGD_PACK,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§5.3",
                note="Receipt details and internal consistency only; tax-law "
                "sufficiency is never a Draftly conclusion.",
            ),
        ),
        order=3,
        accepted_document_class_ids=("rta.doc.stamp_duty_receipt",),
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        physical_original_policy=PhysicalOriginalStatus.ORIGINAL_REPORTED,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C20_REGISTRATION_FEE_AND_SUBMISSION",
        _C20,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_RGD_FEES, _RGD_PACK),
        order=4,
        accepted_document_class_ids=("rta.doc.registration_fee_receipt",),
    ),
    _req(
        "R_C20_DUPLICATE_INSTRUMENT",
        _C20,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_RGD_TRANSACTIONS.id,
                locator="Transactions page, duplicate and photograph rule",
                note="Currently stated for sale/transfer, gift, and exchange.",
            ),
        ),
        order=5,
        accepted_document_class_ids=("rta.doc.prescribed_instrument",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C20_PARTY_PHOTOGRAPHS",
        _C20,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_RGD_TRANSACTIONS.id,
                locator="Transactions page, duplicate and photograph rule",
            ),
        ),
        order=6,
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
    ),
    _req(
        "R_C20_ATTESTATION_DATE_RECORDED",
        _C20,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("43"), _act("45(1)")),
        order=7,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
    _req(
        "R_C20_TITLE_CERTIFICATE_FORWARDED",
        _C20,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_act("45(1)"), _RGD_PACK),
        order=8,
        accepted_document_class_ids=("rta.doc.title_certificate",),
        may_be_satisfied_by_combined_document=False,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        waivable=False,
    ),
    _req(
        "R_C20_SEVEN_WORKING_DAY_FORWARDING",
        _C20,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 45(1)",
                note="The deadline runs from attestation, not from export.",
            ),
            _RGD_PACK,
        ),
        order=9,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    # Only a named human can ever satisfy this. No scan, OCR result, or model
    # confidence may set ORIGINAL_INSPECTED (§Executive 5, §5.4), which is why
    # it is non-waivable and carries its own explanation slot.
    _req(
        "R_C20_ORIGINAL_TITLE_CERTIFICATE_INSPECTED",
        _C20,
        basis=MandatoryBasis.PRODUCT_SAFETY,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§Executive 5, §5.4",
                note="Human review event only: reviewer id, timestamp, inspection "
                "method/location, and an immutable audit event.",
            ),
            _PRACTICE,
        ),
        order=10,
        explanation_slot="explanation_human_review_event_only",
        accepted_document_class_ids=("rta.doc.title_certificate",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        physical_original_policy=PhysicalOriginalStatus.ORIGINAL_INSPECTED,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        waivable=False,
    ),
    _req(
        "R_C20_PRESENTATION_AND_DAY_BOOK",
        _C20,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(_RGD_PACK, _act("34")),
        order=11,
    ),
    _req(
        "R_C20_REGISTRATION_RESULT_RECORDED",
        _C20,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.LEGAL_REGISTRY,
        sources=(
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 49",
                note="The instrument takes effect on registration; export and "
                "signature are not completion.",
            ),
            _act("45(2)"),
            _RGD_PACK,
        ),
        order=12,
        accepted_document_class_ids=("rta.doc.title_certificate",),
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C21_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C21_REGISTERED_CURRENT_POA",
        _C21,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_RGD_PACK, _PRACTICE),
        order=1,
        accepted_document_class_ids=("rta.doc.power_of_attorney",),
        may_be_satisfied_by_combined_document=False,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C21_PRINCIPAL_AND_ATTORNEY_IDENTIFICATION",
        _C21,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("44"), _RGD_PACK),
        order=2,
        accepted_document_class_ids=(
            "rta.doc.nic",
            "rta.doc.passport",
            "rta.doc.driving_licence",
        ),
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C21_EXPRESS_TRANSACTION_CAPACITY",
        _C21,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE, _act("44")),
        order=3,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
        unsatisfied_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
    ),
    _req(
        "R_C21_REVOCATION_CHECKED",
        _C21,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            _PRACTICE,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="§6.4",
                note="Absence of a revocation document is not evidence that the "
                "power is still current.",
            ),
        ),
        order=4,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


_C22_REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    _req(
        "R_C22_CURRENT_SHARES_AND_RIGHTS",
        _C22,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_act("14(d)"), _act("48")),
        order=1,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C22_SEPARATE_INSTRUMENT_PER_COOWNER",
        _C22,
        basis=MandatoryBasis.OPERATIONAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(_RGD_PACK, _act("48")),
        order=2,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
    _req(
        "R_C22_NO_PROHIBITED_COOWNERSHIP_EFFECT",
        _C22,
        basis=MandatoryBasis.LEGAL,
        group=RequirementGroup.CONDITIONAL,
        sources=(
            SourceCitation(
                SRC_RTA_ACT.id,
                locator="s. 48",
                note="An instrument conferring co-ownership is invalid except as "
                "provided by the Act; this cannot be relabelled not applicable.",
            ),
        ),
        order=3,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.BLOCKING,
        unsatisfied_blocker_kind=BlockerKind.STATUTORY,
        waivable=False,
    ),
    _req(
        "R_C22_ALL_NECESSARY_PARTIES_JOINED",
        _C22,
        basis=MandatoryBasis.LAWYER_POLICY,
        group=RequirementGroup.CONDITIONAL,
        sources=(_PRACTICE, _act("48")),
        order=4,
        may_require_multiple_documents=True,
        default_applicability=ApplicabilityStatus.CONDITIONAL,
        unsatisfied_severity=IssueSeverity.HIGH_RISK,
    ),
)


REQUIREMENTS: tuple[RequirementDefinition, ...] = (
    *_C00_REQUIREMENTS,
    *_C01_REQUIREMENTS,
    *_C02_REQUIREMENTS,
    *_C03_REQUIREMENTS,
    *_C04_REQUIREMENTS,
    *_C05_REQUIREMENTS,
    *_C06_REQUIREMENTS,
    *_C07_REQUIREMENTS,
    *_C08_REQUIREMENTS,
    *_C09_REQUIREMENTS,
    *_C10_REQUIREMENTS,
    *_C11_REQUIREMENTS,
    *_C12_REQUIREMENTS,
    *_C13_REQUIREMENTS,
    *_C14_REQUIREMENTS,
    *_C15_REQUIREMENTS,
    *_C16_REQUIREMENTS,
    *_C17_REQUIREMENTS,
    *_C18_REQUIREMENTS,
    *_C19_REQUIREMENTS,
    *_C20_REQUIREMENTS,
    *_C21_REQUIREMENTS,
    *_C22_REQUIREMENTS,
)


REQUIREMENTS_BY_MODULE: dict[str, tuple[RequirementDefinition, ...]] = {
    _C00: _C00_REQUIREMENTS,
    _C01: _C01_REQUIREMENTS,
    _C02: _C02_REQUIREMENTS,
    _C03: _C03_REQUIREMENTS,
    _C04: _C04_REQUIREMENTS,
    _C05: _C05_REQUIREMENTS,
    _C06: _C06_REQUIREMENTS,
    _C07: _C07_REQUIREMENTS,
    _C08: _C08_REQUIREMENTS,
    _C09: _C09_REQUIREMENTS,
    _C10: _C10_REQUIREMENTS,
    _C11: _C11_REQUIREMENTS,
    _C12: _C12_REQUIREMENTS,
    _C13: _C13_REQUIREMENTS,
    _C14: _C14_REQUIREMENTS,
    _C15: _C15_REQUIREMENTS,
    _C16: _C16_REQUIREMENTS,
    _C17: _C17_REQUIREMENTS,
    _C18: _C18_REQUIREMENTS,
    _C19: _C19_REQUIREMENTS,
    _C20: _C20_REQUIREMENTS,
    _C21: _C21_REQUIREMENTS,
    _C22: _C22_REQUIREMENTS,
}


# ── Module catalogue (§5.2) ──────────────────────────────────────────────────
#
# `requirement_ids` is derived from REQUIREMENTS_BY_MODULE rather than repeated,
# so adding a requirement cannot leave its module unaware of it.

_MODULE_SOURCES: dict[str, tuple[SourceCitation, ...]] = {
    _C00: (_PRODUCT, _PRACTICE),
    _C01: (_act("43"), _act("44"), _act("45"), _RGD_PACK),
    _C02: (_act("32"), _act("33"), _act("37"), _act("44"), _RGD_PACK),
    _C03: (_act("34"), _act("35"), _RGD_SEARCH, _PRACTICE),
    _C04: (_act("4"), _act("10"), _act("36"), _act("44"), _PRACTICE),
    _C05: (_PRACTICE,),
    _C06: (_act("44"), _REG_FORMS, _PRACTICE),
    _C07: (_form("11"), _form("12"), _act("43"), _act("44"), _PRACTICE),
    _C08: (_form("10"), _form("29"), _form("36"), _PRACTICE),
    _C09: (_act("54"), _act("55"), _PRACTICE),
    _C10: (_PRACTICE,),
    _C11: (_local("council record set"), _PRACTICE),
    _C12: (_UDA, _PRACTICE),
    _C13: (_act("36"), _form("7"), _RGD_PACK),
    _C14: (_act("50-52"), _form("21"), _RGD_PACK),
    _C15: (_act("46"), _form("9"), _form("28"), _form("33"), _form("36")),
    _C16: (_act("75"), _form("35"), _PRACTICE),
    _C17: (_act("7-9"), _act("21-25"), _act("29-30"), _form("13"), _form("30")),
    _C18: (_REG_FORMS, _PRACTICE),
    _C19: (_act("24-25"), _act("56"), _form("25"), _form("34")),
    _C20: (_act("40-45"), _RGD_PACK, _RGD_FEES),
    _C21: (_RGD_PACK, _PRACTICE),
    _C22: (_act("14"), _act("48"), _RGD_PACK),
}

_MODULE_ORDER: tuple[str, ...] = (
    _C00,
    _C01,
    _C02,
    _C03,
    _C04,
    _C05,
    _C06,
    _C07,
    _C08,
    _C09,
    _C10,
    _C11,
    _C12,
    _C13,
    _C14,
    _C15,
    _C16,
    _C17,
    _C18,
    _C19,
    _C20,
    _C21,
    _C22,
)


def _module(module_id: str, order: int) -> ChecklistModuleDefinition:
    return ChecklistModuleDefinition(
        id=module_id,
        version=CHECKLIST_VERSION,
        label_key=f"rta.checklist_module.{module_id}.label",
        description_key=f"rta.checklist_module.{module_id}.description",
        requirement_ids=tuple(r.id for r in REQUIREMENTS_BY_MODULE[module_id]),
        sources=_MODULE_SOURCES[module_id],
        order=order,
    )


CHECKLIST_MODULES: tuple[ChecklistModuleDefinition, ...] = tuple(
    _module(module_id, order) for order, module_id in enumerate(_MODULE_ORDER)
)


# ── Registration packs (§5.5) ────────────────────────────────────────────────
#
# Operational shorthand, not new legal instruments. Each pack cites the RGD page
# it came from; that page carries no reliable last-modified date, so a pack is
# versioned and re-verified rather than treated as settled (§13.2.5).

RP_BASE = "RP-BASE"
RP_DUP = "RP-DUP"
RP_TC = "RP-TC"
RP_PLAN = "RP-PLAN"
RP_CONDO = "RP-CONDO"

REGISTRATION_PACKS: tuple[RegistrationPack, ...] = (
    RegistrationPack(
        id=RP_BASE,
        label_key="rta.registration_pack.RP-BASE.label",
        requirement_ids=(
            "R_C20_PRESCRIBED_INSTRUMENT_FORM",
            "R_C02_CURRENT_TITLE_CERTIFICATE",
            "R_C01_TRANSFEROR_CERTIFIED_ID",
            "R_C01_TRANSFEREE_CERTIFIED_ID",
            "R_C20_STAMP_DUTY_RECEIPT",
            "R_C20_REGISTRATION_FEE_AND_SUBMISSION",
        ),
        sources=(_RGD_PACK, _RGD_FEES),
    ),
    RegistrationPack(
        id=RP_DUP,
        label_key="rta.registration_pack.RP-DUP.label",
        requirement_ids=("R_C20_DUPLICATE_INSTRUMENT", "R_C20_PARTY_PHOTOGRAPHS"),
        sources=(
            SourceCitation(
                SRC_RGD_TRANSACTIONS.id,
                locator="Transactions page, duplicate and photograph rule",
                note="Currently stated for sale/transfer, gift, and exchange.",
            ),
        ),
    ),
    RegistrationPack(
        id=RP_TC,
        label_key="rta.registration_pack.RP-TC.label",
        requirement_ids=("R_C02_NEW_TITLE_CERTIFICATE_APPLICATION",),
        sources=(
            SourceCitation(
                SRC_RGD_TRANSACTIONS.id,
                locator="Transactions page, new Title Certificate",
                note="Operational Ti.Re.31. Not Gazette Form 31 (§Executive 11).",
            ),
            SourceCitation(SRC_TIRE_31_SCAN.id),
        ),
    ),
    RegistrationPack(
        id=RP_PLAN,
        label_key="rta.registration_pack.RP-PLAN.label",
        requirement_ids=(
            "R_C13_AUTHORIZED_SURVEYOR_PLAN",
            "R_C13_SURVEY_DEPARTMENT_CERTIFICATION",
        ),
        sources=(_act("36"), _RGD_PACK),
    ),
    RegistrationPack(
        id=RP_CONDO,
        label_key="rta.registration_pack.RP-CONDO.label",
        requirement_ids=(
            "R_C14_CONDOMINIUM_DECLARATION",
            "R_C14_CONDOMINIUM_PLAN_AND_CERTIFICATION",
            "R_C14_APARTMENT_OWNERSHIP_LAW_DOCUMENTS",
        ),
        sources=(_act("50-52"), _RGD_PACK),
    ),
)


#: §5.6, one row per prescribed instrument. A pack list is an operational
#: expectation about the submission bundle, not a statement that every listed
#: requirement is legally mandatory for that form.
SUBTYPE_REGISTRATION_PACKS: dict[str, tuple[str, ...]] = {
    "lk.rta.instrument.transfer_sale": (RP_BASE, RP_DUP, RP_TC),
    "lk.rta.instrument.sale_agreement": (RP_BASE,),
    "lk.rta.instrument.security_bond_transfer": (RP_BASE,),
    "lk.rta.instrument.certificate_sale_register": (RP_BASE,),
    "lk.rta.instrument.sale_agreement_cancel": (RP_BASE,),
    "lk.rta.instrument.gift": (RP_BASE, RP_DUP),
    "lk.rta.instrument.gift_cancel": (RP_BASE,),
    "lk.rta.instrument.life_interest_cancel": (RP_BASE,),
    "lk.rta.instrument.lease": (RP_BASE,),
    "lk.rta.instrument.lease_cancel": (RP_BASE,),
    "lk.rta.instrument.mortgage": (RP_BASE,),
    "lk.rta.instrument.mortgage_cancel": (RP_BASE,),
    "lk.rta.instrument.caveat": (RP_BASE,),
    "lk.rta.instrument.caveat_cancel": (RP_BASE,),
    "lk.rta.instrument.address_register": (RP_BASE,),
    "lk.rta.instrument.subdivision_amalgamation": (RP_BASE, RP_PLAN),
    "lk.rta.instrument.condominium_register": (RP_BASE, RP_CONDO),
    "lk.rta.instrument.land_exchange": (RP_BASE, RP_DUP),
    "lk.rta.instrument.life_interest_cancel_death": (RP_BASE,),
    "lk.rta.instrument.certificate_sale_cancel": (RP_BASE,),
    "lk.rta.instrument.servitude_access_transfer": (RP_BASE,),
    "lk.rta.instrument.life_interest_holder_lease": (RP_BASE,),
}


# ── Lookups ──────────────────────────────────────────────────────────────────

_REQUIREMENTS_BY_ID: dict[str, RequirementDefinition] = {r.id: r for r in REQUIREMENTS}
_MODULES_BY_ID: dict[str, ChecklistModuleDefinition] = {m.id: m for m in CHECKLIST_MODULES}
_PACKS_BY_ID: dict[str, RegistrationPack] = {p.id: p for p in REGISTRATION_PACKS}


def get_requirement(requirement_id: str) -> RequirementDefinition | None:
    return _REQUIREMENTS_BY_ID.get(requirement_id)


def require_requirement(requirement_id: str) -> RequirementDefinition:
    requirement = _REQUIREMENTS_BY_ID.get(requirement_id)
    if requirement is None:
        raise KeyError(f"Unknown checklist requirement: {requirement_id}")
    return requirement


def get_module(module_id: str) -> ChecklistModuleDefinition | None:
    return _MODULES_BY_ID.get(module_id)


def require_module(module_id: str) -> ChecklistModuleDefinition:
    module = _MODULES_BY_ID.get(module_id)
    if module is None:
        raise KeyError(f"Unknown checklist module: {module_id}")
    return module


def requirements_for_module(module_id: str) -> tuple[RequirementDefinition, ...]:
    """Empty tuple for an unknown module: the compiler skips what it cannot resolve."""
    return REQUIREMENTS_BY_MODULE.get(module_id, ())


def all_module_ids() -> tuple[str, ...]:
    return tuple(m.id for m in CHECKLIST_MODULES)


def get_registration_pack(pack_id: str) -> RegistrationPack | None:
    return _PACKS_BY_ID.get(pack_id)


def registration_packs_for_subtype(subtype_id: str) -> tuple[RegistrationPack, ...]:
    return tuple(
        pack
        for pack_id in SUBTYPE_REGISTRATION_PACKS.get(subtype_id, ())
        if (pack := _PACKS_BY_ID.get(pack_id)) is not None
    )
