import type { RtaMatterState } from "@/types/rta";

/**
 * The six demo-narrative stages the shell stepper shows, each covering one or
 * more `RtaMatterState` values (§10.1). Exception states (`MANUAL_SUPPORTED`,
 * `LITIGATION_HOLD`) and `CANCELLED` fall back to whichever ordinary stage
 * they interrupted rather than getting a stage of their own — they are holds
 * on a stage, not a different stage.
 */
export const STAGE_ORDER = [
  "intake",
  "evidence",
  "review",
  "drafting",
  "approval",
  "export",
] as const;

export type MatterStage = (typeof STAGE_ORDER)[number];

const STATE_STAGE: Record<RtaMatterState, MatterStage> = {
  INTAKE_DRAFT: "intake",
  ROUTED: "intake",
  EVIDENCE_COLLECTION: "evidence",
  REVIEW_REQUIRED: "review",
  LEGAL_REVIEW: "review",
  READY_TO_DRAFT: "drafting",
  DRAFTING: "drafting",
  APPROVAL_PENDING: "approval",
  APPROVED: "approval",
  EXPORTED: "export",
  SUBMITTED: "export",
  REGISTERED: "export",
  CLOSED: "export",
  MANUAL_SUPPORTED: "evidence",
  LITIGATION_HOLD: "review",
  CANCELLED: "intake",
};

export function stageForState(state: RtaMatterState): MatterStage {
  return STATE_STAGE[state];
}
