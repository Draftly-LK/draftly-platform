/** Operational work records do not determine legal approval or export eligibility. */
export type WorkTaskGroup =
  | "documents"
  | "evidence"
  | "drafting"
  | "execution"
  | "registration"
  | "completion";
export type WorkTaskState =
  | "not-started"
  | "in-progress"
  | "blocked"
  | "complete"
  | "stale"
  | "pending-applicability"
  | "not-applicable"
  | "cancelled";
export interface WorkEvidenceReference {
  kind: string;
  id: string;
  version: number | null;
  generation: number | null;
  transactionId: string | null;
  subjectId: string | null;
  associationVersion: number | null;
}
export interface WorkTask {
  id: string;
  version: number;
  group: WorkTaskGroup;
  origin: "governed" | "operational" | "lawyer" | "agent";
  state: WorkTaskState;
  title: string | null;
  titleKey: string | null;
  reason: string | null;
  reasonKey: string | null;
  completedBy: string | null;
  completedAt: string | null;
  assignedTo: string | null;
  evidence: WorkEvidenceReference[];
  action: {
    kind: "navigate" | "decide";
    section: "documents" | "facts" | "checks" | "drafts" | "exports" | null;
    targetId: string | null;
  } | null;
}
export interface WorkChecklistRead {
  matterId: string;
  tasks: WorkTask[];
  suggestions: WorkTask[];
  progress: {
    total: number;
    completed: number;
    percent: number;
    assessing: boolean;
  };
  nextTaskId: string | null;
}
export interface WorkTaskHistory {
  items: {
    id: string;
    taskId: string;
    decision: string;
    actorId: string;
    createdAt: string;
    note: string | null;
    previousState: WorkTaskState;
    state: WorkTaskState;
    version: number;
    evidence: WorkEvidenceReference[];
  }[];
  nextCursor: string | null;
}
export type CreateWorkTask = {
  title: string;
  reason: string;
  group: WorkTaskGroup;
  evidence?: WorkEvidenceReference[];
};
export type WorkTaskDecision = {
  decision: "complete" | "review" | "cancel";
  note?: string;
  evidence?: WorkEvidenceReference[];
};
