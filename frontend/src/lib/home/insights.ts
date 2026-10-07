import type { ApiChecklist, RtaMatterState } from "@/types/rta";
import { daysUntil } from "./dashboard";
import { summarizeMatters, type StatusFilter } from "./practice-snapshot";

/**
 * The home page's at-a-glance figures. Each is derived from data the page
 * already has, with the same predicates as the header counts, so a chart and
 * the number beside it can never disagree.
 */

export type PipelineStage = "progress" | "review" | "drafting";

export interface PipelineSegment {
  stage: PipelineStage;
  count: number;
  /** The Matters filter that lists exactly these matters, when one exists. */
  filter: StatusFilter | null;
}

/** Open matters split by stage: waiting on the lawyer, drafting, and the rest still in progress. */
export function pipelineSegments(states: readonly RtaMatterState[]): {
  open: number;
  segments: PipelineSegment[];
} {
  const { open, needsReview, drafting } = summarizeMatters(states);
  return {
    open,
    segments: [
      { stage: "progress", count: Math.max(0, open - needsReview - drafting), filter: null },
      { stage: "review", count: needsReview, filter: "review" },
      { stage: "drafting", count: drafting, filter: "drafting" },
    ],
  };
}

/** Obligations due on each of the next `days` days, today first. Overdue items count on day 0. */
export function dueByDay(
  dueDates: readonly string[],
  now: Date,
  days = 14,
): number[] {
  const counts = Array.from({ length: days }, () => 0);
  for (const dueDate of dueDates) {
    const offset = Math.max(0, daysUntil(dueDate, now));
    if (offset < days) counts[offset] = (counts[offset] ?? 0) + 1;
  }
  return counts;
}

/**
 * How far a matter's checklist has got: satisfied over applicable requirements.
 * A requirement the rule pack ruled out is not work, so it leaves the denominator.
 * Null when nothing applies yet, which is "not known", not 0%.
 */
export function checklistPercent(checklist: Pick<ApiChecklist, "items"> | null): number | null {
  const applicable = (checklist?.items ?? []).filter((item) => item.applicability !== "NOT_APPLICABLE");
  if (applicable.length === 0) return null;
  const satisfied = applicable.filter((item) => item.lifecycle === "SATISFIED").length;
  return Math.round((satisfied / applicable.length) * 100);
}

/** The research allowance from billing usage: used this period, and the cap if there is one. */
export interface ResearchUsage {
  used: number;
  limit: number | null;
  periodEnd: string | null;
}

export const RESEARCH_METRIC = "research_queries.monthly";

export function researchUsage(
  rows: ReadonlyArray<{ metric: string; quantity: number; limitValue?: number | null; periodEnd?: string }>,
): ResearchUsage {
  const row = rows.find((item) => item.metric === RESEARCH_METRIC);
  return { used: row?.quantity ?? 0, limit: row?.limitValue ?? null, periodEnd: row?.periodEnd ?? null };
}

/** How many timestamps fall in the same calendar month as `now`, in the user's own time zone. */
export function countThisMonth(timestamps: readonly (string | undefined)[], now: Date): number {
  return timestamps.filter((timestamp) => {
    if (!timestamp) return false;
    const date = new Date(timestamp);
    return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth();
  }).length;
}
