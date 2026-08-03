import { describe, expect, it } from "vitest";
import type { FormTemplate, VerifiedFact, VerificationState } from "@/types";
import { deriveTemplateReadiness } from "./readiness";

const template: FormTemplate = {
  id: "template-test",
  formNumber: "Form 8",
  nameKey: "draft.form8Name",
  regime: "rta",
  transactionType: "transfer",
  approvalState: "approved",
  fields: [
    { id: "f-2", labelKey: "facts.parcelNo", order: 2, required: true, factBinding: "parcelNo" },
    { id: "f-1", labelKey: "facts.extent", order: 1, required: true, factBinding: "extent" },
    { id: "f-3", labelKey: "facts.landName", order: 3, required: false, factBinding: "landName" },
    { id: "f-4", labelKey: "facts.notaryName", order: 4, required: true, factBinding: "unbound" },
  ],
  blocks: [],
};

const fact = (key: string, verificationState: VerificationState): VerifiedFact => ({
  id: `fact-${key}`,
  matterId: "matter-test",
  key,
  labelKey: `facts.${key}`,
  section: "parcel",
  value: key,
  extractedValue: key,
  confidence: 0.9,
  verificationState,
  changes: [],
});

describe("deriveTemplateReadiness", () => {
  it("orders fields by the form's own numbering", () => {
    const { fields } = deriveTemplateReadiness(template, []);
    expect(fields.map((entry) => entry.field.id)).toEqual(["f-1", "f-2", "f-3", "f-4"]);
  });

  it("treats verified and corrected facts as satisfied", () => {
    const readiness = deriveTemplateReadiness(template, [
      fact("extent", "verified"),
      fact("parcelNo", "corrected"),
      fact("unbound", "verified"),
    ]);
    expect(readiness.canGenerate).toBe(true);
    expect(readiness.requiredSatisfied).toBe(3);
    expect(readiness.outstanding).toHaveLength(0);
  });

  it("blocks generation and names the field when a required fact is blocked", () => {
    const readiness = deriveTemplateReadiness(template, [
      fact("extent", "blocked"),
      fact("parcelNo", "verified"),
      fact("unbound", "verified"),
    ]);
    expect(readiness.canGenerate).toBe(false);
    expect(readiness.outstanding.map((entry) => entry.field.id)).toEqual(["f-1"]);
    expect(readiness.outstanding[0]?.status).toBe("blocked");
  });

  it("reports conflict and unreviewed states distinctly", () => {
    const readiness = deriveTemplateReadiness(template, [
      fact("extent", "conflict"),
      fact("parcelNo", "unreviewed"),
      fact("unbound", "verified"),
    ]);
    expect(readiness.outstanding.map((entry) => entry.status)).toEqual([
      "conflict",
      "unreviewed",
    ]);
    expect(readiness.requiredSatisfied).toBe(1);
  });

  it("ignores optional fields that have no fact", () => {
    const readiness = deriveTemplateReadiness(template, [
      fact("extent", "verified"),
      fact("parcelNo", "verified"),
      fact("unbound", "verified"),
    ]);
    expect(readiness.fields.find((entry) => entry.field.id === "f-3")?.status).toBe("missing");
    expect(readiness.canGenerate).toBe(true);
  });

  it("marks a required field missing when nothing binds to it", () => {
    const readiness = deriveTemplateReadiness(template, [
      fact("extent", "verified"),
      fact("parcelNo", "verified"),
    ]);
    expect(readiness.canGenerate).toBe(false);
    expect(readiness.outstanding[0]?.status).toBe("missing");
  });
});
