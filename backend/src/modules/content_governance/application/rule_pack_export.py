"""Serialise the RTA rule pack to the shape both the API and the frontend read.

The frontend needs the taxonomy to render the New Matter screen before it has a
matter to ask about, so it ships a copy. A copy is a second source of truth
unless something proves the two are identical — that is what
`scripts/export_rta_contracts.py` writes and `tests/contract` asserts.

Only *definitions* are exported. No matter data, no client data, and no
prescribed legal wording passes through here.
"""

from __future__ import annotations

from typing import Any

from src.modules.content_governance.contracts import (
    ALL_QUESTIONS,
    ALL_SUBTYPES,
    CHECK_DEFINITIONS,
    CHECKLIST_MODULES,
    CONDITIONAL_MODULES,
    CURRENT_VERSIONS,
    DOCUMENT_CLASSES,
    FAMILIES,
    FORM_TEMPLATES,
    LEGACY_MATTER_TYPE_MAP,
    REGIME_ID,
    REQUIREMENTS,
    SEED_SOURCE_RECORDS,
)


def _sources(citations: Any) -> list[dict[str, str]]:
    return [
        {"sourceRecordId": c.source_record_id, "locator": c.locator, "note": c.note}
        for c in citations
    ]


def taxonomy_contract() -> dict[str, Any]:
    """Families, all 22 instruments, processes, services, and conditional modules."""
    return {
        "regimeId": REGIME_ID,
        "versions": CURRENT_VERSIONS.as_dict(),
        "families": [
            {
                "id": family.id.value,
                "labelKey": family.label_key,
                "purposeKey": family.purpose_key,
                "isTransactionFamily": family.is_transaction_family,
                "order": family.order,
            }
            for family in FAMILIES
        ],
        "subtypes": [
            {
                "id": subtype.id,
                "kind": subtype.kind.value,
                "familyId": subtype.family_id.value,
                "labelKey": subtype.label_key,
                "examinationLevel": subtype.examination_level.value,
                "releaseTier": subtype.release_tier.value,
                "gazetteFormNumber": subtype.gazette_form_number,
                "formTemplateId": subtype.form_template_id,
                "companionTemplateIds": list(subtype.companion_template_ids),
                "defaultModuleDefinitionIds": list(subtype.default_module_definition_ids),
                "outOfV0ReasonKey": subtype.out_of_v0_reason_key,
                "requiresDeclaredLegalBasis": subtype.requires_declared_legal_basis,
                "order": subtype.order,
                "sources": _sources(subtype.sources),
            }
            for subtype in ALL_SUBTYPES
        ],
        "conditionalModules": [
            {
                "id": module.id,
                "labelKey": module.label_key,
                "checklistModuleIds": list(module.checklist_module_ids),
                "excludesV0": module.excludes_v0,
            }
            for module in CONDITIONAL_MODULES
        ],
        "legacyMatterTypeMap": dict(LEGACY_MATTER_TYPE_MAP),
    }


def questions_contract() -> dict[str, Any]:
    return {
        "version": CURRENT_VERSIONS.questions,
        "questions": [
            {
                "id": question.id,
                "stage": question.stage.value,
                "order": question.order,
                "promptKey": question.prompt_key,
                "whyKey": question.why_key,
                "valueKind": question.value_kind.value,
                "options": [
                    {"value": option.value, "labelKey": option.label_key}
                    for option in question.options
                ],
                "activatesModuleIds": list(question.activates_module_ids),
                "triggerNoteKey": question.trigger_note_key,
                "inferable": question.inferable,
                "lawyerConfirmationRequired": question.lawyer_confirmation_required,
                "controlsV0Eligibility": question.controls_v0_eligibility,
                "v0Required": question.v0_required,
                "allowsUnknown": question.allows_unknown,
            }
            for question in ALL_QUESTIONS
        ],
    }


def checklist_contract() -> dict[str, Any]:
    return {
        "version": CURRENT_VERSIONS.checklist,
        "modules": [
            {
                "id": module.id,
                "version": module.version,
                "labelKey": module.label_key,
                "descriptionKey": module.description_key,
                "requirementIds": list(module.requirement_ids),
                "order": module.order,
                "sources": _sources(module.sources),
            }
            for module in CHECKLIST_MODULES
        ],
        "requirements": [
            {
                "id": requirement.id,
                "moduleId": requirement.module_id,
                "labelKey": requirement.label_key,
                "explanationKey": requirement.explanation_key,
                "mandatoryBasis": requirement.mandatory_basis.value,
                "group": requirement.group.value,
                "acceptedDocumentClassIds": list(requirement.accepted_document_class_ids),
                "mayBeSatisfiedByCombinedDocument": (
                    requirement.may_be_satisfied_by_combined_document
                ),
                "physicalOriginalPolicy": requirement.physical_original_policy.value,
                "currencyMaxAgeDays": requirement.currency_max_age_days,
                "unsatisfiedSeverity": requirement.unsatisfied_severity.value,
                "unsatisfiedBlockerKind": requirement.unsatisfied_blocker_kind.value,
                "waivable": requirement.waivable,
                "localAuthorityScoped": requirement.local_authority_scoped,
                "order": requirement.order,
                "sources": _sources(requirement.sources),
            }
            for requirement in REQUIREMENTS
        ],
    }


