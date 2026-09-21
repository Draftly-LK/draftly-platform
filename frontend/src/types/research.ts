import type { GroundedAnswer, AssistantScope } from "./answer";

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
  citations: Array<{
    id: string;
    sourceId: string;
    authorityId: string;
    passage: string;
    page: number;
    verified: boolean;
  }>;
  createdAt: string;
  answer?: GroundedAnswer;
}

export interface ResearchJob {
  jobId: string;
  state: "queued" | "running" | "succeeded" | "failed";
  pollAfterMs: number;
  failureClass?: string;
}
