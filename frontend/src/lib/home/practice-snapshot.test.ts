import { describe, expect, it } from "vitest";
import { summarizeMatters } from "./practice-snapshot";

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
