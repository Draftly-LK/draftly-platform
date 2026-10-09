/**
 * RTA matter-workflow vocabulary, mirrored from the backend.
 *
 * Every union in this file is a **closed** vocabulary owned by
 * `backend/src/modules/content_governance/domain/enums.py`. The member strings
 * are the wire values, so a screen can switch on them instead of parsing prose.
 * When the Python enum changes, this file changes with it — nothing here may be
 * widened to `string` and nothing may be invented locally.
 *
 * The taxonomy *data* (families, subtypes, conditional modules) is not written
 * by hand either: it is exported from Python into
 * `src/lib/rta/taxonomy.generated.json` and read through `src/lib/rta/taxonomy.ts`.
 */

/* ── Regime, family, subtype identity (§3.1–§3.4) ───────────────────────── */

/** Registration system that governs the parcel (§3.1). Mirrors `LegalRegime`. */
export type RtaRegimeId =
  | "lk.rta"
  | "lk.deed"
  | "lk.condominium"
  | "lk.special_area";

/** Lawyer-facing grouping shown instead of 22 flat tiles (§3.2). Mirrors `MatterFamily`. */
export type MatterFamilyId =
  | "ownership_change"
  | "agreement_security"
  | "use_interest"
  | "cancel_release"
  | "notice_admin"
  | "parcel_structure"
  | "title_settlement"
  | "dispute_rectification"
  | "controlled_other";

/**
 * A subtype identifier such as `lk.rta.instrument.transfer_sale`.
 *
 * Deliberately not a literal union: the set is data (see
 * `taxonomy.generated.json`), and hardcoding 33 ids here would create a second
 * source of truth that silently drifts from the Python rule pack. Validate with
 * `getSubtype()` from `@/lib/rta/taxonomy`.
 */
export type RtaSubtypeId = string;

/** Prescribed instrument vs statutory process vs registry service (§3.4). Mirrors `SubtypeKind`. */
export type RtaSubtypeKind =
  | "PRESCRIBED_INSTRUMENT"
  | "STATUTORY_PROCESS"
  | "REGISTRY_SERVICE"
  | "CONTROLLED_OTHER";

/** Draftly workflow decision, not terminology used by the Act (§3.3). */
export type ExaminationLevel =
  | "FULL"
  | "FOCUSED"
  | "SPECIAL"
  | "MINIMAL"
  | "TRACKING";

/** How far Draftly automates this subtype today (§3.3, §2.2). */
export type ReleaseTier = "V0" | "V1" | "DEFERRED" | "MANUAL_ONLY";

/* ── Matter state (§10.1, §12.2) ────────────────────────────────────────── */

/**
 * Matter state machine (§10.1). Mirrors `MatterState`.
 *
 * `MANUAL_SUPPORTED` and `LITIGATION_HOLD` are exception states, not terminal
 * failures: evidence and checklist work continue in both.
 */
export type RtaMatterState =
  | "INTAKE_DRAFT"
  | "ROUTED"
  | "EVIDENCE_COLLECTION"
  | "REVIEW_REQUIRED"
  | "LEGAL_REVIEW"
  | "READY_TO_DRAFT"
  | "DRAFTING"
  | "APPROVAL_PENDING"
  | "APPROVED"
  | "EXPORTED"
  | "SUBMITTED"
  | "REGISTERED"
  | "CLOSED"
  | "MANUAL_SUPPORTED"
  | "LITIGATION_HOLD"
  | "CANCELLED";

/** How much of the matter Draftly may automate (§2.3). */
export type AutomationScope =
  | "ASSESSING"
  | "V0_AUTOMATED"
  | "MANUAL_SUPPORTED"
  | "LITIGATION_HOLD";

/**
 * Whether the exact instrument is still provisional (§12.2 `Matter`).
 * A model or a legacy migration may only ever produce `PROVISIONAL`.
 */
export type SubtypeDecisionStatus = "PROVISIONAL" | "LAWYER_CONFIRMED";

/* ── Parcel and party facts set by routing (§4.2) ───────────────────────── */

/** First gate: is the parcel already on an RTA Title Register? (§Executive 1). */
export type TitleStatus = "UNKNOWN" | "INITIAL_COMPILATION" | "RTA_REGISTERED";

/** Ordinary land versus strata (§2.2, ss. 50–52). */
export type ParcelKind =
  | "UNKNOWN"
  | "ORDINARY"
  | "CONDOMINIUM_UNIT"
  | "CONVERSION_TO_CONDOMINIUM";

/** Whole parcel, part, or undivided interest (§4.2 Q03; RTA s. 47). */
export type DispositionScope =
  | "UNKNOWN"
  | "WHOLE_REGISTERED_PARCEL"
  | "PART_OF_PARCEL"
  | "UNDIVIDED_INTEREST";

/** Non-individual party indicators from Q05 (§4.2). */
export type PartyContext =
  | "NATURAL_PERSONS_ONLY"
  | "COMPANY"
  | "ESTATE_OR_DECEASED"
  | "ATTORNEY_POWER_OF_ATTORNEY"
  | "PUBLIC_BODY"
  | "OTHER_NON_INDIVIDUAL";

/* ── Intake questions and answers (§4.1, §4.4) ──────────────────────────── */

/**
 * Answer vocabulary for routing and resolution questions (§4.1).
 *
 * `UNKNOWN` is a valid routing answer and is never coerced into `NO`.
 */
export type TriState = "YES" | "NO" | "UNKNOWN" | "NOT_APPLICABLE";

