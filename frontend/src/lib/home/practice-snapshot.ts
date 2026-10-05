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

/** The Matters list's `?status=` values, one per count on the dashboard. */
export const STATUS_FILTERS = ["open", "review", "drafting"] as const;
export type StatusFilter = (typeof STATUS_FILTERS)[number];

/** Reads `?status=`; anything unrecognised means no filter. */
export function parseStatusFilter(value: string | null | undefined): StatusFilter | null {
  return (STATUS_FILTERS as readonly string[]).includes(value ?? "") ? (value as StatusFilter) : null;
}

/** The same predicates `summarizeMatters` counts with, so a count and its list always agree. */
export function matchesStatusFilter(state: RtaMatterState, filter: StatusFilter): boolean {
  switch (filter) {
    case "open":
      return !FINISHED.has(state);
    case "review":
      return NEEDS_REVIEW.has(state);
    case "drafting":
      return DRAFTING.has(state);
  }
}

/** `/matters?status=review` for a filter, `/matters` for none. */
export function mattersHref(filter: StatusFilter | null): string {
  return filter ? `/matters?status=${filter}` : "/matters";
}
