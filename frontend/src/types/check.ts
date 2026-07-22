import type { Authority } from "./answer";
import type { EvidenceSpan } from "./evidence";

export type CheckStatus = "pass" | "warning" | "fail" | "needs-review";
export type CheckCategory = "missing-document" | "identity" | "parcel" | "chain-of-title" | "registration" | "stamp-duty" | "execution" | "jurisdiction";

export interface CheckResolution { action: "resolved" | "waived" | "document-requested" | "checklist-created"; reason: string; actorId: string; timestamp: string }

export interface Check {
  id: string;
  matterId: string;
  category: CheckCategory;
  descriptionKey: string;
  status: CheckStatus;
  affectedFactIds: string[];
  evidence: EvidenceSpan[];
  authority?: Authority;
  suggestedResolutionKey: string;
  ownerId?: string;
  resolution?: CheckResolution;
}

export interface CrossCheckBinding { factId: string; evidence: EvidenceSpan }
export interface CrossCheck { id: string; matterId: string; labelKey: string; bindings: CrossCheckBinding[]; verdict: "match" | "mismatch" | "incomplete"; checkId: string }