/** Provenance of an intake answer (§12.2 `IntakeAnswer`). */
export type AnswerStatus =
  | "PROVISIONAL"
  | "INFERRED"
  | "LAWYER_CONFIRMED"
  | "SUPERSEDED";

/** When a question is asked (§4.1). */
export type QuestionStage = "ROUTING" | "RESOLUTION" | "PRE_DRAFT";

/** Shape of an accepted answer value, so the UI can render the right control. */
export type AnswerValueKind =
  | "TRI_STATE"
  | "SINGLE_CHOICE"
  | "MULTI_CHOICE"
  | "TEXT"
  | "DATE"
  | "MONEY"
  | "FILE_UPLOAD";

/* ── Checklist (§5.1, §5.4) ─────────────────────────────────────────────── */

/**
 * Why a checklist requirement is on the list (§5.1). Shown beside every item so
 * a lawyer can tell a statute from an office habit.
 */
export type MandatoryBasis =
  | "LEGAL"
  | "REGULATORY"
  | "OPERATIONAL"
  | "LAWYER_POLICY"
  | "PRODUCT_SAFETY"
  | "LOCAL_AUTHORITY"
  | "CONDITIONAL";

/** UI grouping of checklist items (§11.1). */
export type RequirementGroup =
  | "LEGAL_REGISTRY"
  | "TITLE_EXAMINATION"
  | "CONDITIONAL"
  | "OFFICE_ADDED";

/** §5.4 — does this requirement apply to this matter? */
export type ApplicabilityStatus =
  | "PROVISIONAL_REQUIRED"
  | "REQUIRED"
  | "CONDITIONAL"
  | "NOT_APPLICABLE"
  | "WAIVED_BY_LAWYER";

/** §5.4 — has the evidence arrived? */
export type CollectionStatus =
  | "NOT_REQUESTED"
  | "REQUESTED"
  | "MISSING"
  | "PARTIAL"
  | "RECEIVED";

/**
 * §5.4 — how far has the digital copy been reviewed?
 * `AI_ORGANIZED` is deliberately distinct from `LAWYER_CONFIRMED`.
 */
export type DigitalReviewStatus =
  | "UNREVIEWED"
  | "AI_ORGANIZED"
  | "LAWYER_CONFIRMED"
  | "REJECTED"
  | "SUPERSEDED";

/**
 * §5.4 — physical original custody. `ORIGINAL_INSPECTED` requires a named human
 * reviewer; no scan, OCR result, or model confidence may set it.
 */
export type PhysicalOriginalStatus =
  | "NOT_REQUIRED"
  | "UNKNOWN"
  | "COPY_ONLY"
  | "ORIGINAL_REPORTED"
  | "ORIGINAL_INSPECTED";

/** §5.4 — is the evidence still current enough? */
export type CurrencyStatus =
  | "NOT_APPLICABLE"
  | "UNKNOWN"
  | "CURRENT"
  | "STALE"
  | "EXPIRED";

/** §5.4 — does the evidence agree with the rest of the matter? */
export type ConsistencyStatus =
  | "NOT_CHECKED"
  | "MATCHED"
  | "MISMATCH"
  | "INCONCLUSIVE";

/** §5.4 — the lawyer-facing disposition of the item. */
export type ResolutionStatus =
  | "OPEN"
  | "ACTION_REQUESTED"
  | "SATISFIED"
  | "EXCEPTION_ACCEPTED"
  | "REMEDIATED"
  | "CLOSED";

/** Derived lifecycle for the UI (§10.4). Computed, never stored as truth. */
export type ChecklistItemLifecycle =
  | "NOT_TRIGGERED"
  | "OPEN"
  | "REQUESTED"
  | "MISSING"
  | "PARTIALLY_SATISFIED"
  | "REVIEW_READY"
  | "SATISFIED";

/* ── Evidence ingestion and extraction (§10.2, §10.5, §12.2) ────────────── */

/**
 * §10.2 — ingestion state machine for immutable uploaded bytes. Source bytes
 * never transition to "edited"; a corrected file is a new source.
 */
export type SourceFileState =
  | "UPLOAD_INITIATED"
  | "QUARANTINED"
  | "VALIDATED"
  | "STORED"
  | "PROCESSING"
  | "PROCESSED"
  | "PROCESSING_FAILED"
  | "REJECTED"
  | "SUPERSEDED";

/**
 * Why processing did not produce a result. `NOT_CONFIGURED` is the honest answer
 * when no OCR/classification provider is wired.
 */
export type ProcessingFailureReason =
  | "NOT_CONFIGURED"
  | "PROVIDER_ERROR"
  | "UNSUPPORTED_MEDIA"
  | "PASSWORD_PROTECTED"
  | "PAGE_LIMIT_EXCEEDED"
  | "DATA_PROTECTION_GATE"
  | "TIMEOUT";

/** §12.2 `DocumentFragment` — page-range confidence state. */
export type BoundaryStatus = "CANDIDATE" | "REVIEW_REQUIRED" | "CONFIRMED";

/**
 * §12.2 `DetectedDocument` — classification state. `UNIDENTIFIED` is a
 * first-class result, never silently relabelled `other` (§6.3).
 */
export type DocumentClassStatus =
  | "UNIDENTIFIED"
  | "AI_ORGANIZED"
  | "REVIEW_REQUIRED"
  | "LAWYER_CONFIRMED"
  | "REJECTED";

/**
 * §10.5 — extracted-fact lifecycle. A critical fact reaches `LAWYER_CONFIRMED`
 * only through a human decision, whatever the model confidence.
 */
