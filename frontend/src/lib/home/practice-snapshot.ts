import type { RtaMatterState } from "@/types/rta";

/**
 * The home page's practice snapshot: how many matters are open, how many are
 * waiting on the lawyer, and how many are being drafted. Counted from the same
 * matter feed the recent-matters list shows, so the numbers never disagree.
 */
export interface PracticeSnapshot {
  open: number;
  needsReview: number;
  drafting: number;
}

const FINISHED: ReadonlySet<RtaMatterState> = new Set(["REGISTERED", "CLOSED", "CANCELLED"]);
export const NEEDS_REVIEW: ReadonlySet<RtaMatterState> = new Set([
  "REVIEW_REQUIRED",
  "LEGAL_REVIEW",
  "APPROVAL_PENDING",
]);
const DRAFTING: ReadonlySet<RtaMatterState> = new Set(["READY_TO_DRAFT", "DRAFTING"]);

export function summarizeMatters(states: readonly RtaMatterState[]): PracticeSnapshot {
  return states.reduce<PracticeSnapshot>(
    (summary, state) => ({
      open: summary.open + (FINISHED.has(state) ? 0 : 1),
      needsReview: summary.needsReview + (NEEDS_REVIEW.has(state) ? 1 : 0),
      drafting: summary.drafting + (DRAFTING.has(state) ? 1 : 0),
    }),
    { open: 0, needsReview: 0, drafting: 0 },
  );
}
