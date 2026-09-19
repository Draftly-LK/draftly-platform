import { describe, expect, it } from "vitest";
import { itSendsEach, token, recordFetches } from "@/test/fetch-recorder";
import {
  createApproval,
  createExport,
  createRegistrationEvent,
  listApprovals,
  listExports,
  listRegistrationEvents,
} from "./approvals";

const recorder = recordFetches();
const EVENT = {
  eventType: "PRESENTED" as const,
  eventDate: "2026-08-17",
  registryOffice: "Synthetic office",
};

describe("approval accessors", () => {
  itSendsEach(recorder, [
    {
      name: "createApproval",
      call: () =>
        createApproval(token, "form-1", { disposedWarningIds: ["w-1"] }),
      method: "POST",
      path: "/api/v1/forms/form-1/approvals",
      body: { disposedWarningIds: ["w-1"] },
    },
    {
      name: "listApprovals",
      call: () => listApprovals(token, "form-1"),
      method: "GET",
      path: "/api/v1/forms/form-1/approvals",
    },
    {
      name: "createExport",
      call: () =>
        createExport(token, "form-1", { format: "APPROVED_MANIFEST" }),
      method: "POST",
      path: "/api/v1/forms/form-1/exports",
      body: { format: "APPROVED_MANIFEST" },
    },
    {
      name: "listExports",
      call: () => listExports(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/exports",
    },
    {
      name: "createRegistrationEvent",
      call: () => createRegistrationEvent(token, "mat-1", EVENT),
      method: "POST",
      path: "/api/v1/matters/mat-1/registration-events",
      body: EVENT,
    },
    {
      name: "listRegistrationEvents",
      call: () => listRegistrationEvents(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/registration-events",
    },
  ]);
});

it("createApproval sends an empty body, not none, when nothing is disposed", async () => {
  await createApproval(token, "form-1");

  expect(recorder.only().body).toEqual({});
});

it("no approval request carries a step-up token today", async () => {
  // TESTING_PLAN.md §3.2 expects approvals to pass X-Step-Up-Token. The
  // backend's approval route does not demand step-up (an open decision
  // recorded in Stage 3), so the client has nothing to send yet. When the
  // policy lands, this test should flip to require the header.
  await createApproval(token, "form-1");

  expect(recorder.only().headers["X-Step-Up-Token"]).toBeUndefined();
});

describe("list queries", () => {
  it.each([
    [
      "listApprovals",
      () => listApprovals(token, "form-1", { limit: 2, cursor: "c" }),
      "/api/v1/forms/form-1/approvals?limit=2&cursor=c",
    ],
    [
      "listExports",
      () => listExports(token, "mat-1", { limit: 2, cursor: "c" }),
      "/api/v1/matters/mat-1/exports?limit=2&cursor=c",
    ],
    [
      "listRegistrationEvents",
      () => listRegistrationEvents(token, "mat-1", { limit: 2, cursor: "c" }),
      "/api/v1/matters/mat-1/registration-events?limit=2&cursor=c",
    ],
  ] as const)("%s sends limit and cursor", async (_, call, path) => {
    await call();

    expect(recorder.only().path).toBe(path);
  });
});