export type FactStatus =
  | "EXTRACTED_CANDIDATE"
  | "CORROBORATED"
  | "CONFLICTED"
  | "REVIEW_REQUIRED"
  | "LAWYER_CONFIRMED"
  | "LOCKED_FOR_FORM"
  | "SUPERSEDED";

/* ── Checks and issues (§7.1, §7.3, §10.6) ──────────────────────────────── */

/** §7.1 — a "pass" means only that the encoded comparison passed. */
export type CheckOutcome = "PASS" | "FAIL" | "INCONCLUSIVE" | "NOT_RUN";

/** §7.3 — gates on draft generation, approval, and export. */
export type IssueSeverity =
  | "INFORMATION"
  | "WARNING"
  | "HIGH_RISK"
  | "BLOCKING";

/** §7.3 — who, if anyone, may override the blocker. `STATUTORY` nobody may. */
export type BlockerKind =
  | "STATUTORY"
  | "EVIDENCE"
  | "V0_SCOPE"
  | "OFFICE_POLICY"
  | "PROFESSIONAL_JUDGMENT";

/**
 * §10.6 — legal-issue lifecycle. `ACCEPTED_RISK` never changes a failed
 * deterministic check to `PASS`; it records a separate disposition.
 */
export type IssueState =
  | "OPEN"
  | "TRIAGED"
  | "ACTION_REQUIRED"
  | "RESOLVED"
  | "ACCEPTED_RISK"
  | "FALSE_POSITIVE"
  | "OUTSIDE_SCOPE";

/* ── Templates and generated forms (§9.1, §9.5, §10.7) ──────────────────── */

/**
 * §9.1 — a form number alone is never a primary key. `rta.reg.2022.form.31`
 * (register an address) and `rta.ops.tire.31` (apply for a new Title
 * Certificate) are different forms in different namespaces and must never
 * collide.
 */
export type TemplateNamespace =
  | "REGULATION"
  | "OPERATIONAL"
  | "COURT"
  | "TITLE_CERTIFICATE"
  | "TITLE_REGISTER";

/** §9.5 — a transcription is not an approved production rendering. */
export type TemplateStatus = "DRAFT_TRANSCRIPTION" | "VALIDATED" | "SUPERSEDED";

/** §10.7 — generated-form lifecycle. Export changes no legal effect. */
export type GeneratedFormState =
  | "GENERATED_DRAFT"
  | "UNRESOLVED"
  | "REVIEW_READY"
  | "LAWYER_REVIEWED"
  | "APPROVAL_PENDING"
  | "APPROVED"
  | "EXPORTED"
  | "SUBMITTED"
  | "REGISTERED"
  | "STALE_TEMPLATE"
  | "STALE_AFTER_APPROVAL";

/* ── Source authority (§1.1, §13.1) ─────────────────────────────────────── */

/** What kind of authority a requirement or rule rests on (§1.1). */
export type SourceClass =
  | "LAW"
  | "REG"
  | "OPS"
  | "LOCAL_OPS"
  | "PRACTICE"
  | "PRODUCT"
  | "UNVERIFIED";

/* ── Taxonomy contract (shape of taxonomy.generated.json) ───────────────── */

/** A pointer from a taxonomy entry back to the source record that justifies it. */
export interface RtaSourceCitation {
  sourceRecordId: string;
  /** Section, regulation, or form reference inside that source. May be "". */
  locator: string;
  /** Free-text qualifier recorded by the rule-pack author. May be "". */
  note: string;
}

/** One lawyer-facing family of matters (§3.2). */
export interface RtaFamilyDefinition {
  id: MatterFamilyId;
  labelKey: string;
  purposeKey: string;
  /** Display order inside the family picker. 1-based, stable. */
  order: number;
  /**
   * True for the six families that describe a dealing a lawyer initiates.
   * Title settlement, dispute/rectification, and controlled-other are not
   * transactions and are surfaced separately.
   */
  isTransactionFamily: boolean;
}

/** One matter subtype — a prescribed instrument, statutory process, or service (§3.3). */
export interface RtaSubtypeDefinition {
  id: RtaSubtypeId;
  familyId: MatterFamilyId;
  kind: RtaSubtypeKind;
  labelKey: string;
  order: number;
  examinationLevel: ExaminationLevel;
  releaseTier: ReleaseTier;
  /** Why this subtype is outside V0 automation; null when it is inside V0. */
  outOfV0ReasonKey: string | null;
  /** Gazette form number as printed, e.g. "8". Null for processes and services. */
  gazetteFormNumber: string | null;
  /** Namespaced template id, e.g. "rta.reg.2022.form.08". Never the bare number. */
  formTemplateId: string | null;
  /** Additional templates typically filed alongside the primary form. */
  companionTemplateIds: string[];
  /** Checklist modules included for every matter of this subtype. */
  defaultModuleDefinitionIds: string[];
  /** True only for `CONTROLLED_OTHER`, which must not be chosen silently. */
  requiresDeclaredLegalBasis: boolean;
  sources: RtaSourceCitation[];
}

/** A checklist module activated by a routing answer rather than by subtype (§5.2). */
export interface RtaConditionalModuleDefinition {
  id: string;
  labelKey: string;
  /** Never empty — a module that adds no checklist modules would be a no-op. */
  checklistModuleIds: string[];
  /** True when activating this module takes the matter out of V0 automation. */
  excludesV0: boolean;
}

