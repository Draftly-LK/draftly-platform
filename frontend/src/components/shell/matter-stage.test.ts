import { describe, expect, it } from "vitest";
import type { RtaMatterState } from "@/types/rta";
import { STAGE_ORDER, stageForState } from "./matter-stage";

// `satisfies` makes the compiler reject this list if a state is added to or
// removed from RtaMatterState, so the sweep below can never miss one.
const EVERY_STATE = Object.keys({
  INTAKE_DRAFT: true,
  ROUTED: true,
  EVIDENCE_COLLECTION: true,
  REVIEW_REQUIRED: true,
  LEGAL_REVIEW: true,
  READY_TO_DRAFT: true,
  DRAFTING: true,
  APPROVAL_PENDING: true,
  APPROVED: true,
  EXPORTED: true,
  SUBMITTED: true,
  REGISTERED: true,
  CLOSED: true,
  MANUAL_SUPPORTED: true,
  LITIGATION_HOLD: true,
  CANCELLED: true,
} satisfies Record<RtaMatterState, true>) as RtaMatterState[];

describe("stageForState", () => {
  it.each(EVERY_STATE)("%s maps to a stage the stepper shows", (state) => {
    expect(STAGE_ORDER).toContain(stageForState(state));
  });

  it("every stage is reached by at least one state", () => {
    expect(new Set(EVERY_STATE.map(stageForState))).toEqual(new Set(STAGE_ORDER));
  });

  it("the ordinary path never moves backwards through the stages", () => {
    const path: RtaMatterState[] = [
      "INTAKE_DRAFT",
      "ROUTED",
      "EVIDENCE_COLLECTION",
      "REVIEW_REQUIRED",
      "LEGAL_REVIEW",
      "READY_TO_DRAFT",
      "DRAFTING",
      "APPROVAL_PENDING",
      "APPROVED",
      "EXPORTED",
      "SUBMITTED",
      "REGISTERED",
      "CLOSED",
    ];
    const positions = path.map((state) => STAGE_ORDER.indexOf(stageForState(state)));

    expect(positions).toEqual([...positions].sort((a, b) => a - b));
  });
});
