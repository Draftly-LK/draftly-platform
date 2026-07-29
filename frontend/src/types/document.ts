export type ProcessingState =
  | "uploaded"
  | "extracting"
  | "ready-for-review"
  | "failed"
  | "replaced";
export type DocumentLanguage = "en" | "si" | "mixed";
export type DocumentKind =
  | "deed"
  | "survey-plan"
  | "identity"
  | "assessment"
  | "registry-extract"
  | "at-form"
  | "other";
export type DocumentRelation = "authorized" | "unrelated" | "unclassified";
export type IdentitySide = "front" | "back" | "unknown";

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

export interface IdentityExtractedFields {
  fullName: string;
  idReference: string;
  address: string;
  dateOfBirth: string;
}

export type ExtractedFields = IdentityExtractedFields | Record<string, string>;

export interface MatterDocument {
  id: string;
  matterId: string;
  fileName: string;
  kind: DocumentKind;
  language: DocumentLanguage;
  pageCount: number;
  processingState: ProcessingState;
  extractionConfidence?: number;
  qualityProblems: QualityProblem[];
  versions: DocumentVersion[];
  uploadedAt: string;
  relation: DocumentRelation;
  identitySide?: IdentitySide;
  identityGroupId?: string;
  displayName?: string;
  extractedText?: string;
  extractedFields?: ExtractedFields;
}
