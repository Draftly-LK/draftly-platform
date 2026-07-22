import { describe, expect, it } from "vitest";
import { canInsertFact } from "./fact-chip";

describe("FactChip insertion invariant", () => {
  it("allows only lawyer-reviewed fact states", () => {
    expect(canInsertFact({ verificationState: "verified" })).toBe(true);
    expect(canInsertFact({ verificationState: "corrected" })).toBe(true);
    expect(canInsertFact({ verificationState: "unreviewed" })).toBe(false);
    expect(canInsertFact({ verificationState: "conflict" })).toBe(false);
    expect(canInsertFact({ verificationState: "blocked" })).toBe(false);
  });
});

