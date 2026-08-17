"""Controlled document classes and the confidence/automation policy.

Two things live here because they are the same decision seen from two sides:
*what* an uploaded file may be classified as (§14.4), and *how far* the pipeline
may act on that classification without a lawyer (§6.4).

Rules that matter:

- ``UNIDENTIFIED`` is a supported outcome, not a failure. A file the classifier
  cannot place stays in the inbox as ``rta.doc.unidentified``; it is never
  permanently relabelled ``other`` and never discarded (§6.3).
- One file may satisfy several checklist items — a council may issue one
  combined certificate — so the model is requirement-to-document many-to-many.
  This catalogue does not store which requirements a class satisfies; the
  checklist owns that direction (§6.3, §1.2).
- No confidence value auto-confirms a critical fact, a physical original, or a
  negative proposition (§6.4). ``may_auto_confirm_critical_fact`` makes the
  critical-fact half of that testable rather than a comment someone can forget;
  the negative-proposition half is carried by ``facts.py``
  (``negative_requires_search_evidence``), and original inspection is a
  human-only event that this module never scores.
"""

from __future__ import annotations

from dataclasses import dataclass

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

#: Bumped whenever a class is added, retired, or re-scoped. A stored
#: ``DetectedDocument.classId`` is meaningless without the version that
#: produced it, so classification runs pin this alongside the taxonomy version.
DOCUMENT_CLASSES_VERSION = "1.0.0"

UNIDENTIFIED_DOCUMENT_CLASS_ID = "rta.doc.unidentified"
COMBINED_CERTIFICATE_CLASS_ID = "rta.doc.combined_local_authority_certificate"


def _act(section: str) -> SourceCitation:
    return SourceCitation(SRC_RTA_ACT.id, locator=f"s. {section}")


def _gz(form: str) -> SourceCitation:
    return SourceCitation(SRC_GAZETTE_2022.id, locator=f"regulation 15(1) amendment; Form {form}")


def _ops(locator: str) -> SourceCitation:
    return SourceCitation(SRC_RGD_TRANSACTIONS.id, locator=locator)


def _charges(locator: str) -> SourceCitation:
    return SourceCitation(SRC_RGD_CHARGES.id, locator=locator)


def _uda(locator: str) -> SourceCitation:
    return SourceCitation(SRC_UDA_APPROVALS.id, locator=locator)


def _practice(locator: str) -> SourceCitation:
    return SourceCitation(SRC_LAWYER_PRACTICE.id, locator=locator)


def _local(locator: str) -> SourceCitation:
    return SourceCitation(SRC_LOCAL_AUTHORITY.id, locator=locator)


def _product(locator: str) -> SourceCitation:
    return SourceCitation(SRC_PRODUCT_SAFETY.id, locator=locator)


@dataclass(frozen=True)
class DocumentClassDefinition:
    """One controlled class an uploaded document may be assigned (§14.4)."""

    id: str
    label_key: str
    description_key: str
    #: Checklist requirement ids this class can help satisfy are NOT stored
    #: here — the checklist owns that direction. These are reverse-lookup tags
    #: drawn from the checklist module vocabulary (``C02_RTA_TITLE``, …) so the
    #: inbox can offer "documents relevant to this module" without inverting a
    #: satisfaction rule it does not own.
    tags: tuple[str, ...] = ()
    #: True when one uploaded file of this class commonly satisfies several
    #: checklist items (§6.3 combined certificate).
    may_satisfy_multiple_requirements: bool = False
    #: True when this class is a red flag whose presence must raise an issue.
    red_flag: bool = False
    #: True when the class exists to route a matter OUT of V0.
    exclusion_indicator: bool = False
    #: Existing extraction registry kind, where one exists — the literal is
    #: kept in sync by hand with ``modules/document/domain/registry.py``
    #: ``registered_kinds()``; the domain does not import another module's
    #: infrastructure vocabulary.
    extraction_template_kind: str | None = None
    order: int = 0
    #: §13.2 — a class that asserts an evidentiary or operational expectation
    #: names its authority. Empty only for product-defined outcomes, which cite
    #: the product-safety record instead.
    sources: tuple[SourceCitation, ...] = ()


