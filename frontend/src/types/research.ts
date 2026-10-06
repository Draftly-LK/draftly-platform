import type { GroundedAnswer, AssistantScope } from "./answer";

/** Which legal sources a research question searches (not the conversation scope). */
export type ResearchSources = "statutes" | "cases" | "all";

export interface ResearchCitation {
  id: string;
  sourceId: string;
  authorityId: string;
  passage: string;
  page: number;
  verified: boolean;
  /** "case" citations are unverified research leads. Older citations read as "statute". */
  authorityKind?: "statute" | "case";
  title?: string | null;
  reference?: string | null;
  sourceUrl?: string | null;
}

export interface ResearchConversation {
  id: string;
  title: string;
  scope: AssistantScope & { matterId?: string };
  activeBranchId: string;
  createdAt: string;
  updatedAt: string;
}

export interface ResearchMessage {
  id: string;
  conversationId: string;
  branchId: string;
  parentMessageId?: string;
  editedFromId?: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  answerId?: string;
  citations: ResearchCitation[];
  /** The answer's claims in order, each with the authority ids it cites. Empty on older answers. */
  claims?: Array<{ text: string; citationIds: string[] }>;
  createdAt: string;
  answer?: GroundedAnswer;
}

export interface ResearchJob {
  jobId: string;
  state: "queued" | "running" | "succeeded" | "failed";
  pollAfterMs: number;
  failureClass?: string;
}
