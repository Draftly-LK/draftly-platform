export type ProcessingState = "uploaded" | "extracting" | "ready-for-review" | "failed" | "replaced";
export type DocumentLanguage = "en" | "si" | "mixed";
export type DocumentKind = "deed" | "survey-plan" | "identity" | "assessment" | "registry-extract" | "at-form" | "other";

export interface QualityProblem { code: "blur" | "cropped" | "low-contrast" | "handwriting" | "missing-page"; pages: number[] }

export interface DocumentVersion {
  id: string;
  documentId: string;
  fileName: string;
  replacedVersionId?: string;
  replacedBy: string;
  reason: string;
  timestamp: string;
}

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
}

