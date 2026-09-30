import { describe, expect, it } from "vitest";
import { applyDemoDecision, DEMO_GAZETTE_FORMS, DemoDecisionRefused, demoGazetteForm } from "./demo-forms";
import { listSlots, gazetteFormFor } from "./index";

function refusal(run: () => unknown): string | null {
  try {
    run();
    return null;
  } catch (error) {
    return error instanceof DemoDecisionRefused ? error.code : "unexpected";
  }
}

describe("synthetic demo gazette forms", () => {
  it("has a gazette rendering for every demo form, and every bound blank has a field", () => {
    for (const form of DEMO_GAZETTE_FORMS) {
      const gazette = gazetteFormFor(form.templateId);
      expect(gazette, form.templateId).toBeDefined();
      const fieldIds = new Set(form.fields.map((field) => field.fieldId));
      for (const slot of listSlots(gazette!.document)) {
        if (slot.field) expect(fieldIds.has(slot.field), slot.field).toBe(true);
      }
    }
  });

  it("hands out copies, so a demo session never mutates the seed", () => {
    const first = demoGazetteForm("demo-form-08")!;
    first.fields[0]!.displayValue = "changed";
    expect(demoGazetteForm("demo-form-08")!.fields[0]!.displayValue).toBe("Synthetic District");
    expect(demoGazetteForm("missing")).toBeUndefined();
  });

  it("confirms a populated field and bumps the version", () => {
    const form = demoGazetteForm("demo-form-08")!;
    const updated = applyDemoDecision(form, { fieldId: "gn_division", action: "CONFIRM" });
    const field = updated.fields.find((candidate) => candidate.fieldId === "gn_division")!;
    expect(field.awaitingConfirmation).toBe(false);
    expect(updated.version).toBe(form.version + 1);
    expect(updated.preflight.blocking.some((item) => item.subjectId === "gn_division")).toBe(false);
  });

  it("clears with a reason and reports the field unresolved", () => {
    const form = demoGazetteForm("demo-form-08")!;
    const updated = applyDemoDecision(form, { fieldId: "district", action: "CLEAR", reason: "wrong parcel" });
    const field = updated.fields.find((candidate) => candidate.fieldId === "district")!;
    expect(field.renderedValue).toBeNull();
    expect(field.displayValue).toBe("[[UNRESOLVED: district]]");
    expect(updated.preflight.blocking.some((item) => item.subjectId === "district")).toBe(true);
  });

  it("corrects only a non-critical lawyer-authored field", () => {
    const form = demoGazetteForm("demo-form-12")!;
    const updated = applyDemoDecision(form, {
      fieldId: "cancellation_particulars",
      action: "CORRECT",
      value: "  Synthetic particulars  ",
      reason: "drafted",
    });
    expect(updated.fields.find((candidate) => candidate.fieldId === "cancellation_particulars")!.displayValue).toBe(
      "Synthetic particulars",
    );
  });

  it("refuses what the API refuses", () => {
    const form08 = demoGazetteForm("demo-form-08")!;
    const form12 = demoGazetteForm("demo-form-12")!;
    expect(refusal(() => applyDemoDecision(form08, { fieldId: "nope", action: "CONFIRM" }))).toBe("UNKNOWN_FIELD");
    expect(refusal(() => applyDemoDecision(form08, { fieldId: "village", action: "CONFIRM" }))).toBe(
      "FIELD_NOT_POPULATED",
    );
    expect(refusal(() => applyDemoDecision(form08, { fieldId: "district", action: "CLEAR" }))).toBe("REASON_REQUIRED");
    expect(
      refusal(() => applyDemoDecision(form08, { fieldId: "district", action: "CORRECT", value: "x", reason: "r" })),
    ).toBe("CRITICAL_FIELD_REQUIRES_CONFIRMED_FACT");
    expect(
      refusal(() => applyDemoDecision(form08, { fieldId: "notary_name", action: "CORRECT", value: "x", reason: "r" })),
    ).toBe("LAWYER_AUTHORED_TEXT_NOT_PERMITTED");
    expect(
      refusal(() =>
        applyDemoDecision(form12, { fieldId: "cancellation_particulars", action: "CORRECT", value: " ", reason: "r" }),
      ),
    ).toBe("FIELD_VALUE_REQUIRED");
    expect(
      refusal(() => applyDemoDecision({ ...form08, approvalId: "approval-1" }, { fieldId: "district", action: "CONFIRM" })),
    ).toBe("APPROVED_FORM_IMMUTABLE");
  });

  it("warns, rather than blocks, on an unresolved optional field", () => {
    const form = demoGazetteForm("demo-form-08")!;
    expect(form.preflight.warnings.map((item) => item.subjectId)).toContain("village");
    expect(form.preflight.approvalReady).toBe(false);
    expect(form.preflight.registrationReady).toBe(false);
  });
});
