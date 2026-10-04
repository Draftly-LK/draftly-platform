/** Synthetic records only. Shared by interaction tests and the UI review harness. */
export const caseCoverage = {
  catalogueRecords: 3,
  retrievalRecords: 2,
  readerOverlapRecords: 1,
  collections: { LKCA: 2, LKSC: 1 },
  minYear: 1990,
  maxYear: 2000,
  retrievalScope: "conveyancing-only" as const,
};
export const syntheticCase = {
  id: "commonlii-SYNTHETIC-1",
  title: "Synthetic Boundary v Synthetic Title",
  citation: "[1999] Synthetic 1",
  collection: "LKCA" as const,
  decidingCourt: "Synthetic District Court",
  year: 1999,
  decisionDate: "1999-01-02",
  reportSeries: "Synthetic Reports",
  sourceUrl: "https://example.test/synthetic-case",
  provenance: "commonlii-parsed" as const,
  verificationState: "parsed-unverified" as const,
  qualityWarnings: ["encoding-errors", "deciding-court-unparsed"] as (
    | "encoding-errors"
    | "deciding-court-unparsed"
  )[],
  displayPolicy: "metadata-only" as "metadata-only" | "full-text",
  textSha256: "a".repeat(64),
  text: null as string | null,
  displayApprovalReference: null as string | null,
};
export const casePage = {
  corpusVersion: "synthetic-v1",
  coverage: caseCoverage,
  items: [syntheticCase],
  page: { nextCursor: "signed-page-2", hasMore: true, limit: 25 },
};
export const similarCases = {
  corpusVersion: "synthetic-v1",
  coverage: caseCoverage,
  items: [
    {
      case: syntheticCase,
      id: syntheticCase.id,
      title: syntheticCase.title,
      citation: syntheticCase.citation,
      sourceUrl: syntheticCase.sourceUrl,
      score: 0.2,
      matchedSignals: ["lexical", "graph"] as ("lexical" | "graph" | "dense")[],
      readerAvailable: true,
      excerpt: "Synthetic evidence excerpt.\nPreserved second line.",
    },
  ],
  outcome: "similar_cases_found" as "similar_cases_found" | "no_similar_cases",
  degradedChannels: ["dense"] as "dense"[],
  denseStatus: "disabled" as const,
};
