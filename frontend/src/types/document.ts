/**
 * Document ingestion types — RTA workflow §6.1–§6.4, §10.2, §10.3, §12.2.
 *
 * The vocabulary here is the server's, not the UI's. A source file is immutable
 * evidence: its bytes, hash, and filename are never rewritten (§6.2). Only a
 * server-side processing run may move a file to `PROCESSED`; the client shows
 * progress but the server is authoritative (§6.1). There is deliberately no
 * client-side path into `PROCESSED`.
 */

/**
 * The closed vocabularies live in `./rta.ts`, mirrored from the backend enums.
 * They are re-exported here so document-facing modules have one import site and
 * the two files can never drift into two different state machines.
 */
export type {
  BoundaryStatus,
  DocumentClassStatus,
  PhysicalOriginalStatus,
  ProcessingFailureReason,
  SourceFileState,
} from "./rta";

import type {
  BoundaryStatus,
  DocumentClassStatus,
  PhysicalOriginalStatus,
  ProcessingFailureReason,
  SourceFileState,
} from "./rta";

/**
 * Retired M2 vocabulary. Kept only so persisted v3 demo state stays readable
 * during migration (see the store's `migrate`).
 *
 * @deprecated Use {@link SourceFileState}.
 */
export type LegacyProcessingState =
  | "uploaded"
  | "extracting"
  | "ready-for-review"
  | "failed"
  | "replaced";

/**
 * @deprecated Alias retained for legacy call sites. Use {@link SourceFileState}.
 */
export type ProcessingState = SourceFileState;

export type DocumentLanguage = "en" | "si" | "mixed";
export type DocumentKind =
  | "deed"
  | "survey-plan"
  | "identity"
  | "assessment"
  | "registry-extract"
  | "at-form"
  | "other";

export interface QualityProblem {
  code: "blur" | "cropped" | "low-contrast" | "handwriting" | "missing-page";
  pages: number[];
}

export interface DocumentVersion {
  id: string;
  documentId: string;
  fileName: string;
  replacedVersionId?: string;
  replacedBy: string;
  reason: string;
  timestamp: string;
}

/**
 * §12.2 `SourceFile`. Immutable record of received bytes. Nothing in this
 * record is ever edited in place: a corrected or cleaned file is a *new*
 * source file with a `DERIVED_FROM` link (§10.2).
 */
export interface SourceFile {
  id: string;
  matterId: string;
  originalFilename: string;
  mediaType: string;
  byteLength: number;
  sha256: string;
  storageObjectVersion: string;
  uploadActorId: string;
  state: SourceFileState;
  pageCount?: number;
  detectedLanguages: string[];
  retentionClass: string;
  createdAt: string;
  supersededBySourceFileId?: string;
  failureReason?: ProcessingFailureReason;
  /** Recoverable, human-readable explanation key for a failed/unconfigured run. */
  failureExplanationKey?: string;
}

/**
 * §12.2 `DocumentFragment`. A page range inside one source file. Fragments are
 * how one logical document can span several uploads: the bytes are never
 * merged, only related in order (§6.3).
 */
export interface DocumentFragment {
  id: string;
  sourceFileId: string;
  pageStart: number;
  pageEnd: number;
  orderInDocument: number;
  boundaryConfidence: number;
  boundaryStatus: BoundaryStatus;
}

/**
 * §6.3 duplicate/version relationships. Nothing is auto-deleted: a duplicate or
 * superseded document keeps its facts, check results, and audit history.
 */
export type DocumentVersionRelationship =
  | "CURRENT"
  | "POSSIBLE_VERSION"
  | "SUPERSEDED"
  | "EXACT_DUPLICATE";

/**
 * §12.2 `DetectedDocument`. One logical document assembled from one or more
 * fragments. Several documents in one PDF are several `DetectedDocument`s over
 * the same source file; one document split across files is one
 * `DetectedDocument` whose fragments point at different source files.
 */
export interface DetectedDocument {
  id: string;
  matterId: string;
  /** Ordered fragment ids; allows one logical document across several files. */
  fragmentIds: string[];
  classId?: string;
  classConfidence?: number;
  classStatus: DocumentClassStatus;
  languageCodes: string[];
  issuer?: string;
  issueOrExecutionDateFactId?: string;
  versionRelationship?: DocumentVersionRelationship;
  /** The document this one duplicates or supersedes, when known (§6.3). */
  relatedDocumentId?: string;
  version: number;
}

/** How a human confirmed they held the physical original. */
export type PhysicalOriginalInspectionMethod =
  | "IN_PERSON"
  | "SUPERVISED_VIDEO"
  | "REGISTRY_COUNTER";

/**
 * §5.4 / §6.4: `ORIGINAL_INSPECTED` requires reviewer id, timestamp, inspection
 * method/location, and an immutable audit event.
 *
 * No scan, OCR result, or model output may ever set `ORIGINAL_INSPECTED`.
 * Physical-original and authenticity conclusions are human-only events; there
 * is no automated path to this record and there must never be one.
 */
export interface PhysicalOriginalInspection {
  id: string;
  matterId: string;
  checklistItemId: string;
  detectedDocumentId?: string;
  /** The human who physically handled the original. Never a system actor. */
  reviewerId: string;
  inspectedAt: string;
  method: PhysicalOriginalInspectionMethod;
  location: string;
  /** Immutable audit event recorded for this inspection (§5.4). */
  auditEventId: string;
  note?: string;
}

/**
 * The flattened row the M2 screens still render. It is a projection over a
 * source file plus its (currently single) detected document, not a separate
 * authority.
 */
export interface MatterDocument {
  id: string;
  matterId: string;
  fileName: string;
  kind: DocumentKind;
  language: DocumentLanguage;
  pageCount: number;
  /** §10.2 state of the underlying source file. */
  processingState: SourceFileState;
  extractionConfidence?: number;
  qualityProblems: QualityProblem[];
  versions: DocumentVersion[];
  uploadedAt: string;

  /* ── Immutable source-file metadata (§12.2) ───────────────────────────── */
  mediaType?: string;
  byteLength?: number;
  sha256?: string;
  storageObjectVersion?: string;
  uploadActorId?: string;
  retentionClass?: string;
  supersededBySourceFileId?: string;
  failureReason?: ProcessingFailureReason;
  /** Recoverable, human-readable explanation key for a failed/unconfigured run. */
  failureExplanationKey?: string;

  /* ── Detected-document projection (§10.3, §12.2) ──────────────────────── */
  classStatus?: DocumentClassStatus;
  versionRelationship?: DocumentVersionRelationship;
  /** Duplicate/version counterpart, when one was detected (§6.3). */
  relatedDocumentId?: string;
  /** Fragments backing this row; more than one means it spans source files. */
  fragments?: DocumentFragment[];
  /** Set when several detected documents share one source file (§6.3). */
  sourceFileId?: string;
  physicalOriginal?: PhysicalOriginalStatus;
}
