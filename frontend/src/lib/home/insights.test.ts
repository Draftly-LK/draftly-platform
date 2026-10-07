import { describe, expect, it } from "vitest";
import { checklistPercent, dueByDay, pipelineSegments, researchUsage } from "./insights";
import { summarizeMatters } from "./practice-snapshot";
import type { ApiChecklist, RtaMatterState } from "@/types/rta";

const NOW = new Date("2026-07-22T10:00:00Z");

describe("pipelineSegments", () => {
  it("splits open matters by stage with the header's own predicates", () => {
    const states: RtaMatterState[] = ["EVIDENCE_COLLECTION", "REVIEW_REQUIRED", "DRAFTING", "READY_TO_DRAFT", "CLOSED"];
    const { open, segments } = pipelineSegments(states);
    const header = summarizeMatters(states);
    expect(open).toBe(header.open);
    expect(segments).toEqual([
      { stage: "progress", count: 1, filter: null },
      { stage: "review", count: header.needsReview, filter: "review" },
      { stage: "drafting", count: header.drafting, filter: "drafting" },
    ]);
    expect(segments.reduce((sum, segment) => sum + segment.count, 0)).toBe(open);
  });

  it("is all zero for an empty practice", () => {
    expect(pipelineSegments([]).segments.every((segment) => segment.count === 0)).toBe(true);
  });
});

describe("dueByDay", () => {
  it("counts per day from today, puts overdue on today, and ignores the far future", () => {
    expect(dueByDay(["2026-07-22", "2026-07-20", "2026-07-25", "2026-07-25", "2026-09-01"], NOW, 5)).toEqual([2, 0, 0, 2, 0]);
  });
});

describe("checklistPercent", () => {
  const item = (applicability: string, lifecycle: string) => ({ applicability, lifecycle }) as ApiChecklist["items"][number];

  it("is satisfied over applicable requirements", () => {
    const items = [item("APPLICABLE", "SATISFIED"), item("APPLICABLE", "OPEN"), item("APPLICABLE", "OPEN"), item("NOT_APPLICABLE", "OPEN")];
    expect(checklistPercent({ items })).toBe(33);
  });

  it("is unknown, not 0%, when nothing applies or there is no checklist", () => {
    expect(checklistPercent(null)).toBeNull();
    expect(checklistPercent({ items: [item("NOT_APPLICABLE", "OPEN")] })).toBeNull();
  });
});

describe("researchUsage", () => {
  it("reads the monthly research metric and its cap", () => {
    expect(researchUsage([{ metric: "matters.active", quantity: 3 }, { metric: "research_queries.monthly", quantity: 12, limitValue: 50, periodEnd: "2026-08-01T00:00:00Z" }])).toEqual({ used: 12, limit: 50, periodEnd: "2026-08-01T00:00:00Z" });
  });

  it("is zero with no cap when the metric is absent", () => {
    expect(researchUsage([])).toEqual({ used: 0, limit: null, periodEnd: null });
  });
});
