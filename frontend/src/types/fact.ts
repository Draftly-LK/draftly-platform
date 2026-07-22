import type { EvidenceSpan } from "./evidence";

export type VerificationState = "unreviewed" | "verified" | "corrected" | "conflict" | "blocked";
export type FactValue = string | number | boolean | null;

export interface FactChange { id: string; before: FactValue; after: FactValue; reason: string; actorId: string; timestamp: string }
export interface FactConflictCandidate { value: FactValue; evidence: EvidenceSpan; confidence: number }

export interface VerifiedFact {
  id: string;
  matterId: string;
  key: string;
  labelKey: string;
  section: string;
  value: FactValue;
  extractedValue: FactValue;
  evidence?: EvidenceSpan;
  confidence: number;
  verificationState: VerificationState;
  reviewerId?: string;
  reviewedAt?: string;
  changes: FactChange[];
  conflicts?: FactConflictCandidate[];
  manualReason?: string;
}

