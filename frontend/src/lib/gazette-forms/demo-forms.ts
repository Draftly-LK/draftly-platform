import { DEMO_MATTER_ID } from "@/lib/mocks/fixtures";
import type { ApiFormField, ApiGeneratedForm, ApiPreflight, ApiPreflightItem, UnresolvedReason } from "@/types/rta";

/*
 * SYNTHETIC demo forms for the offline workspace (no backend). Every value is
 * invented and labelled synthetic; nothing here comes from a real matter.
 * Field ids, order, criticality, and the decision rules mirror
 * backend/src/modules/content_governance/domain/rta/forms.py and
 * backend/src/modules/draft/domain/policies.py `guard_field_decision`, so the
 * demo refuses exactly what the API refuses.
 */

const CREATED_AT = "2026-07-22T07:00:00.000Z";

interface FieldSeed {
  id: string;
  section: string;
  critical: boolean;
  required?: boolean;
  lawyerAuthored?: boolean;
  /** Omitted: unresolved with this reason. */
  value?: string;
  unresolved?: UnresolvedReason;
  awaiting?: boolean;
}

function field(slug: string, seed: FieldSeed, order: number): ApiFormField {
  const resolved = seed.value !== undefined;
  return {
    id: `${slug}-field-${seed.id}`,
    fieldId: seed.id,
    labelKey: `rta.form.${slug}.field.${seed.id}.label`,
    sectionKey: `rta.form.${slug}.section.${seed.section}`,
    order,
    critical: seed.critical,
    required: seed.required ?? true,
    displayValue: resolved ? seed.value! : `[[UNRESOLVED: ${seed.id}]]`,
    renderedValue: resolved ? seed.value! : null,
    unresolvedReason: resolved ? null : (seed.unresolved ?? "MISSING_FACT"),
    factId: resolved ? `synthetic-fact-${seed.id}` : null,
    factVersion: resolved ? 1 : null,
    evidenceReferenceIds: [],
    transformationId: resolved ? "EXACT_COPY" : null,
    allowedTransformationIds: ["EXACT_COPY"],
    validationRuleIds: [],
    lawyerAuthoredAllowed: seed.lawyerAuthored ?? false,
    humanConfirmationRequired: seed.critical,
    aiSuggested: Boolean(seed.awaiting),
    awaitingConfirmation: Boolean(seed.awaiting),
    reviewDecisionId: null,
    reviewedBy: null,
    reviewedAt: null,
    conflictingCandidates: [],
  };
}

const PARCEL: FieldSeed[] = [
  { id: "district", section: "parcel", critical: true, value: "Synthetic District" },
  { id: "ds_division", section: "parcel", critical: true, value: "Synthetic DS Division" },
  { id: "gn_division", section: "parcel", critical: true, value: "Synthetic GN 000A", awaiting: true },
];

const FORM_08_FIELDS: FieldSeed[] = [
  ...PARCEL,
  { id: "village", section: "parcel", critical: false, required: false },
  { id: "assessment_number", section: "parcel", critical: false, required: false, value: "SYN-0020" },
  { id: "cadastral_map_no", section: "parcel", critical: true, value: "000000" },
  { id: "block_no", section: "parcel", critical: true, value: "00" },
  { id: "sheet_no", section: "parcel", critical: true, value: "00" },
  { id: "parcel_no", section: "parcel", critical: true, value: "0020" },
  { id: "extent", section: "parcel", critical: true, value: "0.0000 ha (synthetic)" },
  { id: "extent_subject_to_transfer", section: "parcel", critical: true, unresolved: "CRITICAL_FACT_UNCONFIRMED" },
  { id: "place_of_registration", section: "title", critical: true, value: "Synthetic Title Registry" },
  { id: "title_certificate_no", section: "title", critical: true, value: "SYN/TC/0001" },
  { id: "class_of_title", section: "title", critical: true, value: "First class (synthetic)" },
  { id: "transferor_name", section: "transferor", critical: true, value: "Synthetic Transferor One" },
  { id: "transferor_nic", section: "transferor", critical: true, value: "000000000V" },
  { id: "transferor_address", section: "transferor", critical: true, value: "1 Synthetic Road, Sample Town" },
  { id: "transferee_name", section: "transferee", critical: true, value: "Synthetic Transferee Two", awaiting: true },
  { id: "transferee_nic", section: "transferee", critical: true, unresolved: "FACT_UNCONFIRMED" },
  { id: "transferee_address", section: "transferee", critical: true, value: "2 Synthetic Lane, Sample Town" },
  { id: "consideration", section: "consideration", critical: true, value: "1,000,000.00" },
  { id: "consideration_words", section: "consideration", critical: true, unresolved: "FACT_CONFLICTED" },
  { id: "notary_name", section: "attestation", critical: false, value: "Synthetic Notary" },
  { id: "notary_code", section: "attestation", critical: false, unresolved: "MISSING_FACT" },
  { id: "attestation_date", section: "attestation", critical: true, required: false },
];

