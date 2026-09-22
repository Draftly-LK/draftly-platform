import { describe, expect, it } from "vitest";
import { itSendsEach, token, recordFetches } from "@/test/fetch-recorder";
import {
  generateForm,
  getForm,
  listForms,
  markFormStale,
  recordFieldDecision,
  runPreflight,
} from "./drafts";

const recorder = recordFetches();
const DECISION = {
  fieldId: "field-1",
  action: "CORRECT" as const,
  value: "Synthetic",
  reason: "Synthetic",
};

describe("draft accessors", () => {
  itSendsEach(recorder, [
    {
      name: "generateForm",
      call: () => generateForm(token, "mat-1"),
      method: "POST",
      path: "/api/v1/matters/mat-1/forms",
      body: {},
    },
    {
      name: "listForms",
      call: () => listForms(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/forms",
    },
    {
      name: "getForm",
      call: () => getForm(token, "form-1"),
      method: "GET",
      path: "/api/v1/forms/form-1",
    },
    {
      name: "recordFieldDecision",
      call: () => recordFieldDecision(token, "form-1", DECISION, 2),
      method: "POST",
      path: "/api/v1/forms/form-1/field-decisions",
      body: DECISION,
      ifMatch: 2,
    },
    {
      name: "runPreflight",
      call: () => runPreflight(token, "form-1"),
      method: "POST",
      path: "/api/v1/forms/form-1/preflight",
    },
    {
      name: "markFormStale",
      call: () => markFormStale(token, "form-1", { reason: "Synthetic" }, 3),
      method: "POST",
      path: "/api/v1/forms/form-1/mark-stale",
      body: { reason: "Synthetic" },
      ifMatch: 3,
    },
  ]);
});

it("generateForm passes the chosen template", async () => {
  await generateForm(token, "mat-1", { templateId: "tpl-1" });

  expect(recorder.only().body).toEqual({ templateId: "tpl-1" });
});

it("listForms sends limit and cursor", async () => {
  await listForms(token, "mat-1", { limit: 3, cursor: "next" });

  expect(recorder.only().path).toBe(
    "/api/v1/matters/mat-1/forms?limit=3&cursor=next",
  );
});
