import { describe, expect, it } from "vitest";
import { humanizeMessageKey, messageFallback } from "./humanize";

describe("humanizeMessageKey", () => {
  it("turns backend enum codes into a sentence", () => {
    expect(humanizeMessageKey("gazette.unresolvedReason.NO_FACT")).toBe("No fact");
    expect(humanizeMessageKey("generatedFormState.STALE_AFTER_APPROVAL")).toBe("Stale after approval");
  });

  it("reads camelCase and kebab-case identifiers", () => {
    expect(humanizeMessageKey("matters.inReview")).toBe("In review");
    expect(humanizeMessageKey("fileState.needs-review")).toBe("Needs review");
  });

  it("names the thing, not the slot, for `.label`-style keys", () => {
    expect(humanizeMessageKey("rta.form.reg_2022_form_08.field.district.label")).toBe("District");
    expect(humanizeMessageKey("rta.form.reg_2022_form_08.title")).toBe("Reg 2022 form 08");
    expect(humanizeMessageKey("rta.subtype.transfer_sale")).toBe("Transfer sale");
    expect(humanizeMessageKey("rta.issue.party_identity_conflict.summary")).toBe("Party identity conflict");
  });

  it("handles a bare key and an empty one", () => {
    expect(humanizeMessageKey("save")).toBe("Save");
    expect(humanizeMessageKey("")).toBe("");
    expect(humanizeMessageKey("label")).toBe("Label");
  });

  it("never returns the dotted key", () => {
    for (const key of ["a.b.c", "checks.state.OPEN", "rta.doc.title_certificate.label"]) {
      expect(humanizeMessageKey(key)).not.toContain(".");
    }
  });
});

describe("messageFallback", () => {
  it("ignores the namespace and humanises the key", () => {
    expect(messageFallback({ namespace: "gazette", key: "unresolvedReason.NO_FACT" })).toBe("No fact");
  });
});