DOCUMENT_CLASSES: tuple[DocumentClassDefinition, ...] = (
    # ── Title record (§14.4 item 1) ──────────────────────────────────────────
    DocumentClassDefinition(
        id="rta.doc.title_certificate",
        label_key="rta.doc.title_certificate.label",
        description_key="rta.doc.title_certificate.description",
        tags=("C02_RTA_TITLE", "C04_SURVEY_CADASTRAL"),
        extraction_template_kind="title-certificate",
        order=1,
        sources=(_act("37"), _act("44"), _ops("Transactions page, submission pack")),
    ),
    DocumentClassDefinition(
        id="rta.doc.title_register_extract",
        label_key="rta.doc.title_register_extract.label",
        description_key="rta.doc.title_register_extract.description",
        tags=("C02_RTA_TITLE", "C03_REGISTRY_SEARCH", "C06_ENCUMBRANCES"),
        may_satisfy_multiple_requirements=True,
        order=2,
        sources=(_act("32-35"), _ops("Transactions page, inspection and certified extract")),
    ),
    # ── Prescribed instruments and the operational application (items 2-3) ───
    DocumentClassDefinition(
        id="rta.doc.form8_instrument",
        label_key="rta.doc.form8_instrument.label",
        description_key="rta.doc.form8_instrument.description",
        tags=("C01_IDENTITY_CAPACITY", "C02_RTA_TITLE", "C20_STAMP_REGISTRATION"),
        extraction_template_kind="form8-instrument",
        order=3,
        sources=(_gz("8"), _act("43")),
    ),
    DocumentClassDefinition(
        id="rta.doc.form12_instrument",
        label_key="rta.doc.form12_instrument.label",
        description_key="rta.doc.form12_instrument.description",
        tags=("C07_MORTGAGE_RELEASE", "C18_CANCELLATION_RELEASE", "C20_STAMP_REGISTRATION"),
        order=4,
        sources=(_gz("12"), _act("43")),
    ),
    # Ti.Re.31 is an operational application for a Title Certificate. It is a
    # different document from Gazette Form 31 (register an address) and the two
    # must never share a class or a template namespace (§1.2, §9.1).
    DocumentClassDefinition(
        id="rta.doc.tire31_application",
        label_key="rta.doc.tire31_application.label",
        description_key="rta.doc.tire31_application.description",
        tags=("C02_RTA_TITLE", "C20_STAMP_REGISTRATION"),
        order=5,
        sources=(
            SourceCitation(
                SRC_TIRE_31_SCAN.id,
                locator="uploaded Sinhala Ti.Re.31 scan",
                note="Not Gazette Form 31; translation and current revision unvalidated.",
            ),
            _ops("Transactions page, title certificate application"),
        ),
    ),
    # ── Identity (item 4) ────────────────────────────────────────────────────
    DocumentClassDefinition(
        id="rta.doc.nic",
        label_key="rta.doc.nic.label",
        description_key="rta.doc.nic.description",
        tags=("C01_IDENTITY_CAPACITY",),
        extraction_template_kind="identity-card",
        order=6,
        sources=(_act("44"), _ops("Transactions page, certified party identification")),
    ),
    DocumentClassDefinition(
        id="rta.doc.passport",
        label_key="rta.doc.passport.label",
        description_key="rta.doc.passport.description",
        tags=("C01_IDENTITY_CAPACITY",),
        order=7,
        sources=(_act("44"), _practice("examination of title — party identification")),
    ),
    # A driving licence corroborates identity in practice; whether the registry
    # accepts it in the submission pack is not established by the OPS sources,
    # so it is cited to practice only.
    DocumentClassDefinition(
        id="rta.doc.driving_licence",
        label_key="rta.doc.driving_licence.label",
        description_key="rta.doc.driving_licence.description",
        tags=("C01_IDENTITY_CAPACITY",),
        order=8,
        sources=(_practice("examination of title — party identification"),),
    ),
    # ── Survey and cadastral identity (item 5) ───────────────────────────────
    DocumentClassDefinition(
        id="rta.doc.survey_plan",
        label_key="rta.doc.survey_plan.label",
        description_key="rta.doc.survey_plan.description",
        tags=("C04_SURVEY_CADASTRAL",),
        extraction_template_kind="survey-plan",
        order=9,
        sources=(_act("4"), _act("44"), _practice("approved/current plan as relevant")),
    ),
    DocumentClassDefinition(
        id="rta.doc.cadastral_map_extract",
        label_key="rta.doc.cadastral_map_extract.label",
        description_key="rta.doc.cadastral_map_extract.description",
        tags=("C04_SURVEY_CADASTRAL", "C02_RTA_TITLE"),
        order=10,
        sources=(_act("4-5"), _act("75"), _ops("Transactions page, parcel identification")),
    ),
    # ── Mortgage (items 6-7) ─────────────────────────────────────────────────
    DocumentClassDefinition(
        id="rta.doc.registered_mortgage_instrument",
        label_key="rta.doc.registered_mortgage_instrument.label",
        description_key="rta.doc.registered_mortgage_instrument.description",
        tags=("C06_ENCUMBRANCES", "C07_MORTGAGE_RELEASE"),
        order=11,
        sources=(_gz("11"), _act("44")),
    ),
    DocumentClassDefinition(
        id="rta.doc.mortgage_discharge_evidence",
        label_key="rta.doc.mortgage_discharge_evidence.label",
        description_key="rta.doc.mortgage_discharge_evidence.description",
        tags=("C07_MORTGAGE_RELEASE", "C18_CANCELLATION_RELEASE"),
        order=12,
        sources=(_gz("12"), _practice("mortgage discharge and release evidence")),
    ),
    # ── Stamp duty and fees (item 8) ─────────────────────────────────────────
    DocumentClassDefinition(
        id="rta.doc.stamp_duty_receipt",
        label_key="rta.doc.stamp_duty_receipt.label",
        description_key="rta.doc.stamp_duty_receipt.description",
        tags=("C20_STAMP_REGISTRATION",),
        order=13,
        sources=(_ops("Transactions page, stamp duty receipt"), _act("40-42")),
    ),
    DocumentClassDefinition(
        id="rta.doc.registration_fee_receipt",
        label_key="rta.doc.registration_fee_receipt.label",
        description_key="rta.doc.registration_fee_receipt.description",
        tags=("C20_STAMP_REGISTRATION",),
        order=14,
        sources=(_charges("Charges page, registration fee"),),
    ),
    # ── Registry search (item 9) ─────────────────────────────────────────────
    DocumentClassDefinition(
        id="rta.doc.registry_search_request",
        label_key="rta.doc.registry_search_request.label",
        description_key="rta.doc.registry_search_request.description",
        tags=("C03_REGISTRY_SEARCH",),
        order=15,
        sources=(_act("34-35"), _ops("Transactions page, inspection request")),
    ),
    # A search result dates the search; it never proves that no later entry
    # exists, and no absence conclusion may be drawn from it alone (§5.3, §7.2).
    DocumentClassDefinition(
        id="rta.doc.registry_search_result",
        label_key="rta.doc.registry_search_result.label",
        description_key="rta.doc.registry_search_result.description",
        tags=("C03_REGISTRY_SEARCH", "C06_ENCUMBRANCES", "C02_RTA_TITLE"),
        may_satisfy_multiple_requirements=True,
        order=16,
        sources=(_act("34-35"), _practice("current search before completion")),
    ),
    DocumentClassDefinition(
        id="rta.doc.registered_instrument_copy",
        label_key="rta.doc.registered_instrument_copy.label",
        description_key="rta.doc.registered_instrument_copy.description",
        tags=("C03_REGISTRY_SEARCH", "C05_TITLE_HISTORY", "C06_ENCUMBRANCES"),
        order=17,
        sources=(_act("34"), _practice("relevant registered instrument copies")),
    ),
    # ── Red-flag classes (item 10) ───────────────────────────────────────────
    # Presence raises an issue for triage. It is not a finding that the
    # interest is valid, subsisting, or binding — that is a lawyer conclusion.
    DocumentClassDefinition(
        id="rta.doc.sale_agreement",
        label_key="rta.doc.sale_agreement.label",
        description_key="rta.doc.sale_agreement.description",
        tags=("C06_ENCUMBRANCES",),
        red_flag=True,
        order=18,
        sources=(_gz("23"), _act("44")),
    ),
    DocumentClassDefinition(
        id="rta.doc.lease",
        label_key="rta.doc.lease.label",
        description_key="rta.doc.lease.description",
        tags=("C06_ENCUMBRANCES", "C08_LEASE_OCCUPATION"),
        red_flag=True,
        order=19,
        sources=(_gz("10"), _act("44")),
    ),
    DocumentClassDefinition(
        id="rta.doc.caveat",
        label_key="rta.doc.caveat.label",
        description_key="rta.doc.caveat.description",
        tags=("C06_ENCUMBRANCES", "C17_CAVEAT_LITIGATION"),
        red_flag=True,
        order=20,
        sources=(_gz("13"), _act("44")),
    ),
    DocumentClassDefinition(
        id="rta.doc.seizure_notice",
        label_key="rta.doc.seizure_notice.label",
        description_key="rta.doc.seizure_notice.description",
        tags=("C06_ENCUMBRANCES", "C17_CAVEAT_LITIGATION"),
        red_flag=True,
        order=21,
        sources=(_act("44"), _practice("encumbrances, seizures, and injunctions")),
    ),
    DocumentClassDefinition(
        id="rta.doc.priority_notice",
        label_key="rta.doc.priority_notice.label",
        description_key="rta.doc.priority_notice.description",
        tags=("C06_ENCUMBRANCES", "C03_REGISTRY_SEARCH"),
        red_flag=True,
        order=22,
        sources=(_ops("Transactions page, expedited service list — priority notice"),),
    ),
    DocumentClassDefinition(
        id="rta.doc.court_notice",
        label_key="rta.doc.court_notice.label",
        description_key="rta.doc.court_notice.description",
        tags=("C17_CAVEAT_LITIGATION", "C19_COURT_STATUTORY_SALE"),
        red_flag=True,
        exclusion_indicator=True,
        order=23,
        sources=(
            _act("21-25"),
            _act("29-30"),
            _product("§14.6 stop condition — court referral, appeal, or lis pendens"),
        ),
    ),
    # ── Local-authority and building records (item 11) ───────────────────────
    # Contextual evidence about rates, lines, and construction. Never title
    # (§1.2, §Executive 9). Every rule here is authority-scoped, so a council's
    # practice must not activate globally (§13.2.8).
    DocumentClassDefinition(
        id=COMBINED_CERTIFICATE_CLASS_ID,
        label_key="rta.doc.combined_local_authority_certificate.label",
        description_key="rta.doc.combined_local_authority_certificate.description",
        tags=("C11_LOCAL_AUTHORITY", "C12_BUILDING_COMPLIANCE"),
        may_satisfy_multiple_requirements=True,
        order=24,
        sources=(
            _local("combined certificate issued by the relevant authority"),
            _product("§6.3 — one document may link to several checklist items"),
        ),
    ),
    DocumentClassDefinition(
        id="rta.doc.street_line_certificate",
        label_key="rta.doc.street_line_certificate.label",
        description_key="rta.doc.street_line_certificate.description",
        tags=("C11_LOCAL_AUTHORITY",),
        order=25,
        sources=(_local("street line enquiry"),),
    ),
    # Street line and building line stay separate classes: the source deck
    # conflates them and only a combined issued certificate merges them (§1.2).
    DocumentClassDefinition(
        id="rta.doc.building_line_certificate",
        label_key="rta.doc.building_line_certificate.label",
        description_key="rta.doc.building_line_certificate.description",
        tags=("C11_LOCAL_AUTHORITY",),
        order=26,
        sources=(_local("building line enquiry"),),
    ),
    DocumentClassDefinition(
        id="rta.doc.non_vesting_certificate",
        label_key="rta.doc.non_vesting_certificate.label",
        description_key="rta.doc.non_vesting_certificate.description",
        tags=("C11_LOCAL_AUTHORITY",),
        order=27,
        sources=(_local("non-vesting enquiry"),),
    ),
    # The council "ownership certificate" records assessment information. It is
    # not proof of legal title under the RTA (§1.2, §Executive 9).
    DocumentClassDefinition(
        id="rta.doc.assessment_certificate",
        label_key="rta.doc.assessment_certificate.label",
        description_key="rta.doc.assessment_certificate.description",
        tags=("C11_LOCAL_AUTHORITY",),
        order=28,
        sources=(
            _local("assessment register / 'ownership' certificate"),
            _act("32-33"),
        ),
    ),
    DocumentClassDefinition(
        id="rta.doc.rates_receipt",
        label_key="rta.doc.rates_receipt.label",
        description_key="rta.doc.rates_receipt.description",
        tags=("C11_LOCAL_AUTHORITY",),
        order=29,
        sources=(_local("rates and taxes receipt"),),
    ),
    DocumentClassDefinition(
        id="rta.doc.approved_building_plan",
        label_key="rta.doc.approved_building_plan.label",
        description_key="rta.doc.approved_building_plan.description",
        tags=("C12_BUILDING_COMPLIANCE",),
        order=30,
        sources=(_uda("building plan approval process"), _local("approved building plan")),
    ),
    DocumentClassDefinition(
        id="rta.doc.certificate_of_conformity",
        label_key="rta.doc.certificate_of_conformity.label",
        description_key="rta.doc.certificate_of_conformity.description",
        tags=("C12_BUILDING_COMPLIANCE",),
        order=31,
        sources=(_uda("certificate of conformity"), _local("certificate of conformity")),
    ),
    # ── Exclusion/classification classes (item 12) ───────────────────────────
    # V0 classifies these so the matter can be explained and routed out; it
    # does not automate the path they belong to (§14.7).
    DocumentClassDefinition(
        id="rta.doc.death_certificate",
        label_key="rta.doc.death_certificate.label",
        description_key="rta.doc.death_certificate.description",
        tags=("C09_PROBATE_TRANSMISSION",),
        exclusion_indicator=True,
        order=32,
        sources=(_act("54-55"), _product("§14.6 stop condition — deceased owner")),
    ),
    DocumentClassDefinition(
        id="rta.doc.will",
        label_key="rta.doc.will.label",
        description_key="rta.doc.will.description",
        tags=("C09_PROBATE_TRANSMISSION",),
        exclusion_indicator=True,
        order=33,
        sources=(_act("54"), _practice("probate suite")),
    ),
    DocumentClassDefinition(
        id="rta.doc.probate_letters_of_administration",
        label_key="rta.doc.probate_letters_of_administration.label",
        description_key="rta.doc.probate_letters_of_administration.description",
        tags=("C09_PROBATE_TRANSMISSION",),
        exclusion_indicator=True,
        order=34,
        sources=(_act("54-55"), _practice("probate suite")),
    ),
    # Company-law sufficiency is outside the supplied RTA sources; these two
    # classes record authority indicators only (§5.3).
    DocumentClassDefinition(
        id="rta.doc.company_incorporation_record",
        label_key="rta.doc.company_incorporation_record.label",
        description_key="rta.doc.company_incorporation_record.description",
        tags=("C10_COMPANY_AUTHORITY",),
        exclusion_indicator=True,
        order=35,
        sources=(
            _practice("company authority checklist"),
            _product("§14.6 stop condition — unresolved company party"),
        ),
    ),
    DocumentClassDefinition(
        id="rta.doc.company_resolution",
        label_key="rta.doc.company_resolution.label",
        description_key="rta.doc.company_resolution.description",
        tags=("C10_COMPANY_AUTHORITY",),
        exclusion_indicator=True,
        order=36,
        sources=(
            _practice("board/company resolution and signing authority"),
            _product("§14.6 stop condition — unresolved company party"),
        ),
    ),
    DocumentClassDefinition(
        id="rta.doc.power_of_attorney",
        label_key="rta.doc.power_of_attorney.label",
        description_key="rta.doc.power_of_attorney.description",
        tags=("C21_POWER_OF_ATTORNEY", "C01_IDENTITY_CAPACITY"),
        exclusion_indicator=True,
        order=37,
        sources=(
            _ops("Transactions page, power of attorney"),
            _act("44"),
            _product("§14.6 stop condition — unresolved POA"),
        ),
    ),
    DocumentClassDefinition(
        id="rta.doc.life_interest_instrument",
        label_key="rta.doc.life_interest_instrument.label",
        description_key="rta.doc.life_interest_instrument.description",
        tags=("C15_LIFE_INTEREST", "C06_ENCUMBRANCES"),
        exclusion_indicator=True,
        order=38,
        sources=(_act("46"), _gz("9"), _gz("28")),
    ),
    DocumentClassDefinition(
        id="rta.doc.subdivision_plan",
        label_key="rta.doc.subdivision_plan.label",
        description_key="rta.doc.subdivision_plan.description",
        tags=("C13_SUBDIVISION_AMALGAMATION", "C04_SURVEY_CADASTRAL"),
        exclusion_indicator=True,
        order=39,
        sources=(_act("36"), _act("47"), _gz("7")),
    ),
    DocumentClassDefinition(
        id="rta.doc.condominium_declaration",
        label_key="rta.doc.condominium_declaration.label",
        description_key="rta.doc.condominium_declaration.description",
        tags=("C14_CONDOMINIUM_STRATA", "C04_SURVEY_CADASTRAL"),
        exclusion_indicator=True,
        order=40,
        sources=(_act("50-52"), _gz("21")),
    ),
    # ── Supported non-answer (item 13) ───────────────────────────────────────
    DocumentClassDefinition(
        id=UNIDENTIFIED_DOCUMENT_CLASS_ID,
        label_key="rta.doc.unidentified.label",
        description_key="rta.doc.unidentified.description",
        order=41,
        sources=(_product("§6.3 — keep in the inbox, never permanently labelled 'other'"),),
    ),
    # ── Classes the checklist modules require (C05, C11-C19) ─────────────────
    #
    # These complete the catalogue for the conditional and cancellation
    # modules. They exist as real classes rather than as ``other`` because a
    # requirement that names an accepted class it cannot resolve is a rule the
    # inbox can never satisfy.
    DocumentClassDefinition(
        id="rta.doc.prescribed_instrument",
        label_key="rta.doc.prescribed_instrument.label",
        description_key="rta.doc.prescribed_instrument.description",
        tags=("C18_CANCELLATION_RELEASE", "C20_STAMP_REGISTRATION"),
        order=42,
        sources=(_gz("any prescribed instrument"), _act("43")),
    ),
    DocumentClassDefinition(
        id="rta.doc.prior_deed",
        label_key="rta.doc.prior_deed.label",
        description_key="rta.doc.prior_deed.description",
        tags=("C05_TITLE_HISTORY",),
        order=43,
        sources=(
            _practice("chain of title"),
            _product("§5.3 — deed history explains a legacy entry; it is not a substitute"),
        ),
    ),
    DocumentClassDefinition(
        id="rta.doc.estate_inventory",
        label_key="rta.doc.estate_inventory.label",
        description_key="rta.doc.estate_inventory.description",
        tags=("C09_PROBATE_TRANSMISSION",),
        exclusion_indicator=True,
        order=44,
        sources=(_act("54"), _act("55"), _practice("probate suite")),
    ),
    DocumentClassDefinition(
        id="rta.doc.assessment_notice",
        label_key="rta.doc.assessment_notice.label",
        description_key="rta.doc.assessment_notice.description",
        tags=("C11_LOCAL_AUTHORITY",),
        order=45,
        # §1.2: a land-rates assessment notice is not an income-tax notice, and
        # the deck's description of it as one must not be implemented.
        sources=(_local("assessment notice"),),
    ),
    DocumentClassDefinition(
        id="rta.doc.development_permit",
        label_key="rta.doc.development_permit.label",
        description_key="rta.doc.development_permit.description",
        tags=("C12_BUILDING_COMPLIANCE",),
        order=46,
        sources=(_uda("development permit"),),
    ),
    DocumentClassDefinition(
        id="rta.doc.survey_department_certification",
        label_key="rta.doc.survey_department_certification.label",
        description_key="rta.doc.survey_department_certification.description",
        tags=("C13_SUBDIVISION_AMALGAMATION", "C04_SURVEY_CADASTRAL"),
        exclusion_indicator=True,
        order=47,
        sources=(_act("36"), _ops("Transactions page, subdivision")),
    ),
    DocumentClassDefinition(
        id="rta.doc.condominium_plan",
        label_key="rta.doc.condominium_plan.label",
        description_key="rta.doc.condominium_plan.description",
        tags=("C14_CONDOMINIUM_STRATA",),
        exclusion_indicator=True,
        order=48,
        sources=(_act("50-52"), _gz("21")),
    ),
    DocumentClassDefinition(
        id="rta.doc.servitude_instrument",
        label_key="rta.doc.servitude_instrument.label",
        description_key="rta.doc.servitude_instrument.description",
        tags=("C16_SERVITUDE_ACCESS", "C06_ENCUMBRANCES"),
        order=49,
        sources=(_act("75"), _gz("35")),
    ),
    DocumentClassDefinition(
        id="rta.doc.consent_letter",
        label_key="rta.doc.consent_letter.label",
        description_key="rta.doc.consent_letter.description",
        tags=("C15_LIFE_INTEREST", "C18_CANCELLATION_RELEASE"),
        order=50,
        sources=(_practice("consent of an affected interest holder"),),
    ),
    DocumentClassDefinition(
        id="rta.doc.court_order",
        label_key="rta.doc.court_order.label",
        description_key="rta.doc.court_order.description",
        tags=("C17_CAVEAT_LITIGATION", "C18_CANCELLATION_RELEASE", "C19_COURT_STATUTORY_SALE"),
        red_flag=True,
        exclusion_indicator=True,
        order=51,
        # Distinct from ``rta.doc.court_notice``: an order or decree determines
        # something, a notice announces a proceeding. Collapsing them would let
        # a pending case read as a concluded one (§8.4).
        sources=(_act("21-25"), _act("56")),
    ),
    DocumentClassDefinition(
        id="rta.doc.certificate_of_sale",
        label_key="rta.doc.certificate_of_sale.label",
        description_key="rta.doc.certificate_of_sale.description",
        tags=("C19_COURT_STATUTORY_SALE",),
        exclusion_indicator=True,
        order=52,
        sources=(_act("56"), _gz("25"), _gz("34")),
    ),
)