/** The whole generated taxonomy document. */
export interface RtaTaxonomyContract {
  regimeId: RtaRegimeId;
  versions: Record<string, string>;
  families: RtaFamilyDefinition[];
  subtypes: RtaSubtypeDefinition[];
  conditionalModules: RtaConditionalModuleDefinition[];
  /** §3.6 — retired M2 matter type → subtype id. Every value is provisional. */
  legacyMatterTypeMap: Record<string, RtaSubtypeId>;
}

/* ── Matter API wire types ──────────────────────────────────────────────── */
/* Mirrors backend/src/modules/matter/api/schemas.py. Responses are camelCase
   because the Pydantic models use a `to_camel` alias generator. Fields typed as
   plain enums there are widened to their TS unions here only where the backend
   guarantees the value comes from the closed enum. */

/** Mirrors `MatterRead`. */
export interface ApiRtaMatter {
  id: string;
  reference: string;
  clientReference: string | null;
  responsibleLawyerId: string;
  regimeId: RtaRegimeId;
  familyId: MatterFamilyId | null;
  subtypeId: RtaSubtypeId | null;
  subtypeDecisionStatus: SubtypeDecisionStatus;
  legacyMatterType: string | null;
  lifecycleStatus: string;
  state: RtaMatterState;
  automationScope: AutomationScope;
  titleStatus: TitleStatus;
  parcelKind: ParcelKind;
  dispositionScope: DispositionScope;
  /** §8.3 `DisputeStage`; kept as a string because no screen switches on it yet. */
  disputeStage: string;
  instrumentLanguage: string;
  localAuthorityId: string | null;
  activeChecklistSnapshotId: string | null;
  partyContexts: PartyContext[];
  activatedConditionalModuleIds: string[];
  automationExclusionReasonKeys: string[];
  createdAt: string;
  updatedAt: string;
  version: number;
}

/** Mirrors `PageInfo`. */
export interface ApiPageInfo {
  nextCursor: string | null;
  hasMore: boolean;
  limit: number;
}

/** Canonical register wire contract; values and immutable lineage are form-free. */
export type ApiFactValue = string | number | boolean | null;
export interface ApiFactEvidenceInput {
  interpretationGeneration?: number | null;
  sourceFileId: string;
  pageNumber: number;
  sourceSha256: string;
  extractionRunId?: string | null;
  detectedDocumentId?: string | null;
  candidateId?: string | null;
  candidateVersion?: number | null;
  snippet?: string;
}
export interface ApiFactEvidence {
  interpretationGeneration?: number | null;
  id: string;
  sourceFileId: string;
  detectedDocumentId: string | null;
  pageNumber: number;
  sourceSha256: string;
  extractionRunId: string | null;
  supportingText: string | null;
  pageText: string | null;
  precision: "page" | "text";
  candidateId: string | null;
  candidateVersion: number | null;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
    coordinateSpace: string;
  } | null;
}
export interface ApiMatterFact {
  id: string;
  matterId: string;
  factTypeId: string;
  fieldKey: string | null;
  labelKey: string;
  value: ApiFactValue;
  originalValue: ApiFactValue;
  status:
    | "EXTRACTED_CANDIDATE"
    | "CORROBORATED"
    | "CONFLICTED"
    | "REVIEW_REQUIRED"
    | "LAWYER_CONFIRMED"
    | "LOCKED_FOR_FORM"
    | "REJECTED"
    | "SUPERSEDED";
  origin: "legacy" | "machine" | "lawyer";
  modelReportedConfidence: number | null;
  evidence: ApiFactEvidence[];
  reviewedBy: string | null;
  reviewedAt: string | null;
  version: number;
  createdAt: string;
  transactionId: string | null;
  subjectId: string | null;
  scopeStatus: "legacy-unassigned" | "unassigned" | "assigned";
  evidenceStale: boolean;
  sourceCandidateId: string | null;
  manualReason: string | null;
  lineageId: string | null;
  supersedesFactId: string | null;
  supersededByFactId: string | null;
  scopeToken: string | null;
  conflictFactIds: string[];
}
export interface ApiFactDecision {
  id: string;
  targetId: string;
  decision: string;
  reviewerId: string;
  reviewerRole: string;
  createdAt: string;
  previousValue: ApiFactValue;
  newValue: ApiFactValue;
  reason: string | null;
  resolvedFactIds: string[];
}
export interface ApiFactHistory {
  items: ApiMatterFact[];
  decisions: ApiFactDecision[];
  page: ApiPageInfo;
}
export type TransactionRole =
  | "transferor"
  | "transferee"
  | "owner"
  | "donor"
  | "donee"
  | "lessor"
  | "lessee"
  | "mortgagor"
  | "mortgagee"
  | "other";
export interface ApiMatterSubject {
  id: string;
  userId: string;
  matterId: string;
  kind: "party" | "parcel";
  ordinal: number;
}
export interface ApiMatterTransaction {
  id: string;
  userId: string;
  matterId: string;
  ordinal: number;
  version: number;
  parcelSubjectIds: string[];
  partyRoles: { subjectId: string; role: TransactionRole }[];
}
export interface ApiFactType {
  id: string;
  fieldKey: string | null;
  labelKey: string;
  subject:
    | "MATTER"
    | "REGIME"
    | "TITLE"
    | "PARCEL"
    | "PARTY"
    | "INSTRUMENT"
    | "INTEREST"
    | "ORGANIZATION"
    | "PROCESS";
  valueKind:
    | "TEXT"
    | "IDENTIFIER"
    | "ENUM"
    | "DATE"
    | "MONEY"
    | "AREA"
    | "BOOLEAN"
    | "COUNT";
  critical: boolean;
  negativeRequiresSearchEvidence: boolean;
  options: { value: string; labelKey: string }[];
}
export interface ApiFactTypes {
  versions: Record<string, string>;
  factTypes: ApiFactType[];
}