const FORM_12_FIELDS: FieldSeed[] = [
  ...PARCEL,
  { id: "cadastral_map_no", section: "parcel", critical: true, value: "000000" },
  { id: "block_no", section: "parcel", critical: true, value: "00" },
  { id: "sheet_no", section: "parcel", critical: true, value: "00" },
  { id: "parcel_no", section: "parcel", critical: true, value: "0020" },
  { id: "extent", section: "parcel", critical: true, value: "0.0000 ha (synthetic)" },
  { id: "place_of_registration", section: "title", critical: true, value: "Synthetic Title Registry" },
  { id: "title_certificate_no", section: "title", critical: true, value: "SYN/TC/0001" },
  { id: "class_of_title", section: "title", critical: true, value: "First class (synthetic)" },
  { id: "registered_owner_name", section: "title", critical: true, value: "Synthetic Owner One" },
  { id: "mortgage_reference", section: "prior_mortgage", critical: true, value: "SYN-DB-0001" },
  { id: "mortgage_registration_date", section: "prior_mortgage", critical: true },
  { id: "mortgagee_name", section: "mortgagee", critical: true, value: "Synthetic Bank PLC" },
  { id: "mortgagee_address", section: "mortgagee", critical: true },
  { id: "releasing_party_authority", section: "mortgagee", critical: true, unresolved: "FACT_UNCONFIRMED" },
  { id: "discharge_evidence_kind", section: "discharge", critical: true },
  { id: "discharge_reference", section: "discharge", critical: true },
  { id: "discharge_date", section: "discharge", critical: true },
  {
    id: "cancellation_particulars",
    section: "discharge",
    critical: false,
    required: false,
    lawyerAuthored: true,
  },
  { id: "notary_name", section: "attestation", critical: false, value: "Synthetic Notary" },
  { id: "notary_code", section: "attestation", critical: false },
  { id: "attestation_date", section: "attestation", critical: true, required: false },
];

function preflightFor(form: Omit<ApiGeneratedForm, "preflight">): ApiPreflight {
  const item = (code: string, subjectId: string | null, blocking: boolean): ApiPreflightItem => ({
    code,
    subjectId,
    explanationKey: `rta.form.preflight.${code.toLowerCase()}`,
    gate: blocking ? "APPROVAL" : "REVIEW",
    blocking,
  });
  const blocking: ApiPreflightItem[] = [];
  const warnings: ApiPreflightItem[] = [];
  for (const candidate of form.fields) {
    const unresolved = candidate.renderedValue === null;
    if (unresolved && candidate.required) blocking.push(item("UNRESOLVED_REQUIRED_FIELD", candidate.fieldId, true));
    else if (unresolved) warnings.push(item("UNRESOLVED_OPTIONAL_FIELD", candidate.fieldId, false));
    else if (candidate.awaitingConfirmation) blocking.push(item("FIELD_AWAITING_CONFIRMATION", candidate.fieldId, true));
  }
  blocking.push(item("TEMPLATE_NOT_VALIDATED", null, true));
  return {
    formId: form.id,
    templateId: form.templateId,
    templateVersion: form.templateVersion,
    rulePackVersion: form.rulePackVersion,
    blocking,
    warnings,
    reviewReady: false,
    approvalReady: false,
    registrationReady: false,
    templateRegistrationReadyCapable: false,
    watermarkKey: "rta.form.watermark.draft_not_approved",
    evaluatedAt: CREATED_AT,
  };
}

