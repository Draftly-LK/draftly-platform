import { describe, expect, it } from "vitest";
import { matchesStatusFilter, mattersHref, parseStatusFilter, summarizeMatters } from "./practice-snapshot";

describe("summarizeMatters", () => {
  it("counts nothing for an empty practice", () => {
    expect(summarizeMatters([])).toEqual({ open: 0, needsReview: 0, drafting: 0 });
  });

  it("treats registered, closed and cancelled matters as finished", () => {
    expect(summarizeMatters(["REGISTERED", "CLOSED", "CANCELLED"]).open).toBe(0);
  });

  it("counts review and drafting states within the open matters", () => {
    expect(
      summarizeMatters([
        "REVIEW_REQUIRED",
        "LEGAL_REVIEW",
        "APPROVAL_PENDING",
        "READY_TO_DRAFT",
        "DRAFTING",
        "INTAKE_DRAFT",
        "REGISTERED",
      ]),
    ).toEqual({ open: 6, needsReview: 3, drafting: 2 });
  });
});

describe("status filters", () => {
  it("parses the three known values and ignores everything else", () => {
    expect(parseStatusFilter("review")).toBe("review");
    expect(parseStatusFilter("open")).toBe("open");
    expect(parseStatusFilter("drafting")).toBe("drafting");
    expect(parseStatusFilter("REVIEW")).toBeNull();
    expect(parseStatusFilter("")).toBeNull();
    expect(parseStatusFilter(null)).toBeNull();
    expect(parseStatusFilter(undefined)).toBeNull();
  });

  it("selects exactly the matters each dashboard count counts", () => {
    const states = ["INTAKE_DRAFT", "REVIEW_REQUIRED", "LEGAL_REVIEW", "DRAFTING", "READY_TO_DRAFT", "APPROVED", "CLOSED"] as const;
    const summary = summarizeMatters([...states]);
    for (const [filter, count] of [
      ["open", summary.open],
      ["review", summary.needsReview],
      ["drafting", summary.drafting],
    ] as const) {
      expect(states.filter((state) => matchesStatusFilter(state, filter))).toHaveLength(count);
    }
  });

  it("builds the list link for a filter", () => {
    expect(mattersHref("review")).toBe("/matters?status=review");
    expect(mattersHref(null)).toBe("/matters");
  });
});
