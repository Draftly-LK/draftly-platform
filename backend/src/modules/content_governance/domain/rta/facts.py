"""Canonical RTA fact types and the critical-fact set.

A *fact type* is what can be known about a matter — the registered owner's
name, the cadastral map number, the attestation date. A *fact* is one
evidence-linked value for one of them, owned by `verification`.

The one rule that matters here: a fact type marked ``critical`` requires
explicit lawyer confirmation before it can populate a form field or satisfy an
approval gate, **at any model confidence, including 1.00** (§6.4). There is no
confidence bypass and no "auto-confirm above threshold" path.

Field keys reuse the vocabulary already extracted by
`modules/document/domain/registry.py` (``cadastralMapNo``, ``parcelNo``,
``extent``, ``transferorName``, …) so the prescribed form stays the single
contract for what is extracted, what gates drafting, and what renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FactSubject(str, Enum):
    """What the fact is about — used to group the verification queue."""

    MATTER = "MATTER"
    REGIME = "REGIME"
    TITLE = "TITLE"
    PARCEL = "PARCEL"
    PARTY = "PARTY"
    INSTRUMENT = "INSTRUMENT"
    INTEREST = "INTEREST"
    ORGANIZATION = "ORGANIZATION"
    PROCESS = "PROCESS"


class FactValueKind(str, Enum):
    """Enough typing for deterministic comparison and unit conversion."""

    TEXT = "TEXT"
    IDENTIFIER = "IDENTIFIER"
    ENUM = "ENUM"
    DATE = "DATE"
    MONEY = "MONEY"
    AREA = "AREA"
    BOOLEAN = "BOOLEAN"
    COUNT = "COUNT"


@dataclass(frozen=True)
class FactTypeDefinition:
    """One knowable particular of an RTA matter."""

    id: str
    #: Extraction/form-binding key; ``None`` when the fact has no form field.
    field_key: str | None
    subject: FactSubject
    value_kind: FactValueKind
    label_key: str
    #: §6.4 — critical facts never bypass lawyer confirmation.
    critical: bool
    #: A negative proposition ("no mortgage") is never inferred from the
    #: absence of a document (§6.4, §7.2). These need current search evidence.
    negative_requires_search_evidence: bool = False


def _f(
    fact_id: str,
    field_key: str | None,
    subject: FactSubject,
    kind: FactValueKind,
    critical: bool,
    *,
    negative_requires_search_evidence: bool = False,
) -> FactTypeDefinition:
    return FactTypeDefinition(
        id=fact_id,
        field_key=field_key,
        subject=subject,
        value_kind=kind,
        label_key=f"rta.fact.{fact_id.rsplit('.', 1)[-1]}",
        critical=critical,
        negative_requires_search_evidence=negative_requires_search_evidence,
    )


FACT_TYPES: tuple[FactTypeDefinition, ...] = (
    # ── Regime and instrument ────────────────────────────────────────────────
    _f("rta.regime.coverage_confirmed", None, FactSubject.REGIME, FactValueKind.BOOLEAN, True),
    _f("rta.instrument.exact_subtype", None, FactSubject.INSTRUMENT, FactValueKind.ENUM, True),
    _f("rta.instrument.disposition_scope", None, FactSubject.INSTRUMENT, FactValueKind.ENUM, True),
    _f("rta.instrument.attestation_date", None, FactSubject.INSTRUMENT, FactValueKind.DATE, True),
    _f(
        "rta.instrument.consideration",
        "consideration",
        FactSubject.INSTRUMENT,
        FactValueKind.MONEY,
        True,
    ),
    _f(
        "rta.instrument.consideration_words",
        "considerationWords",
        FactSubject.INSTRUMENT,
        FactValueKind.TEXT,
        True,
    ),
    _f(
        "rta.instrument.notary_name",
        "notaryName",
        FactSubject.INSTRUMENT,
        FactValueKind.TEXT,
        False,
    ),
    _f(
        "rta.instrument.notary_code",
        "notaryCode",
        FactSubject.INSTRUMENT,
        FactValueKind.IDENTIFIER,
        False,
    ),
    # ── Title ────────────────────────────────────────────────────────────────
    _f(
        "rta.title.certificate_no",
        "titleCertificateNo",
        FactSubject.TITLE,
        FactValueKind.IDENTIFIER,
        True,
    ),
    _f("rta.title.class", "classOfTitle", FactSubject.TITLE, FactValueKind.ENUM, True),
    _f(
        "rta.title.place_of_registration",
        "placeOfRegistration",
        FactSubject.TITLE,
        FactValueKind.TEXT,
        True,
    ),
    _f("rta.title.registered_owner_name", "ownerName", FactSubject.TITLE, FactValueKind.TEXT, True),
    _f("rta.title.register_search_datetime", None, FactSubject.TITLE, FactValueKind.DATE, True),
    # ── Parcel ───────────────────────────────────────────────────────────────
    _f("rta.parcel.district", "district", FactSubject.PARCEL, FactValueKind.TEXT, True),
    _f("rta.parcel.ds_division", "dsDivision", FactSubject.PARCEL, FactValueKind.TEXT, True),
    _f("rta.parcel.gn_division", "gnDivision", FactSubject.PARCEL, FactValueKind.TEXT, True),
    _f("rta.parcel.village", "village", FactSubject.PARCEL, FactValueKind.TEXT, False),
    _f(
        "rta.parcel.assessment_number",
        "assessmentNumber",
        FactSubject.PARCEL,
        FactValueKind.IDENTIFIER,
        False,
    ),
    _f(
        "rta.parcel.cadastral_map_number",
        "cadastralMapNo",
        FactSubject.PARCEL,
        FactValueKind.IDENTIFIER,
        True,
    ),
    _f("rta.parcel.block_number", "blockNo", FactSubject.PARCEL, FactValueKind.IDENTIFIER, True),
    _f("rta.parcel.sheet_number", "sheetNo", FactSubject.PARCEL, FactValueKind.IDENTIFIER, True),
    _f("rta.parcel.parcel_number", "parcelNo", FactSubject.PARCEL, FactValueKind.IDENTIFIER, True),
    _f("rta.parcel.extent", "extent", FactSubject.PARCEL, FactValueKind.AREA, True),
    _f(
        "rta.parcel.extent_subject_to_transaction",
        "extentSubjectToTransfer",
        FactSubject.PARCEL,
        FactValueKind.AREA,
        True,
    ),
    _f("rta.parcel.kind", None, FactSubject.PARCEL, FactValueKind.ENUM, True),
    _f(
        "rta.parcel.survey_plan_no",
        "surveyPlanNo",
        FactSubject.PARCEL,
        FactValueKind.IDENTIFIER,
        False,
    ),
    _f("rta.parcel.surveyor_name", "surveyorName", FactSubject.PARCEL, FactValueKind.TEXT, False),
    _f("rta.parcel.land_name", "landName", FactSubject.PARCEL, FactValueKind.TEXT, False),
    _f("rta.parcel.lot_no", "lotNo", FactSubject.PARCEL, FactValueKind.IDENTIFIER, False),
    _f("rta.parcel.boundary_north", "boundaryNorth", FactSubject.PARCEL, FactValueKind.TEXT, False),
    _f("rta.parcel.boundary_east", "boundaryEast", FactSubject.PARCEL, FactValueKind.TEXT, False),
    _f("rta.parcel.boundary_south", "boundarySouth", FactSubject.PARCEL, FactValueKind.TEXT, False),
    _f("rta.parcel.boundary_west", "boundaryWest", FactSubject.PARCEL, FactValueKind.TEXT, False),
    _f("rta.parcel.building_present", None, FactSubject.PARCEL, FactValueKind.BOOLEAN, False),
    # ── Parties ──────────────────────────────────────────────────────────────
    _f("rta.party.transferor_name", "transferorName", FactSubject.PARTY, FactValueKind.TEXT, True),
    _f(
        "rta.party.transferor_nic",
        "transferorNic",
        FactSubject.PARTY,
        FactValueKind.IDENTIFIER,
        True,
    ),
    _f(
        "rta.party.transferor_address",
        "transferorAddress",
        FactSubject.PARTY,
        FactValueKind.TEXT,
        True,
    ),
    _f("rta.party.transferee_name", "transfereeName", FactSubject.PARTY, FactValueKind.TEXT, True),
    _f(
        "rta.party.transferee_nic",
        "transfereeNic",
        FactSubject.PARTY,
        FactValueKind.IDENTIFIER,
        True,
    ),
    _f(
        "rta.party.transferee_address",
        "transfereeAddress",
        FactSubject.PARTY,
        FactValueKind.TEXT,
        True,
    ),
    _f("rta.party.capacity_confirmed", None, FactSubject.PARTY, FactValueKind.BOOLEAN, True),
    _f("rta.party.signing_authority", None, FactSubject.PARTY, FactValueKind.TEXT, True),
    _f("rta.party.all_natural_persons", None, FactSubject.PARTY, FactValueKind.BOOLEAN, True),
    # The owner-versus-transferor conclusion. It is its own fact rather than a
    # comparison the gates recompute, because it is a lawyer's conclusion about
    # two names — not a string equality (§7.2 CHK_OWNER_TRANSFEROR).
    _f(
        "rta.party.transferor_is_registered_owner",
        None,
        FactSubject.PARTY,
        FactValueKind.BOOLEAN,
        True,
    ),
    _f(
        "rta.instrument.special_condition_present",
        None,
        FactSubject.INSTRUMENT,
        FactValueKind.BOOLEAN,
        True,
    ),
    _f("rta.party.coowners_present", None, FactSubject.PARTY, FactValueKind.BOOLEAN, True),
    _f("rta.party.creates_coownership", None, FactSubject.PARTY, FactValueKind.BOOLEAN, True),
    # ── Interests and encumbrances ───────────────────────────────────────────
    _f(
        "rta.interest.mortgage_status",
        None,
        FactSubject.INTEREST,
        FactValueKind.ENUM,
        True,
        negative_requires_search_evidence=True,
    ),
    _f(
        "rta.interest.mortgage_reference",
        None,
        FactSubject.INTEREST,
        FactValueKind.IDENTIFIER,
        True,
    ),
    _f("rta.interest.mortgagee_name", None, FactSubject.INTEREST, FactValueKind.TEXT, True),
    _f(
        "rta.interest.mortgagee_authority_confirmed",
        None,
        FactSubject.INTEREST,
        FactValueKind.BOOLEAN,
        True,
    ),
    _f(
        "rta.interest.discharge_evidence_kind", None, FactSubject.INTEREST, FactValueKind.ENUM, True
    ),
    _f(
        "rta.interest.lease_status",
        None,
        FactSubject.INTEREST,
        FactValueKind.ENUM,
        True,
        negative_requires_search_evidence=True,
    ),
    _f(
        "rta.interest.occupation_status",
        None,
        FactSubject.INTEREST,
        FactValueKind.ENUM,
        True,
        negative_requires_search_evidence=True,
    ),
    _f(
        "rta.interest.life_interest_present",
        None,
        FactSubject.INTEREST,
        FactValueKind.BOOLEAN,
        True,
    ),
    _f("rta.interest.servitude_present", None, FactSubject.INTEREST, FactValueKind.BOOLEAN, False),
    _f(
        "rta.interest.caveat_or_notice_status",
        None,
        FactSubject.INTEREST,
        FactValueKind.ENUM,
        True,
        negative_requires_search_evidence=True,
    ),
    # ── Process and dispute ──────────────────────────────────────────────────
    _f("rta.process.dispute_stage", None, FactSubject.PROCESS, FactValueKind.ENUM, True),
    _f(
        "rta.process.transmission_completed", None, FactSubject.PROCESS, FactValueKind.BOOLEAN, True
    ),
    _f("rta.process.probate_path", None, FactSubject.PROCESS, FactValueKind.ENUM, True),
    _f(
        "rta.process.court_proceeding_reference",
        None,
        FactSubject.PROCESS,
        FactValueKind.IDENTIFIER,
        True,
    ),
    # ── Organisation (company party) ─────────────────────────────────────────
    _f("rta.org.company_name", None, FactSubject.ORGANIZATION, FactValueKind.TEXT, True),
    _f("rta.org.company_number", None, FactSubject.ORGANIZATION, FactValueKind.IDENTIFIER, True),
    _f("rta.org.resolution_date", None, FactSubject.ORGANIZATION, FactValueKind.DATE, True),
    # ── Local authority (contextual evidence, never title) ───────────────────
    _f("rta.local.assessment_register_name", None, FactSubject.MATTER, FactValueKind.TEXT, False),
    _f("rta.local.local_authority_id", None, FactSubject.MATTER, FactValueKind.IDENTIFIER, False),
    _f("rta.local.rates_paid_to", None, FactSubject.MATTER, FactValueKind.DATE, False),
)

_BY_ID: dict[str, FactTypeDefinition] = {f.id: f for f in FACT_TYPES}
_BY_FIELD_KEY: dict[str, FactTypeDefinition] = {
    f.field_key: f for f in FACT_TYPES if f.field_key is not None
}

CRITICAL_FACT_TYPE_IDS: frozenset[str] = frozenset(f.id for f in FACT_TYPES if f.critical)


def get_fact_type(fact_type_id: str) -> FactTypeDefinition | None:
    return _BY_ID.get(fact_type_id)


def fact_type_for_field(field_key: str) -> FactTypeDefinition | None:
    return _BY_FIELD_KEY.get(field_key)


def is_critical(fact_type_id: str) -> bool:
    """No confidence value, model score, or corroboration count changes this."""
    return fact_type_id in CRITICAL_FACT_TYPE_IDS
