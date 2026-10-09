"""Read-only catalogue exports existing authority without client data."""

import json
from pathlib import Path

from src.modules.content_governance.application import rule_pack_export
from src.modules.content_governance.contracts import (
    CURRENT_VERSIONS,
    FACT_TYPES,
    DischargeEvidenceKind,
    DispositionScope,
    DisputeStage,
    EncumbranceStatus,
    NoticeStatus,
    OccupationStatus,
    ParcelKind,
    ProbatePath,
    TitleClass,
)


def test_fact_types_are_lossless_definition_metadata() -> None:
    contract = rule_pack_export.fact_types_contract()
    assert contract["versions"] == CURRENT_VERSIONS.as_dict()
    assert [{k: v for k, v in row.items() if k != "options"} for row in contract["factTypes"]] == [
        {
            "id": fact.id,
            "fieldKey": fact.field_key,
            "labelKey": fact.label_key,
            "subject": fact.subject.value,
            "valueKind": fact.value_kind.value,
            "critical": fact.critical,
            "negativeRequiresSearchEvidence": fact.negative_requires_search_evidence,
        }
        for fact in FACT_TYPES
    ]


def test_existing_enum_relationships_export_exact_choices() -> None:
    by_id = {row["id"]: row for row in rule_pack_export.fact_types_contract()["factTypes"]}
    relationships = {
        "rta.title.class": TitleClass,
        "rta.interest.mortgage_status": EncumbranceStatus,
        "rta.interest.lease_status": EncumbranceStatus,
        "rta.interest.occupation_status": OccupationStatus,
        "rta.interest.caveat_or_notice_status": NoticeStatus,
        "rta.interest.discharge_evidence_kind": DischargeEvidenceKind,
        "rta.process.probate_path": ProbatePath,
        "rta.instrument.disposition_scope": DispositionScope,
        "rta.parcel.kind": ParcelKind,
        "rta.process.dispute_stage": DisputeStage,
    }
    for fact_id, enum_type in relationships.items():
        assert [option["value"] for option in by_id[fact_id]["options"]] == [
            v.value for v in enum_type
        ]
        assert all(option["labelKey"] for option in by_id[fact_id]["options"])
    assert by_id["rta.party.holder_name_en"]["options"] == []


def test_catalogue_labels_resolve_in_both_ui_languages() -> None:
    messages = Path(__file__).resolve().parents[3] / "frontend/src/lib/i18n/messages"
    contract = rule_pack_export.fact_types_contract()
    for locale in ("en", "si"):
        catalogue = json.loads((messages / f"{locale}.json").read_text(encoding="utf-8"))
        for fact in contract["factTypes"]:
            for key in [fact["labelKey"], *(option["labelKey"] for option in fact["options"])]:
                label = catalogue
                for part in key.split("."):
                    label = label[part]
                assert isinstance(label, str) and label.strip(), (locale, key)


def test_fact_type_labels_do_not_fall_back_to_english_in_sinhala() -> None:
    messages = Path(__file__).resolve().parents[3] / "frontend/src/lib/i18n/messages"
    english = json.loads((messages / "en.json").read_text(encoding="utf-8"))["rta"]["fact"]
    sinhala = json.loads((messages / "si.json").read_text(encoding="utf-8"))["rta"]["fact"]
    assert not [key for key, label in english.items() if sinhala[key] == label]
