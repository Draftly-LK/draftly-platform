export type LegalSourceType = "statute" | "amendment";

export interface LegalSourceSummary {
  id: string;
  title: string;
  reference: string;
  type: LegalSourceType;
  weight: "binding" | "unverified-candidate";
  verified: boolean;
  sectionCount: number;
  sourceUrl: string;
  extractionConfidence: string;
  corpusVersion: string;
}