/** Mirrors `MatterListRead`. */
export interface ApiRtaMatterList {
  items: ApiRtaMatter[];
  page: ApiPageInfo;
}

/** Mirrors `IntakeAnswerRead`. */
export interface ApiIntakeAnswer {
  id: string;
  questionDefinitionId: string;
  /** Shape depends on the question's `AnswerValueKind`; unknown forces a narrowing. */
  value: unknown;
  status: AnswerStatus;
  answeredBy: string | null;
  answerReason: string | null;
  supersedesId: string | null;
  inferredFromFactIds: string[];
  createdAt: string;
}

/** Mirrors `GateRead` — one evaluated eligibility predicate or stop condition. */
export interface ApiGate {
  id: string;
  satisfied: boolean;
  severity: IssueSeverity;
  blockerKind: BlockerKind;
  reasonKey: string;
  sourceRecordIds: string[];
  isV0Predicate: boolean;
}

/** Mirrors `RoutingRead`. */
export interface ApiRouting {
  matter: ApiRtaMatter;
  automationScope: AutomationScope;
  gates: ApiGate[];
  unmetGateIds: string[];
  statutoryBlockerIds: string[];
  nextQuestionIds: string[];
  activatedConditionalModuleIds: string[];
}

/** Mirrors `ChecklistItemRead`. */
export interface ApiChecklistItem {
  requirementDefinitionId: string;
  moduleDefinitionId: string;
  inclusionReason: string;
  inclusionTriggerId: string | null;
  labelKey: string;
  explanationKey: string;
  mandatoryBasis: MandatoryBasis;
  group: RequirementGroup;
  applicability: ApplicabilityStatus;
  sourceRecordIds: string[];
  acceptedDocumentClassIds: string[];
  mayBeSatisfiedByCombinedDocument: boolean;
  physicalOriginalPolicy: PhysicalOriginalStatus;
  currencyMaxAgeDays: number | null;
  unsatisfiedSeverity: IssueSeverity;
  unsatisfiedBlockerKind: BlockerKind;
  waivable: boolean;
  localAuthorityId: string | null;
}

/**
 * Mirrors `ChecklistItemRead` — the *live* checklist item, as opposed to
 * `ApiChecklistItem`, which is the compiled snapshot the intake shows.
 *
 * Carries the seven orthogonal statuses of §5.4 plus the two derived fields
 * (§10.4). `lifecycle` and `computedResolution` are computed for display and
 * are never stored as truth, so nothing may write them back.
 */
export interface ApiChecklistItemState {
  id: string;
  requirementDefinitionId: string;
  moduleDefinitionId: string;
  inclusionReason: string;
  inclusionTriggerId: string | null;
  labelKey: string;
  explanationKey: string;
  mandatoryBasis: MandatoryBasis;
  group: RequirementGroup;
  sourceRecordIds: string[];
  acceptedDocumentClassIds: string[];
  mayBeSatisfiedByCombinedDocument: boolean;
  physicalOriginalPolicy: PhysicalOriginalStatus;
  waivable: boolean;
  localAuthorityId: string | null;
  applicability: ApplicabilityStatus;
  collection: CollectionStatus;
  digitalReview: DigitalReviewStatus;
  physicalOriginal: PhysicalOriginalStatus;
  currency: CurrencyStatus;
  consistency: string;
  resolution: ResolutionStatus;
  lifecycle: ChecklistItemLifecycle;
  computedResolution: ResolutionStatus;
}

/** Mirrors `ChecklistRead` — the active checklist for a matter. */
export interface ApiChecklist {
  snapshotId: string;
  matterId: string;
  fingerprint: string;
  rulePackVersion: string;
  compilerVersion: string;
  taxonomyVersion: string;
  checklistVersion: string;
  moduleDefinitionIds: string[];
  supersedesId: string | null;
  createdAt: string;
  items: ApiChecklistItemState[];
  blockingRequirementIds: string[];
}

/** Mirrors `ChecklistDeltaRead`. */
export interface ApiChecklistDelta {
  added: string[];
  removed: string[];
  changed: Record<string, string>[];
  retainedAfterReview: string[];
}

/** Mirrors `ChecklistSnapshotRead`. */
export interface ApiChecklistSnapshot {
  snapshotId: string;
  matterId: string;
  fingerprint: string;
  rulePackVersions: Record<string, string>;
  moduleDefinitionIds: string[];
  items: ApiChecklistItem[];
  delta: ApiChecklistDelta | null;
}

/* ── Document ingestion API wire types ──────────────────────────────────── */
/* Mirrors backend/src/modules/document/api/schemas.py. */

/** Mirrors `SourceFileRead`. `storageObjectKey` is never exposed. */
export interface ApiSourceFile {
  id: string;
  matterId: string;
  originalFilename: string;
  mediaType: string;
  byteLength: number;
  sha256: string;
  storageObjectVersion: string;
  uploadActorId: string;
  state: SourceFileState;
  pageCount: number | null;
  detectedLanguages: string[];
  retentionClass: string;
  failureReason: ProcessingFailureReason | null;
  failureExplanationKey: string | null;
  supersededBySourceFileId: string | null;
  derivedFromSourceFileId: string | null;
  duplicateOfSourceFileId: string | null;
  versionRelationship: string | null;
  detectedDocumentIds: string[];
  containsMultipleDocuments: boolean;
  createdAt: string;
  updatedAt: string;
  version: number;
}

