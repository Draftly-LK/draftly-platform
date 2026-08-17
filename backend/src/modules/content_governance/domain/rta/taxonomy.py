"""RTA matter taxonomy — regime, family, exact subtype, conditional module.

```text
Legal regime
  -> Matter family
    -> Exact instrument subtype or statutory process
      -> Conditional scenario modules
```

The 22 Gazette instruments are **exact subtypes, not 22 top-level tiles**
(§Executive 2). The UI selects a family first, then requires selection and
lawyer confirmation of the exact prescribed instrument.

Stable IDs never change; display labels are translation keys and may.
Mapping source: Gazette Extraordinary No. 2308/27 (2022), amendment to
regulation 15(1), items (i)-(xxii) — recorded as a source citation on every
instrument rather than merely copied into code (§3.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.modules.content_governance.domain.enums import (
    ExaminationLevel,
    LegalRegime,
    MatterFamily,
    ReleaseTier,
    SubtypeKind,
)
from src.modules.content_governance.domain.sources import (
    SRC_GAZETTE_2022,
    SRC_LAWYER_PRACTICE,
    SRC_PRODUCT_SAFETY,
    SRC_RGD_TRANSACTIONS,
    SRC_RTA_ACT,
    SRC_TIRE_31_SCAN,
    SourceCitation,
)

#: Bumped whenever a subtype is added, retired, or re-tiered. Pinned into every
#: checklist snapshot and preflight so a rule change is never retroactive.
TAXONOMY_VERSION = "1.0.0"

REGIME_ID = LegalRegime.LK_RTA.value


# ── Family definitions ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class FamilyDefinition:
    """One lawyer-facing grouping shown on the New Matter screen (§3.2)."""

    id: MatterFamily
    label_key: str
    purpose_key: str
    #: Families that describe statutory processes rather than dispositions are
    #: presented separately from the six transaction families.
    is_transaction_family: bool = True
    order: int = 0


FAMILIES: tuple[FamilyDefinition, ...] = (
    FamilyDefinition(
        id=MatterFamily.OWNERSHIP_CHANGE,
        label_key="rta.family.ownership_change.label",
        purpose_key="rta.family.ownership_change.purpose",
        order=1,
    ),
    FamilyDefinition(
        id=MatterFamily.AGREEMENT_SECURITY,
        label_key="rta.family.agreement_security.label",
        purpose_key="rta.family.agreement_security.purpose",
        order=2,
    ),
    FamilyDefinition(
        id=MatterFamily.USE_INTEREST,
        label_key="rta.family.use_interest.label",
        purpose_key="rta.family.use_interest.purpose",
        order=3,
    ),
    FamilyDefinition(
        id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.family.cancel_release.label",
        purpose_key="rta.family.cancel_release.purpose",
        order=4,
    ),
    FamilyDefinition(
        id=MatterFamily.NOTICE_ADMIN,
        label_key="rta.family.notice_admin.label",
        purpose_key="rta.family.notice_admin.purpose",
        order=5,
    ),
    FamilyDefinition(
        id=MatterFamily.PARCEL_STRUCTURE,
        label_key="rta.family.parcel_structure.label",
        purpose_key="rta.family.parcel_structure.purpose",
        order=6,
    ),
    FamilyDefinition(
        id=MatterFamily.TITLE_SETTLEMENT,
        label_key="rta.family.title_settlement.label",
        purpose_key="rta.family.title_settlement.purpose",
        is_transaction_family=False,
        order=7,
    ),
    FamilyDefinition(
        id=MatterFamily.DISPUTE_RECTIFICATION,
        label_key="rta.family.dispute_rectification.label",
        purpose_key="rta.family.dispute_rectification.purpose",
        is_transaction_family=False,
        order=8,
    ),
    FamilyDefinition(
        id=MatterFamily.CONTROLLED_OTHER,
        label_key="rta.family.controlled_other.label",
        purpose_key="rta.family.controlled_other.purpose",
        is_transaction_family=False,
        order=9,
    ),
)


# ── Subtype definitions ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SubtypeDefinition:
    """One exact instrument, statutory process, or registry service (§3.3, §3.4).

    ``gazette_form_number`` is display metadata only. The authoritative pointer
    at a template is ``form_template_id``, which is namespaced so Gazette Form
    31 and operational Ti.Re.31 cannot collide (§9.1).
    """

    id: str
    kind: SubtypeKind
    family_id: MatterFamily
    label_key: str
    examination_level: ExaminationLevel
    release_tier: ReleaseTier
    sources: tuple[SourceCitation, ...]
    gazette_form_number: str | None = None
    form_template_id: str | None = None
    #: Additional operational forms produced alongside the prescribed
    #: instrument — for a transfer, the Ti.Re.31 title-certificate application.
    companion_template_ids: tuple[str, ...] = ()
    default_module_definition_ids: tuple[str, ...] = ()
    #: Why this subtype cannot reach automated V0 output, when it cannot.
    out_of_v0_reason_key: str | None = None
    #: True only for subtypes that require a legal basis typed by the lawyer.
    requires_declared_legal_basis: bool = False
    order: int = 0

    @property
    def is_prescribed_instrument(self) -> bool:
        return self.kind is SubtypeKind.PRESCRIBED_INSTRUMENT


_GZ = SourceCitation(
    SRC_GAZETTE_2022.id,
    locator="regulation 15(1) amendment, items (i)-(xxii)",
)


def _gz(item: str, form: str) -> SourceCitation:
    return SourceCitation(
        SRC_GAZETTE_2022.id,
        locator=f"regulation 15(1) amendment, item ({item}); Form {form}",
    )


def _act(section: str) -> SourceCitation:
    return SourceCitation(SRC_RTA_ACT.id, locator=f"s. {section}")


# The 22 prescribed instruments, in the Gazette's own item order (§3.3).
PRESCRIBED_INSTRUMENTS: tuple[SubtypeDefinition, ...] = (
    SubtypeDefinition(
        id="lk.rta.instrument.transfer_sale",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.OWNERSHIP_CHANGE,
        label_key="rta.subtype.transfer_sale",
        examination_level=ExaminationLevel.FULL,
        release_tier=ReleaseTier.V0,
        gazette_form_number="8",
        form_template_id="rta.reg.2022.form.08",
        companion_template_ids=("rta.ops.tire.31",),
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C20_STAMP_REGISTRATION",
        ),
        sources=(_gz("i", "8"), _act("43"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        order=1,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.sale_agreement",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.AGREEMENT_SECURITY,
        label_key="rta.subtype.sale_agreement",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V1,
        gazette_form_number="23",
        form_template_id="rta.reg.2022.form.23",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("ii", "23"),),
        order=2,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.security_bond_transfer",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.AGREEMENT_SECURITY,
        label_key="rta.subtype.security_bond_transfer",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="24",
        form_template_id="rta.reg.2022.form.24",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C07_MORTGAGE_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.specialist_validation_required",
        sources=(_gz("iii", "24"),),
        order=3,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.certificate_sale_register",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.OWNERSHIP_CHANGE,
        label_key="rta.subtype.certificate_sale_register",
        examination_level=ExaminationLevel.FULL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="25",
        form_template_id="rta.reg.2022.form.25",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C19_COURT_STATUTORY_SALE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.court_or_statutory_sale",
        sources=(_gz("iv", "25"), _act("56")),
        order=4,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.sale_agreement_cancel",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.sale_agreement_cancel",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V1,
        gazette_form_number="26",
        form_template_id="rta.reg.2022.form.26",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C06_ENCUMBRANCES",
            "C18_CANCELLATION_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("v", "26"),),
        order=5,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.gift",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.OWNERSHIP_CHANGE,
        label_key="rta.subtype.gift",
        examination_level=ExaminationLevel.FULL,
        release_tier=ReleaseTier.V1,
        gazette_form_number="9",
        form_template_id="rta.reg.2022.form.09",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C15_LIFE_INTEREST",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("vi", "9"), _act("46")),
        order=6,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.gift_cancel",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.gift_cancel",
        examination_level=ExaminationLevel.FULL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="27",
        form_template_id="rta.reg.2022.form.27",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C15_LIFE_INTEREST",
            "C18_CANCELLATION_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.specialist_validation_required",
        sources=(_gz("vii", "27"),),
        order=7,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.life_interest_cancel",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.life_interest_cancel",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V1,
        gazette_form_number="28",
        form_template_id="rta.reg.2022.form.28",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C15_LIFE_INTEREST",
            "C18_CANCELLATION_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("viii", "28"), _act("46")),
        order=8,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.lease",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.USE_INTEREST,
        label_key="rta.subtype.lease",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V1,
        gazette_form_number="10",
        form_template_id="rta.reg.2022.form.10",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C08_LEASE_OCCUPATION",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("ix", "10"),),
        order=9,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.lease_cancel",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.lease_cancel",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V1,
        gazette_form_number="29",
        form_template_id="rta.reg.2022.form.29",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C08_LEASE_OCCUPATION",
            "C18_CANCELLATION_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("x", "29"),),
        order=10,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.mortgage",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.AGREEMENT_SECURITY,
        label_key="rta.subtype.mortgage",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V1,
        gazette_form_number="11",
        form_template_id="rta.reg.2022.form.11",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C07_MORTGAGE_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("xi", "11"),),
        order=11,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.mortgage_cancel",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.mortgage_cancel",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V0,
        gazette_form_number="12",
        form_template_id="rta.reg.2022.form.12",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C07_MORTGAGE_RELEASE",
            "C18_CANCELLATION_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        sources=(_gz("xii", "12"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        order=12,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.caveat",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.NOTICE_ADMIN,
        label_key="rta.subtype.caveat",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="13",
        form_template_id="rta.reg.2022.form.13",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C17_CAVEAT_LITIGATION",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.grounds_need_lawyer_analysis",
        sources=(_gz("xiii", "13"),),
        order=13,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.caveat_cancel",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.caveat_cancel",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="30",
        form_template_id="rta.reg.2022.form.30",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C17_CAVEAT_LITIGATION",
            "C18_CANCELLATION_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.grounds_need_lawyer_analysis",
        sources=(_gz("xiv", "30"),),
        order=14,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.address_register",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.NOTICE_ADMIN,
        label_key="rta.subtype.address_register",
        examination_level=ExaminationLevel.MINIMAL,
        release_tier=ReleaseTier.V1,
        gazette_form_number="31",
        # Gazette Form 31 registers an ADDRESS. It is not the operational
        # Ti.Re.31 title-certificate application (§Executive 11).
        form_template_id="rta.reg.2022.form.31",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("xv", "31"),),
        order=15,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.subdivision_amalgamation",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.PARCEL_STRUCTURE,
        label_key="rta.subtype.subdivision_amalgamation",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="7",
        form_template_id="rta.reg.2022.form.07",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C13_SUBDIVISION_AMALGAMATION",
            "C17_CAVEAT_LITIGATION",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.parcel_restructure",
        sources=(_gz("xvi", "7"), _act("36")),
        order=16,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.condominium_register",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.PARCEL_STRUCTURE,
        label_key="rta.subtype.condominium_register",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="21",
        form_template_id="rta.reg.2022.form.21",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C14_CONDOMINIUM_STRATA",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.condominium",
        sources=(_gz("xvii", "21"), _act("50-52")),
        order=17,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.land_exchange",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.OWNERSHIP_CHANGE,
        label_key="rta.subtype.land_exchange",
        examination_level=ExaminationLevel.FULL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="32",
        form_template_id="rta.reg.2022.form.32",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.two_parcel_examination",
        sources=(_gz("xviii", "32"),),
        order=18,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.life_interest_cancel_death",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.life_interest_cancel_death",
        examination_level=ExaminationLevel.FOCUSED,
        release_tier=ReleaseTier.V1,
        gazette_form_number="33",
        form_template_id="rta.reg.2022.form.33",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C09_PROBATE_TRANSMISSION",
            "C15_LIFE_INTEREST",
            "C18_CANCELLATION_RELEASE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.subtype_not_piloted",
        sources=(_gz("xix", "33"),),
        order=19,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.certificate_sale_cancel",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.CANCEL_RELEASE,
        label_key="rta.subtype.certificate_sale_cancel",
        examination_level=ExaminationLevel.FULL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="34",
        form_template_id="rta.reg.2022.form.34",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C18_CANCELLATION_RELEASE",
            "C19_COURT_STATUTORY_SALE",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.court_or_statutory_sale",
        sources=(_gz("xx", "34"),),
        order=20,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.servitude_access_transfer",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.USE_INTEREST,
        label_key="rta.subtype.servitude_access_transfer",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="35",
        form_template_id="rta.reg.2022.form.35",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C16_SERVITUDE_ACCESS",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.servitude_analysis",
        sources=(_gz("xxi", "35"), _act("75")),
        order=21,
    ),
    SubtypeDefinition(
        id="lk.rta.instrument.life_interest_holder_lease",
        kind=SubtypeKind.PRESCRIBED_INSTRUMENT,
        family_id=MatterFamily.USE_INTEREST,
        label_key="rta.subtype.life_interest_holder_lease",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.DEFERRED,
        gazette_form_number="36",
        form_template_id="rta.reg.2022.form.36",
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C03_REGISTRY_SEARCH",
            "C04_SURVEY_CADASTRAL",
            "C06_ENCUMBRANCES",
            "C08_LEASE_OCCUPATION",
            "C15_LIFE_INTEREST",
            "C20_STAMP_REGISTRATION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.life_interest",
        sources=(_gz("xxii", "36"),),
        order=22,
    ),
)


# Additional RTA processes and registry services — deliberately NOT part of the
# 22 (§3.4). Initial compilation in particular is a different statutory process
# from a subsequent transfer (§Executive 1).
ADDITIONAL_PROCESSES: tuple[SubtypeDefinition, ...] = (
    SubtypeDefinition(
        id="lk.rta.process.initial_compilation",
        kind=SubtypeKind.STATUTORY_PROCESS,
        family_id=MatterFamily.TITLE_SETTLEMENT,
        label_key="rta.process.initial_compilation",
        examination_level=ExaminationLevel.TRACKING,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=("C00_MATTER_ADMIN", "C17_CAVEAT_LITIGATION"),
        out_of_v0_reason_key="rta.v0_exclusion.initial_compilation",
        sources=(_act("10-27"),),
        order=101,
    ),
    SubtypeDefinition(
        id="lk.rta.process.transmission_testate",
        kind=SubtypeKind.STATUTORY_PROCESS,
        family_id=MatterFamily.TITLE_SETTLEMENT,
        label_key="rta.process.transmission_testate",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C09_PROBATE_TRANSMISSION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.transmission",
        sources=(_act("54"),),
        order=102,
    ),
    SubtypeDefinition(
        id="lk.rta.process.transmission_intestate",
        kind=SubtypeKind.STATUTORY_PROCESS,
        family_id=MatterFamily.TITLE_SETTLEMENT,
        label_key="rta.process.transmission_intestate",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C09_PROBATE_TRANSMISSION",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.transmission",
        sources=(_act("55"),),
        order=103,
    ),
    SubtypeDefinition(
        id="lk.rta.process.court_order_owner_register",
        kind=SubtypeKind.STATUTORY_PROCESS,
        family_id=MatterFamily.TITLE_SETTLEMENT,
        label_key="rta.process.court_order_owner_register",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
            "C19_COURT_STATUTORY_SALE",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.court_or_statutory_sale",
        sources=(_act("56"),),
        order=104,
    ),
    SubtypeDefinition(
        id="lk.rta.process.second_class_challenge",
        kind=SubtypeKind.STATUTORY_PROCESS,
        family_id=MatterFamily.DISPUTE_RECTIFICATION,
        label_key="rta.process.second_class_challenge",
        examination_level=ExaminationLevel.TRACKING,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=("C00_MATTER_ADMIN", "C17_CAVEAT_LITIGATION"),
        out_of_v0_reason_key="rta.v0_exclusion.litigation_hold",
        sources=(_act("29-30"),),
        order=105,
    ),
    SubtypeDefinition(
        id="lk.rta.process.rectification_indemnity",
        kind=SubtypeKind.STATUTORY_PROCESS,
        family_id=MatterFamily.DISPUTE_RECTIFICATION,
        label_key="rta.process.rectification_indemnity",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=("C00_MATTER_ADMIN", "C17_CAVEAT_LITIGATION"),
        out_of_v0_reason_key="rta.v0_exclusion.rectification",
        sources=(_act("58-62"),),
        order=106,
    ),
    SubtypeDefinition(
        id="lk.rta.process.title_settlement_dispute",
        kind=SubtypeKind.STATUTORY_PROCESS,
        family_id=MatterFamily.DISPUTE_RECTIFICATION,
        label_key="rta.process.title_settlement_dispute",
        examination_level=ExaminationLevel.TRACKING,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=("C00_MATTER_ADMIN", "C17_CAVEAT_LITIGATION"),
        out_of_v0_reason_key="rta.v0_exclusion.litigation_hold",
        sources=(_act("7-9"), _act("21-25")),
        order=107,
    ),
)

REGISTRY_SERVICES: tuple[SubtypeDefinition, ...] = (
    SubtypeDefinition(
        id="lk.rta.service.inspect_title_register",
        kind=SubtypeKind.REGISTRY_SERVICE,
        family_id=MatterFamily.NOTICE_ADMIN,
        label_key="rta.service.inspect_title_register",
        examination_level=ExaminationLevel.MINIMAL,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=("C00_MATTER_ADMIN", "C03_REGISTRY_SEARCH"),
        out_of_v0_reason_key="rta.v0_exclusion.administrative_service",
        sources=(_act("34"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        order=201,
    ),
    SubtypeDefinition(
        id="lk.rta.service.certified_extract",
        kind=SubtypeKind.REGISTRY_SERVICE,
        family_id=MatterFamily.NOTICE_ADMIN,
        label_key="rta.service.certified_extract",
        examination_level=ExaminationLevel.MINIMAL,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=("C00_MATTER_ADMIN", "C03_REGISTRY_SEARCH"),
        out_of_v0_reason_key="rta.v0_exclusion.administrative_service",
        sources=(_act("35"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        order=202,
    ),
    SubtypeDefinition(
        id="lk.rta.service.new_title_certificate_application",
        kind=SubtypeKind.REGISTRY_SERVICE,
        family_id=MatterFamily.NOTICE_ADMIN,
        label_key="rta.service.new_title_certificate_application",
        examination_level=ExaminationLevel.MINIMAL,
        release_tier=ReleaseTier.V0,
        # Operational Ti.Re.31 — a title-certificate application, NOT Gazette
        # Form 31. Different namespace, different template, different ID.
        form_template_id="rta.ops.tire.31",
        default_module_definition_ids=("C00_MATTER_ADMIN", "C02_RTA_TITLE"),
        sources=(
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="new Title Certificate"),
            SourceCitation(SRC_TIRE_31_SCAN.id),
        ),
        order=203,
    ),
)

CONTROLLED_OTHER: tuple[SubtypeDefinition, ...] = (
    SubtypeDefinition(
        id="lk.rta.instrument.other_declared_instrument",
        kind=SubtypeKind.CONTROLLED_OTHER,
        family_id=MatterFamily.CONTROLLED_OTHER,
        label_key="rta.subtype.other_declared_instrument",
        examination_level=ExaminationLevel.SPECIAL,
        release_tier=ReleaseTier.MANUAL_ONLY,
        default_module_definition_ids=(
            "C00_MATTER_ADMIN",
            "C01_IDENTITY_CAPACITY",
            "C02_RTA_TITLE",
        ),
        out_of_v0_reason_key="rta.v0_exclusion.other_declared_instrument",
        requires_declared_legal_basis=True,
        sources=(
            _GZ,
            SourceCitation(
                SRC_PRODUCT_SAFETY.id,
                locator="controlled fallback",
                note=(
                    "Never a default classification. Requires the lawyer to "
                    "supply a legal basis and confirm the exact instrument."
                ),
            ),
        ),
        order=999,
    ),
)


ALL_SUBTYPES: tuple[SubtypeDefinition, ...] = (
    *PRESCRIBED_INSTRUMENTS,
    *ADDITIONAL_PROCESSES,
    *REGISTRY_SERVICES,
    *CONTROLLED_OTHER,
)


# ── Conditional scenario modules (§3.5) ──────────────────────────────────────


@dataclass(frozen=True)
class ConditionalModuleDefinition:
    """A fact about the parties or property, not a transaction type (§3.5).

    A lawyer may add or remove a suggested module, but removing a rule-triggered
    one requires a recorded reason, and a statutory blocker cannot be removed by
    relabelling it "not applicable".
    """

    id: str
    label_key: str
    checklist_module_ids: tuple[str, ...]
    #: True when triggering this module leaves the automated V0 path.
    excludes_v0: bool = False
    sources: tuple[SourceCitation, ...] = field(default_factory=tuple)


CONDITIONAL_MODULES: tuple[ConditionalModuleDefinition, ...] = (
    ConditionalModuleDefinition(
        "lk.rta.module.company_party",
        "rta.module.company_party",
        ("C10_COMPANY_AUTHORITY",),
        excludes_v0=True,
        sources=(SourceCitation(SRC_LAWYER_PRACTICE.id),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.estate_or_deceased_owner",
        "rta.module.estate_or_deceased_owner",
        ("C09_PROBATE_TRANSMISSION",),
        excludes_v0=True,
        sources=(_act("54"), _act("55")),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.power_of_attorney",
        "rta.module.power_of_attorney",
        ("C21_POWER_OF_ATTORNEY",),
        excludes_v0=True,
        sources=(SourceCitation(SRC_RGD_TRANSACTIONS.id),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.coowners",
        "rta.module.coowners",
        ("C22_COOWNERS",),
        excludes_v0=True,
        sources=(_act("48"), _act("14")),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.mortgage_present",
        "rta.module.mortgage_present",
        ("C07_MORTGAGE_RELEASE",),
        sources=(_act("44"),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.lease_or_occupation",
        "rta.module.lease_or_occupation",
        ("C08_LEASE_OCCUPATION",),
        sources=(SourceCitation(SRC_LAWYER_PRACTICE.id),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.life_interest",
        "rta.module.life_interest",
        ("C15_LIFE_INTEREST",),
        excludes_v0=True,
        sources=(_act("46"),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.servitude",
        "rta.module.servitude",
        ("C16_SERVITUDE_ACCESS",),
        sources=(_act("75"),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.building_present",
        "rta.module.building_present",
        ("C12_BUILDING_COMPLIANCE",),
        sources=(SourceCitation("src.lk.uda.ops.approvals"),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.local_authority_clearance",
        "rta.module.local_authority_clearance",
        ("C11_LOCAL_AUTHORITY",),
        sources=(SourceCitation("src.local_ops.council_records"),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.missing_original",
        "rta.module.missing_original",
        (),
        sources=(SourceCitation(SRC_LAWYER_PRACTICE.id),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.active_notice_or_litigation",
        "rta.module.active_notice_or_litigation",
        ("C17_CAVEAT_LITIGATION",),
        excludes_v0=True,
        sources=(_act("21-25"), _act("29-30")),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.court_or_statutory_sale",
        "rta.module.court_or_statutory_sale",
        ("C19_COURT_STATUTORY_SALE",),
        excludes_v0=True,
        sources=(_act("24-25"), _act("56")),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.state_land",
        "rta.module.state_land",
        (),
        excludes_v0=True,
        sources=(SourceCitation(SRC_LAWYER_PRACTICE.id),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.special_personal_law",
        "rta.module.special_personal_law",
        (),
        excludes_v0=True,
        sources=(SourceCitation(SRC_LAWYER_PRACTICE.id),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.subdivision_amalgamation",
        "rta.module.subdivision_amalgamation",
        ("C13_SUBDIVISION_AMALGAMATION",),
        excludes_v0=True,
        sources=(_act("36"),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.condominium_strata",
        "rta.module.condominium_strata",
        ("C14_CONDOMINIUM_STRATA",),
        excludes_v0=True,
        sources=(_act("50-52"),),
    ),
    ConditionalModuleDefinition(
        "lk.rta.module.initial_compilation_triage",
        "rta.module.initial_compilation_triage",
        ("C17_CAVEAT_LITIGATION",),
        excludes_v0=True,
        sources=(_act("10-27"),),
    ),
)


# ── Legacy migration (§3.6) ──────────────────────────────────────────────────
#
# The retired M2 `MatterType` vocabulary maps forward. Migration is
# non-destructive: the legacy value is preserved on the matter, the exact
# subtype is marked PROVISIONAL, and `other` never auto-approves.

LEGACY_MATTER_TYPE_MAP: dict[str, str] = {
    "transfer": "lk.rta.instrument.transfer_sale",
    "gift": "lk.rta.instrument.gift",
    "lease": "lk.rta.instrument.lease",
    "mortgage": "lk.rta.instrument.mortgage",
    "other": "lk.rta.instrument.other_declared_instrument",
}

#: Conditional modules a legacy migration must switch on, because the legacy
#: type carried none of the screening the exact subtype requires (§3.6).
LEGACY_MIGRATION_SCREENING: dict[str, tuple[str, ...]] = {
    "transfer": (),
    "gift": ("lk.rta.module.life_interest",),
    "lease": ("lk.rta.module.lease_or_occupation",),
    "mortgage": ("lk.rta.module.mortgage_present",),
    "other": (),
}


@dataclass(frozen=True)
class LegacyMigrationResult:
    """What a legacy `MatterType` becomes, and what still has to be decided."""

    legacy_type: str
    subtype_id: str
    family_id: MatterFamily
    #: Always PROVISIONAL — a migration is not a lawyer's confirmation (§3.6).
    needs_lawyer_confirmation: bool
    activated_conditional_module_ids: tuple[str, ...]
    #: Legacy documents are UNREVIEWED_LEGACY, never "type = other" (§3.6).
    legacy_document_classification_status: str
    requires_declared_legal_basis: bool


LEGACY_DOCUMENT_CLASSIFICATION_STATUS = "UNREVIEWED_LEGACY"


def migrate_legacy_matter_type(legacy_type: str) -> LegacyMigrationResult:
    """Map a retired M2 ``MatterType`` onto the exact-subtype taxonomy.

    Raises ``KeyError`` for an unrecognised legacy value rather than guessing:
    silently defaulting to ``other`` is exactly the false assumption §3.6
    forbids.
    """
    subtype_id = LEGACY_MATTER_TYPE_MAP[legacy_type]
    subtype = require_subtype(subtype_id)
    return LegacyMigrationResult(
        legacy_type=legacy_type,
        subtype_id=subtype_id,
        family_id=subtype.family_id,
        needs_lawyer_confirmation=True,
        activated_conditional_module_ids=LEGACY_MIGRATION_SCREENING[legacy_type],
        legacy_document_classification_status=LEGACY_DOCUMENT_CLASSIFICATION_STATUS,
        requires_declared_legal_basis=subtype.requires_declared_legal_basis,
    )


# ── Lookups ──────────────────────────────────────────────────────────────────

_SUBTYPES_BY_ID: dict[str, SubtypeDefinition] = {s.id: s for s in ALL_SUBTYPES}
_FAMILIES_BY_ID: dict[MatterFamily, FamilyDefinition] = {f.id: f for f in FAMILIES}
_CONDITIONAL_BY_ID: dict[str, ConditionalModuleDefinition] = {m.id: m for m in CONDITIONAL_MODULES}


def get_subtype(subtype_id: str) -> SubtypeDefinition | None:
    return _SUBTYPES_BY_ID.get(subtype_id)


def require_subtype(subtype_id: str) -> SubtypeDefinition:
    subtype = _SUBTYPES_BY_ID.get(subtype_id)
    if subtype is None:
        raise KeyError(f"Unknown RTA subtype '{subtype_id}'.")
    return subtype


def get_family(family_id: MatterFamily) -> FamilyDefinition | None:
    return _FAMILIES_BY_ID.get(family_id)


def subtypes_in_family(family_id: MatterFamily) -> tuple[SubtypeDefinition, ...]:
    return tuple(s for s in ALL_SUBTYPES if s.family_id is family_id)


def get_conditional_module(module_id: str) -> ConditionalModuleDefinition | None:
    return _CONDITIONAL_BY_ID.get(module_id)


def v0_subtype_ids() -> tuple[str, ...]:
    """The subtypes that may produce an automated V0 registration-oriented draft."""
    return tuple(s.id for s in ALL_SUBTYPES if s.release_tier is ReleaseTier.V0)
