import type { Authority } from "./answer";

export type StepState = "not-started" | "in-progress" | "complete" | "blocked";
export interface StepRule { id: string; labelKey: string; keywords: string[] }

export interface Step {
  id: string;
  workflowId: string;
  order: number;
  titleKey: string;
  objectiveKey: string;
  state: StepState;
  mandatory: boolean;
  requiredFactIds: string[];
  requiredDocumentIds: string[];
  authority: Authority;
  sourceExcerpt: string;
  rules: StepRule[];
  note?: string;
  overrideReason?: string;
}

export interface Workflow {
  id: string;
  titleKey: string;
  regime: "rta";
  transactionTypes: string[];
  function: "examination" | "drafting" | "execution" | "attestation";
  approvalState: "draft" | "approved" | "retired";
  language: "en" | "si" | "bilingual";
  ownerId: string;
  version: string;
  steps: Step[];
}

