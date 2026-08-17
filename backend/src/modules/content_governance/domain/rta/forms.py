"""Prescribed-form template registry and fact-to-field mappings.

Two rules govern this file.

1. **A form number is never a primary key** (§9.1, §Executive 11).
   ``rta.reg.2022.form.31`` is the Gazette instrument for registering an
   *address*; ``rta.ops.tire.31`` is the RGD operational application for a *new
   Title Certificate*. Same number, different namespace, different record. The
   same protection applies to Gazette Form 30 (cancel a caveat) versus
   operational Ti.Re.30 (searches and copies).
2. **Nothing here is an approved production rendering** (§9.5). Every template
   is ``DRAFT_TRANSCRIPTION``, carries no lawyer approval, and has no layout,
   so ``registration_ready_capable`` is False for all of them. The Gazette's
   legal prose is deliberately not copied into this repository: what is
   modelled is field structure, fact binding, and the recorded defects of the
   source text. Labels are translation keys, never English form copy.

Known typographical defects of the 2022 English form set are recorded as
translation keys that *name* the defect (§1.2). Draftly never silently repairs
a legal template, and never renders a corrected reading of one.

Only three mappings are populated: Gazette Form 8 (the V0 transfer pilot),
Gazette Form 12 (the V0 mortgage-cancellation pilot), and operational Ti.Re.31.
Every other template is registered so that routing, namespacing, and staleness
work, with an empty field schema until the official artifact is anchored.

Implements §9.1, §9.3, §9.4, §9.5, §1.2, and the §12.2 ``FormTemplate`` /
``FormFieldMapping`` contracts.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from src.modules.content_governance.domain.enums import TemplateNamespace, TemplateStatus
from src.modules.content_governance.domain.sources import (
    SRC_GAZETTE_2022,
    SRC_RGD_CHARGES,
    SRC_RGD_TRANSACTIONS,
    SRC_RTA_ACT,
    SRC_TIRE_31_SCAN,
    SourceCitation,
)

#: Bumped when a template is added, retired, or its field schema changes.
#: Pinned into every generated form so a template change never rewrites an
#: existing draft in place (§9.5: no auto-update of live matters).
FORMS_VERSION = "1.0.0"

#: Per-template version. Stays below 1.0.0 until a lawyer-approved rendering
#: with a documented variance exists; a transcription is not a template (§9.5).
_DRAFT_VERSION = "0.1.0"


# ── Transformations and validation rules (§9.3) ──────────────────────────────
#
# A populated field stores the transformation that produced it. Anything not
# listed on the mapping is not an allowed transformation for that field, which
# is what stops a "helpful" normalisation of a name or an extent.

TRANSFORM_EXACT_COPY = "EXACT_COPY"
TRANSFORM_TRANSLITERATION = "TRANSLITERATION"
TRANSFORM_UNIT_CONVERSION = "UNIT_CONVERSION"
TRANSFORM_FORMAT_DATE = "FORMAT_DATE"
TRANSFORM_NUMBER_TO_WORDS = "NUMBER_TO_WORDS"

ALLOWED_TRANSFORMATION_IDS: frozenset[str] = frozenset(
    {
        TRANSFORM_EXACT_COPY,
        TRANSFORM_TRANSLITERATION,
        TRANSFORM_UNIT_CONVERSION,
        TRANSFORM_FORMAT_DATE,
        TRANSFORM_NUMBER_TO_WORDS,
    }
)

# The first four mirror the deterministic validators already implemented in
# `modules/document/domain/registry.py`; they are referenced by id because a
# governed-content module does not import another module's extraction code.
VALIDATION_NIC_FORMAT = "VAL_NIC_FORMAT"
VALIDATION_ISO_DATE = "VAL_ISO_DATE"
VALIDATION_EXTENT_HECTARES = "VAL_EXTENT_HECTARES"
VALIDATION_DIGITS = "VAL_DIGITS"
VALIDATION_MONEY_AMOUNT = "VAL_MONEY_AMOUNT"
VALIDATION_CLASS_OF_TITLE = "VAL_CLASS_OF_TITLE"
VALIDATION_CONSIDERATION_WORDS_MATCH = "VAL_CONSIDERATION_WORDS_MATCH_FIGURES"
VALIDATION_EXTENT_NOT_GREATER_THAN_PARCEL = "VAL_EXTENT_NOT_GREATER_THAN_PARCEL"


# ── Recorded source defects (§1.2, §9.5) ─────────────────────────────────────
#
# Keys name a defect; they never carry a corrected rendering. §1.2 reports the
# defects against the 2022 English form set without identifying which form
# carries which, so the whole set is flagged rather than one form guessed at.

DEFECT_CAPTION_OR_REQUEST_MISMATCH = "rta.form.defect.caption_or_request_sentence_mismatch"
DEFECT_DECEASED_RENDERED_DISEASED = "rta.form.defect.deceased_rendered_diseased"
DEFECT_ENGLISH_TEXT_NOT_VALIDATED = "rta.form.defect.english_text_not_lawyer_validated"
DEFECT_SINHALA_TAMIL_TEXT_NOT_HELD = "rta.form.defect.sinhala_tamil_text_not_held"
DEFECT_TRANSLATION_UNVERIFIED = "rta.form.defect.translation_unverified"
DEFECT_REVISION_UNVERIFIED = "rta.form.defect.current_revision_unverified"
DEFECT_OFFICIAL_ARTIFACT_NOT_HELD = "rta.form.defect.official_artifact_not_held"
DEFECT_SCAN_CONTAINS_PRIVATE_DATA = "rta.form.defect.scan_contains_private_sample_data"

GAZETTE_2022_KNOWN_DEFECT_KEYS: tuple[str, ...] = (
    DEFECT_CAPTION_OR_REQUEST_MISMATCH,
    DEFECT_DECEASED_RENDERED_DISEASED,
    DEFECT_ENGLISH_TEXT_NOT_VALIDATED,
    DEFECT_SINHALA_TAMIL_TEXT_NOT_HELD,
)


# ── Definitions ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FormFieldMapping:
    """One form field and the canonical fact it may be populated from (§9.3).

    ``fact_type_id`` is ``None`` where the form needs a particular that has no
    canonical fact type yet; such a field can only ever be lawyer-entered.
    """

    field_id: str
    label_key: str
    fact_type_id: str | None
    required: bool
    #: §6.4 — a critical fact needs an explicit lawyer decision at any model
    #: confidence, so this also gates approval, not merely the UI badge.
    critical: bool
    human_confirmation_required: bool
    order: int
    allowed_transformation_ids: tuple[str, ...] = ()
    validation_rule_ids: tuple[str, ...] = ()
    section_key: str | None = None
    #: True for a field the lawyer may author free text into (§9.4). The
    #: addition is versioned and sourced as lawyer-authored.
    lawyer_authored_allowed: bool = False


@dataclass(frozen=True)
class FormTemplateDefinition:
    """One namespaced form record (§9.1, §9.5, §12.2 ``FormTemplate``)."""

    id: str
    version: str
    namespace: TemplateNamespace
    form_number: str
    title_key: str
    subtype_ids: tuple[str, ...]
    languages: tuple[str, ...]
    status: TemplateStatus
    sources: tuple[SourceCitation, ...]
    official_artifact_source_record_id: str | None = None
    page_range: str | None = None
    field_mappings: tuple[FormFieldMapping, ...] = ()
    approved_by_lawyer_id: str | None = None
    approved_at: str | None = None
    #: False until the official page image/PDF and an approved production
    #: rendering exist in the repository (§9.5). No layout is fabricated.
    production_layout_available: bool = False
    known_source_defect_keys: tuple[str, ...] = ()
    supersedes_template_id: str | None = None

    @property
    def registration_ready_capable(self) -> bool:
        """Whether this template could ever back a registration-ready export.

        False for everything in this repository today, and that is the honest
        answer: a transcription without a named lawyer approval and without an
        approved rendering cannot produce a submittable instrument (§9.4, §9.5).
        """
        return (
            self.status is TemplateStatus.VALIDATED
            and self.approved_by_lawyer_id is not None
            and self.production_layout_available
        )


# ── Builders ─────────────────────────────────────────────────────────────────


def _slug(template_id: str) -> str:
    """Translation-key segment for a template id (dots separate key levels)."""
    return template_id.removeprefix("rta.").replace(".", "_")


def _gz(form_number: str) -> SourceCitation:
    """Citation for one of the 22 instruments listed in the regulation 15(1) amendment."""
    return SourceCitation(
        SRC_GAZETTE_2022.id,
        locator=f"regulation 15(1) amendment; Form {form_number}",
    )


def _gz_related(form_number: str) -> SourceCitation:
    """Citation for a 2022-amendment form that is *not* a regulation 15(1) item.

    Forms 4, 14, 19, 37, 38, and 39 sit in the same Gazette but outside the
    items (i)-(xxii) list that ``sources.py`` records as the 15(1) scope. Citing
    them at "regulation 15(1)" would put a locator on the record that the source
    does not support, which §13.1 does not allow and §9.5 would then carry into
    every template-approval screen.
    """
    return SourceCitation(
        SRC_GAZETTE_2022.id,
        locator=f"2022 amendment, outside regulation 15(1) items (i)-(xxii); Form {form_number}",
    )


def _act(section: str) -> SourceCitation:
    # "ss." for a range, "s." for a single section — the citation convention the
    # sibling rule modules already use.
    prefix = "ss." if "-" in section else "s."
    return SourceCitation(SRC_RTA_ACT.id, locator=f"{prefix} {section}")


#: §5.5 `RP-DUP`. Cited as an operational rule with a re-verification note, not
#: reproduced as instruction text, and never treated as permanent (§13.4).
_RP_DUP = SourceCitation(
    SRC_RGD_TRANSACTIONS.id,
    locator="submission pack RP-DUP",
    note=(
        "RGD currently states a duplicate-instrument and photograph requirement "
        "for sale/transfer, gift, and exchange. Content confidence is high, "
        "currency requires re-verification before it gates a submission."
    ),
)


def _field(
    slug: str,
    field_id: str,
    fact_type_id: str | None,
    order: int,
    *,
    section: str,
    critical: bool,
    required: bool = True,
    human_confirmation: bool | None = None,
    transformations: tuple[str, ...] = (TRANSFORM_EXACT_COPY,),
    validations: tuple[str, ...] = (),
    lawyer_authored_allowed: bool = False,
) -> FormFieldMapping:
    return FormFieldMapping(
        field_id=field_id,
        label_key=f"rta.form.{slug}.field.{field_id}.label",
        fact_type_id=fact_type_id,
        required=required,
        critical=critical,
        # A critical fact always needs the human decision; a field may also
        # demand one for a non-critical reason (an attestation particular).
        human_confirmation_required=critical if human_confirmation is None else human_confirmation,
        order=order,
        allowed_transformation_ids=transformations,
        validation_rule_ids=validations,
        section_key=f"rta.form.{slug}.section.{section}",
        lawyer_authored_allowed=lawyer_authored_allowed,
    )


def _gazette_2022_form(
    suffix: str,
    form_number: str,
    subtype_ids: tuple[str, ...],
    extra_sources: tuple[SourceCitation, ...] = (),
    *,
    namespace: TemplateNamespace = TemplateNamespace.REGULATION,
    field_mappings: tuple[FormFieldMapping, ...] = (),
    regulation_15_1: bool = True,
) -> FormTemplateDefinition:
    """A record for one form of the 2022 amendment.

    ``suffix`` is the id segment (``"08"``, ``"14.first_class"``) and
    ``form_number`` the printed number; they differ because the id is zero
    padded for stable sorting and a form may have class variants.

    ``regulation_15_1`` is False for the related forms of the same Gazette that
    are not one of the 22 prescribed instruments, so their citation does not
    claim a regulation 15(1) item number they do not have.
    """
    template_id = f"rta.reg.2022.form.{suffix}"
    gazette = _gz(form_number) if regulation_15_1 else _gz_related(form_number)
    return FormTemplateDefinition(
        id=template_id,
        version=_DRAFT_VERSION,
        namespace=namespace,
        form_number=form_number,
        title_key=f"rta.form.{_slug(template_id)}.title",
        subtype_ids=subtype_ids,
        # Only the English text of the amendment has been read. Claiming si/ta
        # here would assert a validated trilingual template that we do not hold.
        languages=("en",),
        status=TemplateStatus.DRAFT_TRANSCRIPTION,
        sources=(gazette, *extra_sources),
        official_artifact_source_record_id=SRC_GAZETTE_2022.id,
        page_range=None,
        field_mappings=field_mappings,
        known_source_defect_keys=GAZETTE_2022_KNOWN_DEFECT_KEYS,
    )


# ── Gazette Form 8 field mapping (§9.3) ──────────────────────────────────────
#
# Item structure and field ids follow the already-extracted `FORM8_INSTRUMENT`
# template in `modules/document/domain/registry.py`, so what is extracted, what
# gates drafting, and what renders stay one vocabulary. Field ids are
# snake_case; the camelCase extraction keys live on the fact types.

_F08 = "reg_2022_form_08"

_FORM_08_FIELDS: tuple[FormFieldMapping, ...] = (
    # Item 1 — land-parcel particulars. The cadastral parcel is the unit of
    # record (RTA ss. 4-5), so these identifiers are critical, not descriptive.
    _field(_F08, "district", "rta.parcel.district", 1, section="parcel", critical=True),
    _field(_F08, "ds_division", "rta.parcel.ds_division", 2, section="parcel", critical=True),
    _field(_F08, "gn_division", "rta.parcel.gn_division", 3, section="parcel", critical=True),
    _field(
        _F08,
        "village",
        "rta.parcel.village",
        4,
        section="parcel",
        critical=False,
        required=False,
    ),
    _field(
        _F08,
        "assessment_number",
        "rta.parcel.assessment_number",
        5,
        section="parcel",
        critical=False,
        required=False,
    ),
    _field(
        _F08,
        "cadastral_map_no",
        "rta.parcel.cadastral_map_number",
        6,
        section="parcel",
        critical=True,
        validations=(VALIDATION_DIGITS,),
    ),
    _field(_F08, "block_no", "rta.parcel.block_number", 7, section="parcel", critical=True),
    _field(_F08, "sheet_no", "rta.parcel.sheet_number", 8, section="parcel", critical=True),
    _field(_F08, "parcel_no", "rta.parcel.parcel_number", 9, section="parcel", critical=True),
    _field(
        _F08,
        "extent",
        "rta.parcel.extent",
        10,
        section="parcel",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_UNIT_CONVERSION),
        validations=(VALIDATION_EXTENT_HECTARES,),
    ),
    # A transferred extent smaller than the parcel is a part disposition, which
    # RTA s. 47 blocks until subdivision — the comparison is a check, not a
    # rendering rule, so the mapping only names the validation.
    _field(
        _F08,
        "extent_subject_to_transfer",
        "rta.parcel.extent_subject_to_transaction",
        11,
        section="parcel",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_UNIT_CONVERSION),
        validations=(VALIDATION_EXTENT_HECTARES, VALIDATION_EXTENT_NOT_GREATER_THAN_PARCEL),
    ),
    # Item 2 — title particulars.
    _field(
        _F08,
        "place_of_registration",
        "rta.title.place_of_registration",
        12,
        section="title",
        critical=True,
    ),
    _field(
        _F08,
        "title_certificate_no",
        "rta.title.certificate_no",
        13,
        section="title",
        critical=True,
    ),
    _field(
        _F08,
        "class_of_title",
        "rta.title.class",
        14,
        section="title",
        critical=True,
        validations=(VALIDATION_CLASS_OF_TITLE,),
    ),
    # Item 3 — transferor. Transliteration is allowed but never automatic: a
    # name in a different script is a candidate for lawyer confirmation.
    _field(
        _F08,
        "transferor_name",
        "rta.party.transferor_name",
        15,
        section="transferor",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    _field(
        _F08,
        "transferor_nic",
        "rta.party.transferor_nic",
        16,
        section="transferor",
        critical=True,
        validations=(VALIDATION_NIC_FORMAT,),
    ),
    _field(
        _F08,
        "transferor_address",
        "rta.party.transferor_address",
        17,
        section="transferor",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    # Item 4 — transferee.
    _field(
        _F08,
        "transferee_name",
        "rta.party.transferee_name",
        18,
        section="transferee",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    _field(
        _F08,
        "transferee_nic",
        "rta.party.transferee_nic",
        19,
        section="transferee",
        critical=True,
        validations=(VALIDATION_NIC_FORMAT,),
    ),
    _field(
        _F08,
        "transferee_address",
        "rta.party.transferee_address",
        20,
        section="transferee",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    # Item 5 — consideration. The words are derivable from the figures, so the
    # derivation is declared and shown, never silently applied (§9.3).
    _field(
        _F08,
        "consideration",
        "rta.instrument.consideration",
        21,
        section="consideration",
        critical=True,
        validations=(VALIDATION_MONEY_AMOUNT,),
    ),
    _field(
        _F08,
        "consideration_words",
        "rta.instrument.consideration_words",
        22,
        section="consideration",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_NUMBER_TO_WORDS),
        validations=(VALIDATION_CONSIDERATION_WORDS_MATCH,),
    ),
    # Attestation block. §9.3 forbids pre-certifying the attestation act, so
    # the date is not required for a working draft; it is recorded from the
    # execution event and drives the s. 45(1) seven-working-day task.
    _field(
        _F08,
        "notary_name",
        "rta.instrument.notary_name",
        23,
        section="attestation",
        critical=False,
        human_confirmation=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    _field(
        _F08,
        "notary_code",
        "rta.instrument.notary_code",
        24,
        section="attestation",
        critical=False,
        human_confirmation=True,
    ),
    _field(
        _F08,
        "attestation_date",
        "rta.instrument.attestation_date",
        25,
        section="attestation",
        critical=True,
        required=False,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_FORMAT_DATE),
        validations=(VALIDATION_ISO_DATE,),
    ),
)


# ── Gazette Form 12 field mapping (§5.6, §9.3) ───────────────────────────────
#
# Unlike Form 8 there is no extracted artifact for Form 12 in this repository.
# These fields are the particulars §5.6 says a mortgage cancellation must
# identify — prior mortgage, releasing party and its authority, discharge
# basis — and every one must be re-anchored to the official page before the
# template can leave DRAFT_TRANSCRIPTION.

_F12 = "reg_2022_form_12"

_FORM_12_FIELDS: tuple[FormFieldMapping, ...] = (
    _field(_F12, "district", "rta.parcel.district", 1, section="parcel", critical=True),
    _field(_F12, "ds_division", "rta.parcel.ds_division", 2, section="parcel", critical=True),
    _field(_F12, "gn_division", "rta.parcel.gn_division", 3, section="parcel", critical=True),
    _field(
        _F12,
        "cadastral_map_no",
        "rta.parcel.cadastral_map_number",
        4,
        section="parcel",
        critical=True,
        validations=(VALIDATION_DIGITS,),
    ),
    _field(_F12, "block_no", "rta.parcel.block_number", 5, section="parcel", critical=True),
    _field(_F12, "sheet_no", "rta.parcel.sheet_number", 6, section="parcel", critical=True),
    _field(_F12, "parcel_no", "rta.parcel.parcel_number", 7, section="parcel", critical=True),
    _field(
        _F12,
        "extent",
        "rta.parcel.extent",
        8,
        section="parcel",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_UNIT_CONVERSION),
        validations=(VALIDATION_EXTENT_HECTARES,),
    ),
    _field(
        _F12,
        "place_of_registration",
        "rta.title.place_of_registration",
        9,
        section="title",
        critical=True,
    ),
    _field(
        _F12,
        "title_certificate_no",
        "rta.title.certificate_no",
        10,
        section="title",
        critical=True,
    ),
    _field(
        _F12,
        "class_of_title",
        "rta.title.class",
        11,
        section="title",
        critical=True,
        validations=(VALIDATION_CLASS_OF_TITLE,),
    ),
    _field(
        _F12,
        "registered_owner_name",
        "rta.title.registered_owner_name",
        12,
        section="title",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    # Cancelling "a" mortgage is not a legal act; cancelling the exact
    # registered entry is. The reference is required and lawyer-confirmed.
    _field(
        _F12,
        "mortgage_reference",
        "rta.interest.mortgage_reference",
        13,
        section="prior_mortgage",
        critical=True,
    ),
    # Gap: no canonical fact type records when the prior mortgage was
    # registered (facts.py has no rta.interest.mortgage_registration_date).
    _field(
        _F12,
        "mortgage_registration_date",
        None,
        14,
        section="prior_mortgage",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_FORMAT_DATE),
        validations=(VALIDATION_ISO_DATE,),
    ),
    _field(
        _F12,
        "mortgagee_name",
        "rta.interest.mortgagee_name",
        15,
        section="mortgagee",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    # Gap: party addresses exist in facts.py only for transferor/transferee.
    _field(
        _F12,
        "mortgagee_address",
        None,
        16,
        section="mortgagee",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    # Whether the signatory could release for an institutional mortgagee is a
    # legal conclusion; the field records the lawyer's confirmation of it.
    _field(
        _F12,
        "releasing_party_authority",
        "rta.interest.mortgagee_authority_confirmed",
        17,
        section="mortgagee",
        critical=True,
    ),
    _field(
        _F12,
        "discharge_evidence_kind",
        "rta.interest.discharge_evidence_kind",
        18,
        section="discharge",
        critical=True,
    ),
    # Gap: no fact type for the discharge instrument's own reference or date.
    _field(_F12, "discharge_reference", None, 19, section="discharge", critical=True),
    _field(
        _F12,
        "discharge_date",
        None,
        20,
        section="discharge",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_FORMAT_DATE),
        validations=(VALIDATION_ISO_DATE,),
    ),
    # The only §9.4 lawyer-authored slot on this template. Its existence and
    # position are unverified until the official artifact is anchored.
    _field(
        _F12,
        "cancellation_particulars",
        None,
        21,
        section="discharge",
        critical=False,
        required=False,
        human_confirmation=True,
        lawyer_authored_allowed=True,
    ),
    _field(
        _F12,
        "notary_name",
        "rta.instrument.notary_name",
        22,
        section="attestation",
        critical=False,
        human_confirmation=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    _field(
        _F12,
        "notary_code",
        "rta.instrument.notary_code",
        23,
        section="attestation",
        critical=False,
        human_confirmation=True,
    ),
    _field(
        _F12,
        "attestation_date",
        "rta.instrument.attestation_date",
        24,
        section="attestation",
        critical=True,
        required=False,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_FORMAT_DATE),
        validations=(VALIDATION_ISO_DATE,),
    ),
)


# ── Operational Ti.Re.31 field mapping (§1.2, §9.5) ──────────────────────────
#
# Derived from the uploaded Sinhala scan, whose translation, revision, and
# current acceptance are unverified. In the V0 transfer flow the applicant is
# the transferee, which is why the applicant fields bind to transferee facts;
# any other applicant is lawyer-entered, so every one stays human-confirmed.

_T31 = "ops_tire_31"

_TIRE_31_FIELDS: tuple[FormFieldMapping, ...] = (
    _field(
        _T31,
        "applicant_name",
        "rta.party.transferee_name",
        1,
        section="applicant",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    _field(
        _T31,
        "applicant_nic",
        "rta.party.transferee_nic",
        2,
        section="applicant",
        critical=True,
        validations=(VALIDATION_NIC_FORMAT,),
    ),
    _field(
        _T31,
        "applicant_address",
        "rta.party.transferee_address",
        3,
        section="applicant",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    _field(_T31, "district", "rta.parcel.district", 4, section="parcel", critical=True),
    _field(_T31, "ds_division", "rta.parcel.ds_division", 5, section="parcel", critical=True),
    _field(_T31, "gn_division", "rta.parcel.gn_division", 6, section="parcel", critical=True),
    _field(
        _T31,
        "cadastral_map_no",
        "rta.parcel.cadastral_map_number",
        7,
        section="parcel",
        critical=True,
        validations=(VALIDATION_DIGITS,),
    ),
    _field(_T31, "block_no", "rta.parcel.block_number", 8, section="parcel", critical=True),
    _field(_T31, "parcel_no", "rta.parcel.parcel_number", 9, section="parcel", critical=True),
    _field(
        _T31,
        "extent",
        "rta.parcel.extent",
        10,
        section="parcel",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_UNIT_CONVERSION),
        validations=(VALIDATION_EXTENT_HECTARES,),
    ),
    _field(
        _T31,
        "place_of_registration",
        "rta.title.place_of_registration",
        11,
        section="title",
        critical=True,
    ),
    # The certificate the application supersedes, not the one it asks for.
    _field(
        _T31,
        "existing_title_certificate_no",
        "rta.title.certificate_no",
        12,
        section="title",
        critical=True,
    ),
    _field(
        _T31,
        "registered_owner_name",
        "rta.title.registered_owner_name",
        13,
        section="title",
        critical=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_TRANSLITERATION),
    ),
    _field(
        _T31,
        "instrument_attestation_date",
        "rta.instrument.attestation_date",
        14,
        section="application",
        critical=True,
        required=False,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_FORMAT_DATE),
        validations=(VALIDATION_ISO_DATE,),
    ),
    # Gap: no canonical fact type for the filing date of an application.
    _field(
        _T31,
        "application_date",
        None,
        15,
        section="application",
        critical=False,
        required=False,
        human_confirmation=True,
        transformations=(TRANSFORM_EXACT_COPY, TRANSFORM_FORMAT_DATE),
        validations=(VALIDATION_ISO_DATE,),
    ),
)


# ── The registry ─────────────────────────────────────────────────────────────

FORM_TEMPLATES: tuple[FormTemplateDefinition, ...] = (
    # The 22 prescribed instruments of the 2022 amendment, in id order.
    _gazette_2022_form(
        "07",
        "7",
        ("lk.rta.instrument.subdivision_amalgamation",),
        (_act("36"),),
    ),
    _gazette_2022_form(
        "08",
        "8",
        ("lk.rta.instrument.transfer_sale",),
        (
            _act("43"),
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="transfer submission pack RP-BASE"),
            _RP_DUP,
        ),
        field_mappings=_FORM_08_FIELDS,
    ),
    _gazette_2022_form(
        "09",
        "9",
        ("lk.rta.instrument.gift",),
        (_act("46"), _RP_DUP),
    ),
    _gazette_2022_form("10", "10", ("lk.rta.instrument.lease",)),
    _gazette_2022_form("11", "11", ("lk.rta.instrument.mortgage",)),
    _gazette_2022_form(
        "12",
        "12",
        ("lk.rta.instrument.mortgage_cancel",),
        (
            SourceCitation(
                SRC_RGD_TRANSACTIONS.id,
                locator="cancellation submission pack RP-BASE",
                note="Prior mortgage and discharge/release evidence accompany the form (§5.6).",
            ),
        ),
        field_mappings=_FORM_12_FIELDS,
    ),
    _gazette_2022_form("13", "13", ("lk.rta.instrument.caveat",)),
    _gazette_2022_form(
        "21",
        "21",
        ("lk.rta.instrument.condominium_register",),
        (_act("50-52"),),
    ),
    _gazette_2022_form("23", "23", ("lk.rta.instrument.sale_agreement",)),
    _gazette_2022_form("24", "24", ("lk.rta.instrument.security_bond_transfer",)),
    _gazette_2022_form(
        "25",
        "25",
        ("lk.rta.instrument.certificate_sale_register",),
        (_act("56"),),
    ),
    _gazette_2022_form("26", "26", ("lk.rta.instrument.sale_agreement_cancel",)),
    _gazette_2022_form("27", "27", ("lk.rta.instrument.gift_cancel",)),
    _gazette_2022_form(
        "28",
        "28",
        ("lk.rta.instrument.life_interest_cancel",),
        (_act("46"),),
    ),
    _gazette_2022_form("29", "29", ("lk.rta.instrument.lease_cancel",)),
    # Form 30 cancels a caveat. Operational Ti.Re.30 is a search/copy
    # application and is a separate record below (§Executive 11).
    _gazette_2022_form("30", "30", ("lk.rta.instrument.caveat_cancel",)),
    # Form 31 registers an ADDRESS. It is not the Ti.Re.31 application for a
    # new Title Certificate, which lives in the OPERATIONAL namespace below.
    _gazette_2022_form("31", "31", ("lk.rta.instrument.address_register",)),
    _gazette_2022_form(
        "32",
        "32",
        ("lk.rta.instrument.land_exchange",),
        (_RP_DUP,),
    ),
    _gazette_2022_form("33", "33", ("lk.rta.instrument.life_interest_cancel_death",)),
    _gazette_2022_form("34", "34", ("lk.rta.instrument.certificate_sale_cancel",)),
    _gazette_2022_form(
        "35",
        "35",
        ("lk.rta.instrument.servitude_access_transfer",),
        (_act("75"),),
    ),
    _gazette_2022_form("36", "36", ("lk.rta.instrument.life_interest_holder_lease",)),
    # Related regulation forms that are not one of the 22 (§9.1).
    #
    # A s. 14 determination is made by the Registrar during initial compilation,
    # not by a court, so it stays in REGULATION; the COURT namespace is reserved
    # for the ss. 21-22 District Court material below.
    _gazette_2022_form(
        "04",
        "4",
        ("lk.rta.process.initial_compilation", "lk.rta.process.title_settlement_dispute"),
        (_act("14"),),
        regulation_15_1=False,
    ),
    # Survey-owner consent described in the 2022 amendment. It is a consent, not
    # the instrument that effects a subdivision, so it does not claim
    # `lk.rta.instrument.subdivision_amalgamation`: that subtype resolves to
    # Form 7 alone, and a consent that must accompany it belongs on the
    # subtype's taxonomy `companion_template_ids`, exactly as Ti.Re.31 does for
    # a transfer. Claiming it here would make `templates_for_subtype` return two
    # candidates for one confirmed subtype and break §9.1 form selection.
    _gazette_2022_form(
        "39",
        "39",
        ("lk.rta.process.initial_compilation",),
        (_act("36"),),
        regulation_15_1=False,
    ),
    # Title Certificate and Title Register variants. `subtype_ids` is empty on
    # purpose: these are registry-issued artifacts that Draftly reads and
    # compares against, never instruments it drafts. The class variants are
    # separate records because s. 14(a) and s. 14(b) titles are different
    # outcomes (§1.2) and a handout conflating them is wrong.
    _gazette_2022_form(
        "14.first_class",
        "14",
        (),
        (_act("14(a)"), _act("37")),
        namespace=TemplateNamespace.TITLE_CERTIFICATE,
        regulation_15_1=False,
    ),
    _gazette_2022_form(
        "14.second_class",
        "14",
        (),
        (_act("14(b)"), _act("37")),
        namespace=TemplateNamespace.TITLE_CERTIFICATE,
        regulation_15_1=False,
    ),
    _gazette_2022_form(
        "19.first_class",
        "19",
        (),
        (_act("14(a)"), _act("32-33")),
        namespace=TemplateNamespace.TITLE_REGISTER,
        regulation_15_1=False,
    ),
    _gazette_2022_form(
        "19.second_class",
        "19",
        (),
        (_act("14(b)"), _act("32-33")),
        namespace=TemplateNamespace.TITLE_REGISTER,
        regulation_15_1=False,
    ),
    # District Court referral material. Which of the two carries the s. 21
    # referral and which the s. 22 appeal is not settled by the source pack,
    # so both cite both sections and neither is used for drafting.
    _gazette_2022_form(
        "37",
        "37",
        ("lk.rta.process.title_settlement_dispute",),
        (_act("21"), _act("22")),
        namespace=TemplateNamespace.COURT,
        regulation_15_1=False,
    ),
    _gazette_2022_form(
        "38",
        "38",
        ("lk.rta.process.title_settlement_dispute", "lk.rta.process.second_class_challenge"),
        (_act("21"), _act("22")),
        namespace=TemplateNamespace.COURT,
        regulation_15_1=False,
    ),
    # ── Operational RGD forms — a different namespace, not a variant ──────────
    #
    # Ti.Re.31 is listed only against the title-certificate service. Its use
    # alongside a Form 8 transfer is a companion-template link on the subtype
    # (taxonomy `companion_template_ids`), not a second subtype claim here.
    FormTemplateDefinition(
        id="rta.ops.tire.31",
        version=_DRAFT_VERSION,
        namespace=TemplateNamespace.OPERATIONAL,
        form_number="31",
        title_key="rta.form.ops_tire_31.title",
        subtype_ids=("lk.rta.service.new_title_certificate_application",),
        languages=("si",),
        status=TemplateStatus.DRAFT_TRANSCRIPTION,
        sources=(
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="new Title Certificate"),
            SourceCitation(SRC_TIRE_31_SCAN.id),
        ),
        official_artifact_source_record_id=SRC_TIRE_31_SCAN.id,
        page_range=None,
        field_mappings=_TIRE_31_FIELDS,
        known_source_defect_keys=(
            DEFECT_TRANSLATION_UNVERIFIED,
            DEFECT_REVISION_UNVERIFIED,
            DEFECT_SCAN_CONTAINS_PRIVATE_DATA,
        ),
    ),
    FormTemplateDefinition(
        id="rta.ops.tire.30",
        version=_DRAFT_VERSION,
        namespace=TemplateNamespace.OPERATIONAL,
        form_number="30",
        title_key="rta.form.ops_tire_30.title",
        subtype_ids=("lk.rta.service.certified_extract",),
        languages=("si",),
        status=TemplateStatus.DRAFT_TRANSCRIPTION,
        sources=(
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="searches and certified copies"),
            SourceCitation(
                SRC_RGD_CHARGES.id,
                locator="search and copy charges",
                note="Fees are versioned data and are re-verified, never hard-coded (§13.4).",
            ),
        ),
        # No copy of the current form is held; only the service is documented.
        official_artifact_source_record_id=None,
        page_range=None,
        known_source_defect_keys=(
            DEFECT_OFFICIAL_ARTIFACT_NOT_HELD,
            DEFECT_REVISION_UNVERIFIED,
        ),
    ),
)


_BY_ID: dict[str, FormTemplateDefinition] = {t.id: t for t in FORM_TEMPLATES}


# ── Lookups ──────────────────────────────────────────────────────────────────


def get_template(template_id: str) -> FormTemplateDefinition | None:
    return _BY_ID.get(template_id)


def require_template(template_id: str) -> FormTemplateDefinition:
    template = _BY_ID.get(template_id)
    if template is None:
        raise KeyError(f"Unknown form template '{template_id}'.")
    return template


def templates_for_subtype(subtype_id: str) -> tuple[FormTemplateDefinition, ...]:
    """Templates declared for an exact subtype.

    Companion operational forms are linked from the subtype, so a transfer
    returns Form 8 here and picks up Ti.Re.31 through the taxonomy.
    """
    return tuple(t for t in FORM_TEMPLATES if subtype_id in t.subtype_ids)


def template_ids() -> tuple[str, ...]:
    return tuple(t.id for t in FORM_TEMPLATES)


def assert_no_id_collision() -> None:
    """Enforce §9.1: the namespaced id, never the form number, is the key.

    Gazette Form 31 and operational Ti.Re.31 share a printed number and must
    remain two records; only a repeated *id* is a packaging error.
    """
    duplicates = sorted(i for i, n in Counter(t.id for t in FORM_TEMPLATES).items() if n > 1)
    if duplicates:
        raise ValueError(f"Duplicate form template ids: {', '.join(duplicates)}")


def assert_one_template_per_instrument_subtype() -> None:
    """Enforce §9.1: a confirmed instrument subtype selects exactly one form.

    ``templates_for_subtype`` is the form-selection path, so a drafted
    instrument subtype claimed by two templates makes the selection ambiguous
    and lets a related form (a consent, a certificate) be drafted as if it were
    the instrument. Forms that merely accompany an instrument are linked from
    the taxonomy's ``companion_template_ids``, never by a second claim here.

    Process and registry-service subtypes are exempt: nothing is drafted from
    them, and several related records legitimately reference the same process.
    """
    claims: Counter[str] = Counter()
    for template in FORM_TEMPLATES:
        claims.update(s for s in template.subtype_ids if s.startswith("lk.rta.instrument."))
    contested = sorted(s for s, n in claims.items() if n > 1)
    if contested:
        raise ValueError(
            f"Instrument subtypes claimed by more than one form template: {', '.join(contested)}"
        )


def assert_transformations_declared() -> None:
    """Enforce §9.3: a field may only allow a transformation from the vocabulary.

    A hand-typed transformation id that no engine implements would otherwise
    read as a permission grant and silently allow nothing.
    """
    unknown = sorted(
        f"{template.id}.{mapping.field_id}:{transformation}"
        for template in FORM_TEMPLATES
        for mapping in template.field_mappings
        for transformation in mapping.allowed_transformation_ids
        if transformation not in ALLOWED_TRANSFORMATION_IDS
    )
    if unknown:
        raise ValueError(f"Undeclared field transformations: {', '.join(unknown)}")


# Checked at import so a collision can never reach a matter: the lookup dict
# above would otherwise silently keep the last definition of a repeated id.
assert_no_id_collision()
assert_one_template_per_instrument_subtype()
assert_transformations_declared()
