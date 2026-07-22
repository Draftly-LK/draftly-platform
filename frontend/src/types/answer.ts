import type { EvidenceSpan } from "./evidence";

export type AuthorityType = "statute" | "amendment" | "gazette" | "case-rule" | "practice-direction";
export type CourtLevel = "supreme-court" | "court-of-appeal" | "high-court" | "district-court" | "not-applicable";
export type AuthorityWeight = "binding" | "persuasive" | "historical" | "unverified-candidate";

export interface Authority { id: string; title: string; reference: string; type: AuthorityType; courtLevel: CourtLevel; weight: AuthorityWeight; verified: boolean }
export interface Citation { id: string; authority: Authority; evidence: EvidenceSpan }
export interface Claim { id: string; text: string; citations: Citation[] }
export type AssistantScopeType = "matter" | "step" | "document" | "library";
export interface AssistantScope { type: AssistantScopeType; targetId?: string; labelKey: string }

export type GroundedAnswer =
  | { id: string; kind: "grounded"; question: string; claims: Claim[]; corpusLimitKey: string }
  | { id: string; kind: "insufficient-authority"; question: string; reasonKey: string; suggestedActionKey: string };