/** Mirrors `SourceFileListRead`. */
export interface ApiSourceFileList {
  items: ApiSourceFile[];
  page: ApiPageInfo;
}

/** Latest persisted attempt, without candidate values or storage paths. */
export interface ApiLatestProcessingRun {
  jobId: string;
  state: "succeeded" | "failed";
  outcome: SourceFileState;
  provider: string;
  reasons: string[];
  failureReason: ProcessingFailureReason | null;
  failureExplanationKey: string | null;
  pagesProcessed: number;
  aiExtractionCalls: number;
  startedAt: string;
  finishedAt: string | null;
  pageOutcomes: Array<{
    pageNo: number;
    qualityStatus: "normal" | "likely_blank" | "ocr_sparse" | "ocr_failed";
    rotationStatus: "not_required" | "applied" | "rotation_uncertain";
  }>;
  manualReviewRequired: boolean;
}

export interface ApiSourceProcessingStatus {
  sourceFile: ApiSourceFile;
  latestRun: ApiLatestProcessingRun | null;
}

/** Mirrors `DocumentFragmentRead`. */
export interface ApiDocumentFragment {
  id: string;
  sourceFileId: string;
  pageStart: number;
  pageEnd: number;
  orderInDocument: number;
  /** Null when a human drew the range — a decision is not a model score. */
  boundaryConfidence: number | null;
  boundaryStatus: BoundaryStatus;
}

/** Mirrors `DetectedDocumentRead`. */
export interface ApiDetectedDocument {
  interpretationGeneration?: number;
  extractionState?:
    | "current"
    | "refresh_required"
    | "failed"
    | "unsupported"
    | "unavailable";
  latestRefreshRunId?: string | null;
  refreshFailureReason?: string | null;
  id: string;
  matterId: string;
  classId: string | null;
  classConfidence: number | null;
  classStatus: DocumentClassStatus;
  boundaryStatus: BoundaryStatus;
  languageCodes: string[];
  issuer: string | null;
  issueOrExecutionDateFactId: string | null;
  versionRelationship: string | null;
  duplicateOfDetectedDocumentId: string | null;
  fragments: ApiDocumentFragment[];
  sourceFileIds: string[];
  spansMultipleSources: boolean;
  createdAt: string;
  updatedAt: string;
  version: number;
}

/** Mirrors `DocumentInboxRead`. */
export interface ApiDocumentInbox {
  matterId: string;
  sourceFiles: ApiSourceFile[];
  documents: ApiDetectedDocument[];
  boundaryReviewDocumentIds: string[];
  classificationReviewDocumentIds: string[];
  unidentifiedDocumentIds: string[];
  /** Stored, processing, or failed — never quietly counted as done. */
  unprocessedSourceFileIds: string[];
  page: ApiPageInfo;
  pageAccounting?: ApiPageAccounting[];
}

export interface ApiPageAccounting {
  sourceFileId: string;
  pageCount: number | null;
  unclaimedPageNumbers: number[];
  overlappingPageNumbers: number[];
  outOfBoundsPageNumbers?: number[];
  blankPageNumbers: number[];
  unsupportedPageNumbers: number[];
  complete: boolean;
  manualReviewRequired: boolean;
}

export interface ApiInterpretationHistory {
  documentId: string;
  matterId: string;
  currentGeneration: number;
  snapshots: { generation: number; classId: string | null; fragments: { sourceFileId: string; pageStart: number; pageEnd: number; orderInDocument?: number }[]; actorId: string | null; createdAt: string }[];
  refreshRuns: { id: string; generation: number; outcome: string; reasons: string[]; startedAt: string; finishedAt: string | null }[];
}

/** Mirrors `PageCandidateRead`. Nothing here is verified. */
export interface ApiPageCandidate {
  key: string;
  value: string | null;
  pageNo: number;
  sourceFileId: string;
  detectedDocumentId: string | null;
  provider: string;
  modelReportedConfidence: number;
  formatValid: boolean | null;
}

/** Mirrors `ProcessingRunRead`. `state` is already terminal on return. */
export interface ApiProcessingRun {
  jobId: string;
  state: "succeeded" | "failed";
  pollAfterMs: number | null;
  sourceFileId: string;
  provider: string;
  outcome: string;
  reasons: string[];
  failureReason: ProcessingFailureReason | null;
  failureExplanationKey: string | null;
  pagesProcessed: number;
  aiExtractionCalls: number;
  startedAt: string;
  finishedAt: string | null;
  correlationId: string;
  sourceFile: ApiSourceFile;
  detectedDocuments: ApiDetectedDocument[];
  candidateFields: ApiPageCandidate[];
  candidatesWithheld: boolean;
}

export interface ApiDocumentReviewPage {
  sourceFileId?: string | null;
  id: string;
  pageNo: number;
  correctedWidth: number;
  correctedHeight: number;
  qualityStatus: "normal" | "likely_blank" | "ocr_sparse" | "ocr_failed";
  rotationStatus: "not_required" | "applied" | "rotation_uncertain";
  classificationTypeId: string;
  classificationConfidence: number;
  imageUrl: string;
  ocrUrl: string;
}

export interface ApiReviewCandidate {
  id: string;
  key: string;
  candidateValue: string;
  editedValue: string | null;
  pageNo: number;
  modelReportedConfidence: number;
  reviewState: "unverified" | "approved";
  version: number;
}

