/** Case law is a separate contract from statutory sources and assistant answers. */
export interface CaseCoverage {
  catalogueRecords: number;
  retrievalRecords: number;
  readerOverlapRecords: number;
  collections: Record<string, number>;
  minYear: number | null;
  maxYear: number | null;
  retrievalScope: "conveyancing-only";
}
export interface CaseRecord {
  id: string;
  title: string;
  citation: string;
  collection: "LKCA" | "LKSC";
  decidingCourt: string | null;
  year: number;
  decisionDate: string | null;
  reportSeries: string | null;
  sourceUrl: string;
  provenance: "commonlii-parsed";
  verificationState: "parsed-unverified";
  qualityWarnings: Array<
    | "encoding-errors"
    | "missing-pages"
    | "malformed-tags"
    | "deciding-court-unparsed"
  >;
  displayPolicy: "metadata-only" | "full-text";
  textSha256: string;
  text: string | null;
  displayApprovalReference: string | null;
}
export interface CasePage {
  corpusVersion: string;
  coverage: CaseCoverage;
  items: CaseRecord[];
  page: { nextCursor: string | null; hasMore: boolean; limit: number };
}
export interface CaseDetail {
  corpusVersion: string;
  coverage: CaseCoverage;
  item: CaseRecord;
}
export interface SimilarCase {
  case: CaseRecord | null;
  id: string;
  title: string;
  citation: string;
  sourceUrl: string;
  score: number;
  matchedSignals: Array<"lexical" | "graph" | "dense">;
  readerAvailable: boolean;
  excerpt: string;
}
export interface CaseSearch {
  corpusVersion: string;
  coverage: CaseCoverage;
  items: SimilarCase[];
  outcome: "similar_cases_found" | "no_similar_cases";
  degradedChannels: Array<"dense">;
  denseStatus: "disabled" | "unavailable" | "enabled-status-unknown";
}