function build(id: string, formNumber: string, seeds: FieldSeed[]): ApiGeneratedForm {
  const slug = `reg_2022_form_${formNumber}`;
  const fields = seeds.map((seed, index) => field(slug, seed, index + 1));
  const base = {
    id,
    matterId: DEMO_MATTER_ID,
    templateId: `rta.reg.2022.form.${formNumber}`,
    templateVersion: "0.1.0",
    titleKey: `rta.form.${slug}.title`,
    formNumber: String(Number(formNumber)),
    namespace: "REGULATION" as const,
    formVersion: 1,
    state: "UNRESOLVED" as const,
    subtypeId: formNumber === "08" ? "lk.rta.instrument.transfer_sale" : "lk.rta.instrument.mortgage_cancel",
    rulePackVersion: "synthetic",
    draftArtifactHash: null,
    approvedArtifactHash: null,
    approvalId: null,
    staleReason: null,
    knownSourceDefectKeys: [
      "rta.form.defect.english_text_not_lawyer_validated",
      "rta.form.defect.sinhala_tamil_text_not_held",
    ],
    fields,
    createdAt: CREATED_AT,
    updatedAt: CREATED_AT,
    version: 1,
  };
  return { ...base, preflight: preflightFor(base) };
}

export const DEMO_GAZETTE_FORMS: ApiGeneratedForm[] = [
  build("demo-form-08", "08", FORM_08_FIELDS),
  build("demo-form-12", "12", FORM_12_FIELDS),
];

export function demoGazetteForm(id: string): ApiGeneratedForm | undefined {
  const form = DEMO_GAZETTE_FORMS.find((candidate) => candidate.id === id);
  return form ? structuredClone(form) : undefined;
}

/** Refusal codes, named after the API errors they stand in for. */
export type DemoDecisionError =
  | "APPROVED_FORM_IMMUTABLE"
  | "UNKNOWN_FIELD"
  | "FIELD_NOT_POPULATED"
  | "REASON_REQUIRED"
  | "CRITICAL_FIELD_REQUIRES_CONFIRMED_FACT"
  | "LAWYER_AUTHORED_TEXT_NOT_PERMITTED"
  | "FIELD_VALUE_REQUIRED";

export class DemoDecisionRefused extends Error {
  constructor(readonly code: DemoDecisionError) {
    super(code);
  }
}

/** Apply one field decision to a demo form the way the API would. */
export function applyDemoDecision(
  form: ApiGeneratedForm,
  body: { fieldId: string; action: "CONFIRM" | "CORRECT" | "CLEAR"; value?: string; reason?: string },
): ApiGeneratedForm {
  if (form.approvalId !== null) throw new DemoDecisionRefused("APPROVED_FORM_IMMUTABLE");
  const target = form.fields.find((candidate) => candidate.fieldId === body.fieldId);
  if (!target) throw new DemoDecisionRefused("UNKNOWN_FIELD");
  const populated = target.renderedValue !== null;
  let next: ApiFormField;
  if (body.action === "CONFIRM") {
    if (!populated) throw new DemoDecisionRefused("FIELD_NOT_POPULATED");
    next = { ...target, awaitingConfirmation: false, reviewDecisionId: `synthetic-decision-${form.version}` };
  } else {
    if (!(body.reason ?? "").trim()) throw new DemoDecisionRefused("REASON_REQUIRED");
    if (body.action === "CLEAR") {
      next = {
        ...target,
        displayValue: `[[UNRESOLVED: ${target.fieldId}]]`,
        renderedValue: null,
        unresolvedReason: "MISSING_FACT",
        awaitingConfirmation: false,
        reviewDecisionId: `synthetic-decision-${form.version}`,
      };
    } else {
      if (target.critical) throw new DemoDecisionRefused("CRITICAL_FIELD_REQUIRES_CONFIRMED_FACT");
      if (!target.lawyerAuthoredAllowed) throw new DemoDecisionRefused("LAWYER_AUTHORED_TEXT_NOT_PERMITTED");
      const value = (body.value ?? "").trim();
      if (!value) throw new DemoDecisionRefused("FIELD_VALUE_REQUIRED");
      next = {
        ...target,
        displayValue: value,
        renderedValue: value,
        unresolvedReason: null,
        transformationId: "LAWYER_AUTHORED",
        awaitingConfirmation: false,
        reviewDecisionId: `synthetic-decision-${form.version}`,
      };
    }
  }
  const updated = {
    ...form,
    fields: form.fields.map((candidate) => (candidate.fieldId === body.fieldId ? next : candidate)),
    version: form.version + 1,
  };
  return { ...updated, preflight: preflightFor(updated) };
}