export interface ApiDocumentReview {
  interpretationGeneration?: number;
  current?: boolean;
  id: string;
  matterId: string;
  detectedDocumentId: string;
  typeId: string;
  suggestedName: string | null;
  pages: ApiDocumentReviewPage[];
  candidates: ApiReviewCandidate[];
}

/* ── Check and legal-issue API wire types ───────────────────────────────── */
/* Mirrors backend/src/modules/check/api/schemas.py. */

/** Mirrors `FactVersionPinRead`. */
export interface ApiFactVersionPin {
  factId: string;
  version: number;
}

/** Mirrors `CheckResultRead`. */
export interface ApiCheckResult {
  id: string;
  checkDefinitionId: string;
  checkDefinitionVersion: string;
  runId: string;
  outcome: CheckOutcome;
  defaultSeverity: IssueSeverity;
  explanationKey: string;
  safetyRuleKey: string | null;
  labelKey: string | null;
  comparisonKey: string | null;
  sourceRecordIds: string[];
  failureBlockerKind: BlockerKind | null;
  inputFactVersions: ApiFactVersionPin[];
  evidenceReferenceIds: string[];
  requiresHumanConclusion: boolean;
  /** True when the conclusion rests on a rule this repository cannot verify. */
  provisional: boolean;
  createdAt: string;
}

/** Mirrors `LegalIssueRead`. */
export interface ApiLegalIssue {
  id: string;
  matterId: string;
  checkId: string | null;
  issueTypeId: string;
  severity: IssueSeverity;
  blockerKind: BlockerKind;
  state: IssueState;
  summaryKey: string;
  sourceRecordIds: string[];
  evidenceReferenceIds: string[];
  assignedTo: string | null;
  resolutionDecisionId: string | null;
  resolutionReason: string | null;
  /** The dispositions this issue's blocker kind can legitimately reach. */
  permittedStates: IssueState[];
  createdAt: string;
  updatedAt: string;
  version: number;
}

/** Mirrors `IssueGatesRead`. */
export interface ApiIssueGates {
  blocksDraftGeneration: boolean;
  blocksApproval: boolean;
  blocksRegistrationReadyExport: boolean;
  openStatutoryBlockerIds: string[];
  openBlockingIssueIds: string[];
}

/** Mirrors `CheckRunRead`. */
export interface ApiCheckRun {
  runId: string;
  results: ApiCheckResult[];
  raisedIssues: ApiLegalIssue[];
  gates: ApiIssueGates;
}

/** Mirrors `CheckResultListRead`. */
export interface ApiCheckResultList {
  items: ApiCheckResult[];
  page: ApiPageInfo;
}

/** Mirrors `LegalIssueListRead`. Gates are computed over every issue, not the page. */
export interface ApiLegalIssueList {
  items: ApiLegalIssue[];
  page: ApiPageInfo;
  gates: ApiIssueGates;
}

/* ── Drafting API wire types ─────────────────────────────────────────────── */
/* Mirrors backend/src/modules/draft/api/schemas.py. */

/** Mirrors `FactCandidateRead`. */
export interface ApiFactCandidate {
  factId: string;
  factTypeId: string;
  value: unknown;
  version: number;
  status: FactStatus;
  evidenceReferenceIds: string[];
  modelReportedConfidence: number | null;
}

/**
 * Why a field renders its unresolved token instead of a value (§9.4). Mirrors
 * `UnresolvedReason` in backend/src/modules/content_governance/domain/enums.py;
 * every value needs a `gazette.unresolvedReason.*` message.
 */
export type UnresolvedReason =
  | "NO_FACT"
  | "FACT_NOT_CONFIRMED"
  | "FACT_CONFLICTED"
  | "FACT_SUPERSEDED"
  | "BLOCKED_BY_ISSUE";

/** Mirrors `FormFieldRead`. */
export interface ApiFormField {
  id: string;
  fieldId: string;
  labelKey: string;
  sectionKey: string;
  order: number;
  critical: boolean;
  required: boolean;
  /** The value, or the §9.4 `[[UNRESOLVED: <field_id>]]` token. Never `""`. */
  displayValue: string;
  renderedValue: string | null;
  unresolvedReason: string | null;
  factId: string | null;
  factVersion: number | null;
  evidenceReferenceIds: string[];
  transformationId: string | null;
  allowedTransformationIds: string[];
  validationRuleIds: string[];
  lawyerAuthoredAllowed: boolean;
  humanConfirmationRequired: boolean;
  aiSuggested: boolean;
  awaitingConfirmation: boolean;
  reviewDecisionId: string | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  conflictingCandidates: ApiFactCandidate[];
}

/** Mirrors `PreflightItemRead`. */
export interface ApiPreflightItem {
  code: string;
  subjectId: string | null;
  explanationKey: string;
  gate: string;
  blocking: boolean;
}

/** Mirrors `PreflightRead`. `registrationReady` is false for every template today (§9.5). */
export interface ApiPreflight {
  formId: string;
  templateId: string;
  templateVersion: string;
  rulePackVersion: string;
  blocking: ApiPreflightItem[];
  warnings: ApiPreflightItem[];
  reviewReady: boolean;
  approvalReady: boolean;
  registrationReady: boolean;
  templateRegistrationReadyCapable: boolean;
  watermarkKey: string | null;
  evaluatedAt: string;
}