# ── Confidence and automation policy (§6.4) ──────────────────────────────────


@dataclass(frozen=True)
class ConfidencePolicy:
    """The §6.4 thresholds as one governed object.

    Scattering these numbers through the pipeline is how a threshold quietly
    drifts. They are calibrated per class, language, and field, so the values
    below are the product floor a calibration may tighten but never relax.
    """

    boundary_auto_threshold: float
    boundary_review_floor: float
    class_auto_threshold: float
    class_top_two_margin: float
    class_review_floor: float
    noncritical_fact_auto_threshold: float
    noncritical_fact_review_floor: float


CONFIDENCE_POLICY = ConfidencePolicy(
    boundary_auto_threshold=0.97,
    boundary_review_floor=0.80,
    class_auto_threshold=0.95,
    class_top_two_margin=0.15,
    class_review_floor=0.80,
    noncritical_fact_auto_threshold=0.95,
    noncritical_fact_review_floor=0.80,
)


# ── Lookups ──────────────────────────────────────────────────────────────────

_BY_ID: dict[str, DocumentClassDefinition] = {c.id: c for c in DOCUMENT_CLASSES}


def get_document_class(class_id: str) -> DocumentClassDefinition | None:
    return _BY_ID.get(class_id)


def require_document_class(class_id: str) -> DocumentClassDefinition:
    """Raises ``KeyError`` rather than falling back to ``UNIDENTIFIED``.

    An unknown id is a programming error; silently coercing it would hide a
    stale ``DOCUMENT_CLASSES_VERSION`` behind a plausible-looking inbox entry.
    """
    document_class = _BY_ID.get(class_id)
    if document_class is None:
        raise KeyError(f"Unknown RTA document class '{class_id}'.")
    return document_class