def checks_contract() -> dict[str, Any]:
    return {
        "version": CURRENT_VERSIONS.checks,
        "checks": [
            {
                "id": check.id,
                "version": check.version,
                "labelKey": check.label_key,
                "comparisonKey": check.comparison_key,
                "inputFactTypeIds": list(check.input_fact_type_ids),
                "failureSeverity": check.failure_severity.value,
                "failureBlockerKind": check.failure_blocker_kind.value,
                "issueTypeId": check.issue_type_id,
                "safetyRuleKey": check.safety_rule_key,
                "absenceIsNotEvidence": check.absence_is_not_evidence,
                "blocksDraftGeneration": check.blocks_draft_generation,
                "blocksApproval": check.blocks_approval,
                "v0Required": check.v0_required,
                "sources": _sources(check.sources),
            }
            for check in CHECK_DEFINITIONS
        ],
    }


def forms_contract() -> dict[str, Any]:
    """Template metadata only.

    No template in this repository is a lawyer-approved production rendering,
    so ``registrationReadyCapable`` is false everywhere and the UI must block
    registration-ready export (§9.5).
    """
    return {
        "version": CURRENT_VERSIONS.forms,
        "templates": [
            {
                "id": template.id,
                "version": template.version,
                "namespace": template.namespace.value,
                "formNumber": template.form_number,
                "titleKey": template.title_key,
                "subtypeIds": list(template.subtype_ids),
                "languages": list(template.languages),
                "status": template.status.value,
                "approvedByLawyerId": template.approved_by_lawyer_id,
                "productionLayoutAvailable": template.production_layout_available,
                "registrationReadyCapable": template.registration_ready_capable,
                "knownSourceDefectKeys": list(template.known_source_defect_keys),
                "fieldMappings": [
                    {
                        "fieldId": mapping.field_id,
                        "labelKey": mapping.label_key,
                        "factTypeId": mapping.fact_type_id,
                        "required": mapping.required,
                        "critical": mapping.critical,
                        "humanConfirmationRequired": mapping.human_confirmation_required,
                        "sectionKey": mapping.section_key,
                        "order": mapping.order,
                    }
                    for mapping in template.field_mappings
                ],
                "sources": _sources(template.sources),
            }
            for template in FORM_TEMPLATES
        ],
    }


def document_classes_contract() -> dict[str, Any]:
    return {
        "version": CURRENT_VERSIONS.document_classes,
        "classes": [
            {
                "id": document_class.id,
                "labelKey": document_class.label_key,
                "descriptionKey": document_class.description_key,
                "tags": list(document_class.tags),
                "maySatisfyMultipleRequirements": (
                    document_class.may_satisfy_multiple_requirements
                ),
                "redFlag": document_class.red_flag,
                "exclusionIndicator": document_class.exclusion_indicator,
                "extractionTemplateKind": document_class.extraction_template_kind,
                "order": document_class.order,
            }
            for document_class in DOCUMENT_CLASSES
        ],
    }


def sources_contract() -> dict[str, Any]:
    """Source records with their verification state.

    ``requiresReverification`` is true for every seed record, and the UI must
    show ``SOURCE REVERIFICATION REQUIRED`` rather than presenting an
    unverified fee or instruction as final (§13.2.6).
    """
    return {
        "sources": [
            {
                "id": record.id,
                "sourceClass": record.source_class.value,
                "title": record.title,
                "issuingAuthority": record.issuing_authority,
                "jurisdiction": record.jurisdiction,
                "citation": record.citation,
                "canonicalUrl": record.canonical_url,
                "publicationDate": (
                    record.publication_date.isoformat() if record.publication_date else None
                ),
                "retrievedAt": record.retrieved_at.isoformat() if record.retrieved_at else None,
                "verifiedAt": record.verified_at.isoformat() if record.verified_at else None,
                "confidence": record.confidence.value,
                "currencyStatus": record.currency_status.value,
                "lawyerApproved": record.lawyer_approval is not None,
                "requiresReverification": record.requires_reverification,
                "notes": record.notes,
            }
            for record in SEED_SOURCE_RECORDS
        ],
    }


def full_rule_pack_contract() -> dict[str, Any]:
    """Everything, in one document, for the contract test and the API."""
    return {
        "versions": CURRENT_VERSIONS.as_dict(),
        "taxonomy": taxonomy_contract(),
        "questions": questions_contract(),
        "checklist": checklist_contract(),
        "checks": checks_contract(),
        "forms": forms_contract(),
        "documentClasses": document_classes_contract(),
        "sources": sources_contract(),
    }
