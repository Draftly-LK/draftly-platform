export interface EvidenceRegion { x: number; y: number; width: number; height: number }
export interface EvidenceCharRange { start: number; end: number }

export interface EvidenceSpan {
  documentId: string;
  page: number;
  region?: EvidenceRegion;
  charRange?: EvidenceCharRange;
  snippet: string;
}