/** Mirrors `GeneratedFormRead`. */
export interface ApiGeneratedForm {
  id: string;
  matterId: string;
  templateId: string;
  templateVersion: string;
  titleKey: string;
  formNumber: string;
  namespace: TemplateNamespace;
  formVersion: number;
  state: GeneratedFormState;
  subtypeId: string;
  rulePackVersion: string;
  draftArtifactHash: string | null;
  approvedArtifactHash: string | null;
  approvalId: string | null;
  staleReason: string | null;
  /** §9.5 — the recorded defects of the source text travel with the draft. */
  knownSourceDefectKeys: string[];
  fields: ApiFormField[];
  preflight: ApiPreflight;
  createdAt: string;
  updatedAt: string;
  version: number;
}

/** Mirrors `GeneratedFormSummaryRead`. */
export interface ApiGeneratedFormSummary {
  id: string;
  matterId: string;
  templateId: string;
  templateVersion: string;
  formVersion: number;
  state: GeneratedFormState;
  subtypeId: string;
  rulePackVersion: string;
  draftArtifactHash: string | null;
  approvedArtifactHash: string | null;
  approvalId: string | null;
  staleReason: string | null;
  createdAt: string;
  updatedAt: string;
  version: number;
}

/** Mirrors `GeneratedFormListRead`. */
export interface ApiGeneratedFormList {
  items: ApiGeneratedFormSummary[];
  page: ApiPageInfo;
}

/* ── Approval, export, and registration API wire types ──────────────────── */
/* Mirrors backend/src/modules/approval/api/schemas.py. No route in this module
   takes If-Match: an approval, an export, and a registration event are all
   immutable records with no version to condition on (§9.6). */

/** Mirrors `ApprovalGateItemRead`. */
export interface ApiApprovalGateItem {
  id: string;
  code: string;
  subjectId: string | null;
  explanationKey: string;
  blocking: boolean;
}

/** Mirrors `ApprovalGateRead`. */
export interface ApiApprovalGate {
  formId: string;
  templateId: string;
  templateVersion: string;
  rulePackVersion: string;
  blocking: ApiApprovalGateItem[];
  warnings: ApiApprovalGateItem[];
  approvalReady: boolean;
  registrationReady: boolean;
  templateRegistrationReadyCapable: boolean;
}

/** Mirrors `ApprovalRead`. One immutable §9.6 signed application event. */
export interface ApiApproval {
  id: string;
  matterId: string;
  targetType: string;
  targetId: string;
  targetVersion: string;
  approverId: string;
  approverWorkflowRole: string;
  declarationVersion: string;
  declarationTextHash: string;
  snapshotHash: string;
  confirmedFactHash: string;
  warningDispositionIds: string[];
  templateId: string;
  templateVersion: string;
  rulePackVersion: string;
  revokedByApprovalId: string | null;
  createdAt: string;
}

/** Mirrors `ApprovalCreatedRead`. */
export interface ApiApprovalCreated {
  approval: ApiApproval;
  gate: ApiApprovalGate;
}

/** Mirrors `ApprovalListRead`. */
export interface ApiApprovalList {
  items: ApiApproval[];
  page: ApiPageInfo;
  gate: ApiApprovalGate;
  currentApprovalId: string | null;
}

/** What this module can actually produce. Each member names a record, not a document. */
export type ExportFormat =
  | "WORKING_DRAFT_MANIFEST"
  | "APPROVED_MANIFEST"
  | "EVIDENCE_SCHEDULE";

/** Mirrors `FormExportRead`. `registrationReady` is false in every case (§9.5). */
export interface ApiFormExport {
  id: string;
  matterId: string;
  generatedFormId: string;
  approvalId: string | null;
  artifactKind: ExportFormat;
  artifactHash: string;
  artifactKey: string;
  watermarked: boolean;
  watermarkKey: string | null;
  registrationReady: boolean;
  registrationReadyBlockedBy: string[];
  manifest: Record<string, unknown>;
  createdBy: string;
  createdAt: string;
}

/** Mirrors `FormExportListRead`. */
export interface ApiFormExportList {
  items: ApiFormExport[];
  page: ApiPageInfo;
}

/** Attestation, presentation, or a registry result — three separate events (§9.6). */
export type RegistrationEventType =
  | "ATTESTED"
  | "PRESENTED"
  | "DAY_BOOK_ENTERED"
  | "REGISTERED"
  | "REFUSED"
  | "RETURNED";

/** Mirrors `RegistrationEventRead`. */
export interface ApiRegistrationEvent {
  id: string;
  matterId: string;
  generatedFormId: string | null;
  eventType: RegistrationEventType;
  eventDate: string;
  evidenceReferenceIds: string[];
  dayBookReference: string | null;
  registryOffice: string | null;
  resultNote: string | null;
  recordedBy: string;
  createdAt: string;
}

/** Mirrors `PresentationDeadlineRead`. The s. 45(1) seven-working-day clock. */
export interface ApiPresentationDeadline {
  attestedOn: string;
  dueOn: string;
  workingDays: number;
  basisKey: string;
  /** True while the public-holiday calendar behind this date is unverified (§16.4). */
  provisional: boolean;
  unverifiedReasonKey: string | null;
}

/** Mirrors `RegistrationEventCreatedRead`. */
export interface ApiRegistrationEventCreated {
  event: ApiRegistrationEvent;
  impliedMatterState: RtaMatterState | null;
  deadline: ApiPresentationDeadline | null;
}

/** Mirrors `RegistrationEventListRead`. */
export interface ApiRegistrationEventList {
  items: ApiRegistrationEvent[];
  page: ApiPageInfo;
}
