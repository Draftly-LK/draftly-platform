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
export type RtaRegimeId = "lk.rta" | "lk.deed" | "lk.condominium" | "lk.special_area";

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
export type ExaminationLevel = "FULL" | "FOCUSED" | "SPECIAL" | "MINIMAL" | "TRACKING";

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
export type AutomationScope = "ASSESSING" | "V0_AUTOMATED" | "MANUAL_SUPPORTED" | "LITIGATION_HOLD";

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
export type AnswerStatus = "PROVISIONAL" | "INFERRED" | "LAWYER_CONFIRMED" | "SUPERSEDED";

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
export type CollectionStatus = "NOT_REQUESTED" | "REQUESTED" | "MISSING" | "PARTIAL" | "RECEIVED";

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
export type CurrencyStatus = "NOT_APPLICABLE" | "UNKNOWN" | "CURRENT" | "STALE" | "EXPIRED";

/** §5.4 — does the evidence agree with the rest of the matter? */
export type ConsistencyStatus = "NOT_CHECKED" | "MATCHED" | "MISMATCH" | "INCONCLUSIVE";

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
export type IssueSeverity = "INFORMATION" | "WARNING" | "HIGH_RISK" | "BLOCKING";

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