def red_flag_class_ids() -> tuple[str, ...]:
    return tuple(c.id for c in DOCUMENT_CLASSES if c.red_flag)


def exclusion_indicator_class_ids() -> tuple[str, ...]:
    return tuple(c.id for c in DOCUMENT_CLASSES if c.exclusion_indicator)


def document_classes_for_tag(tag: str) -> tuple[DocumentClassDefinition, ...]:
    """Classes relevant to one checklist module, for inbox filtering only.

    This is a hint, not a satisfaction rule: whether a document satisfies a
    requirement is decided by the checklist and confirmed by a lawyer (§6.3).
    """
    return tuple(c for c in DOCUMENT_CLASSES if tag in c.tags)


def may_auto_organize_class(confidence: float, top_two_margin: float) -> bool:
    """§6.4 — auto-file as ``AI_ORGANIZED``, which is never lawyer-confirmed.

    The margin matters as much as the score: a 0.96 top score against a 0.95
    runner-up is an undecided classification, not a confident one.
    """
    return (
        confidence >= CONFIDENCE_POLICY.class_auto_threshold
        and top_two_margin >= CONFIDENCE_POLICY.class_top_two_margin
    )


def may_auto_split_boundary(confidence: float, continuity_anomaly: bool) -> bool:
    """§6.4 — a provisional split only; a page-numbering or continuity anomaly
    means missing pages until a human says otherwise (§6.3)."""
    return not continuity_anomaly and confidence >= CONFIDENCE_POLICY.boundary_auto_threshold


def may_prefill_noncritical(confidence: float, conflicting: bool, clean_ocr: bool) -> bool:
    """§6.4 — show a noncritical fact as a candidate and permit checklist
    matching. A conflicting value goes to review however high the score."""
    return (
        clean_ocr
        and not conflicting
        and confidence >= CONFIDENCE_POLICY.noncritical_fact_auto_threshold
    )


def may_auto_confirm_critical_fact(confidence: float) -> bool:
    """Always ``False``, at any confidence including 1.00.

    §6.4: a critical legal or form fact has no confidence bypass and always
    requires lawyer confirmation. The parameter is accepted so a caller can
    hand over its score and still be told no — the rule is enforced here rather
    than relied on being remembered at each call site.
    """
    return False
