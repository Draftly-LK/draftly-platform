import { describe, expect, it } from "vitest";
import type { ApiChecklistItem } from "@/types/rta";
import {
  demandsOriginal,
  inclusionText,
  legacyTypeForSubtype,
  PARTY_UNKNOWN,
  togglePartyContext,
} from "./intake-helpers";

describe("togglePartyContext", () => {
  it("adds a context that is not chosen", () => {
    expect(togglePartyContext(["COMPANY"], "PUBLIC_BODY")).toEqual(["COMPANY", "PUBLIC_BODY"]);
  });

  it("removes a context that is already chosen", () => {
    expect(togglePartyContext(["COMPANY", "PUBLIC_BODY"], "COMPANY")).toEqual(["PUBLIC_BODY"]);
  });

  it("choosing UNKNOWN clears every asserted context", () => {
    expect(togglePartyContext(["COMPANY", "PUBLIC_BODY"], PARTY_UNKNOWN)).toEqual([PARTY_UNKNOWN]);
  });

  it("asserting a context clears UNKNOWN", () => {
    expect(togglePartyContext([PARTY_UNKNOWN], "COMPANY")).toEqual(["COMPANY"]);
  });

  it("UNKNOWN is never turned into natural persons only", () => {
    const after = togglePartyContext([], PARTY_UNKNOWN);

    expect(after).toEqual([PARTY_UNKNOWN]);
    expect(after).not.toContain("NATURAL_PERSONS_ONLY");
  });

  it("does not change the list it was given", () => {
    const current = ["COMPANY" as const];

    togglePartyContext(current, PARTY_UNKNOWN);

    expect(current).toEqual(["COMPANY"]);
  });
});

describe("inclusionText", () => {
  const item = (inclusionReason: string, inclusionTriggerId: string | null) =>
    ({ inclusionReason, inclusionTriggerId }) as ApiChecklistItem;
  const t = (key: string) => `t:${key}`;

  it("translates a known reason", () => {
    expect(inclusionText(item("BASE", null), t)).toBe("t:inclusionBase");
  });

  it("keeps internal trigger ids out of user-facing copy", () => {
    expect(inclusionText(item("CONDITIONAL_MODULE", "Q10_MORTGAGE"), t)).toBe(
      "t:inclusionConditionalModule",
    );
  });

  it("shows an unknown reason as its id rather than a missing message", () => {
    expect(inclusionText(item("SYNTHETIC_NEW_REASON", null), t)).toBe("SYNTHETIC_NEW_REASON");
  });
});

describe("legacyTypeForSubtype", () => {
  it.each([
    ["lk.rta.instrument.transfer_sale", "transfer"],
    ["lk.rta.instrument.gift", "gift"],
    ["lk.rta.instrument.lease", "lease"],
    ["lk.rta.instrument.mortgage", "mortgage"],
  ])("reverses the rule pack's map: %s → %s", (subtypeId, legacy) => {
    expect(legacyTypeForSubtype(subtypeId)).toBe(legacy);
  });

  it.each([null, "lk.rta.instrument.other_declared_instrument", "lk.rta.instrument.synthetic"])(
    "falls back to other for %j, never guessing",
    (subtypeId) => {
      expect(legacyTypeForSubtype(subtypeId)).toBe("other");
    },
  );
});

describe("demandsOriginal", () => {
  it.each([
    ["ORIGINAL_REPORTED", true],
    ["ORIGINAL_INSPECTED", true],
    ["NOT_REQUIRED", false],
    ["UNKNOWN", false],
    ["COPY_ONLY", false],
  ] as const)("%s → %s", (policy, expected) => {
    expect(demandsOriginal(policy)).toBe(expected);
  });
});
