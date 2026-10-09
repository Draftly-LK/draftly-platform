// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  token,
  type AccessorCase,
  type RecordedRequest,
} from "@/test/fetch-recorder";
import type { ApiUser } from "./auth";
import type { ApiGeneratedForm } from "@/types/rta";
import {
  generateForm,
  getForm,
  listForms,
  markFormStale,
  recordFieldDecision,
  runPreflight,
} from "./drafts";

const actor: ApiUser = {
  id: "synthetic-user",
  displayName: "Synthetic reviewer",
  role: "approver",
  notaryRegistration: null,
  jurisdiction: null,
  qualifications: null,
  professionalTitles: null,
  addressLine1: null,
  addressLine2: null,
  phone: null,
};
const form: ApiGeneratedForm = {
  id: "form-1",
  matterId: "mat-1",
  templateId: "tpl-1",
  templateVersion: "1",
  titleKey: "synthetic.form",
  formNumber: "1",
  namespace: "REGULATION",
  formVersion: 1,
  state: "GENERATED_DRAFT",
  subtypeId: "synthetic-transfer",
  rulePackVersion: "1",
  draftArtifactHash: null,
  approvedArtifactHash: null,
  approvalId: null,
  staleReason: null,
  scope: null,
  predecessorFormId: null,
  knownSourceDefectKeys: [],
  fields: [],
  preflight: {
    formId: "form-1",
    templateId: "tpl-1",
    templateVersion: "1",
    rulePackVersion: "1",
    blocking: [],
    warnings: [],
    reviewReady: false,
    approvalReady: false,
    registrationReady: false,
    templateRegistrationReadyCapable: false,
    watermarkKey: null,
    evaluatedAt: "2026-10-09T00:00:00Z",
  },
  createdAt: "2026-10-09T00:00:00Z",
  updatedAt: "2026-10-09T00:00:00Z",
  version: 2,
};
const DECISION = {
  fieldId: "field-1",
  action: "CORRECT" as const,
  value: "Synthetic",
  reason: "Synthetic",
};
let requests: RecordedRequest[];
let actorResponse: unknown, formResponse: unknown;
let mutationStatuses: number[];
beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  requests = [];
  actorResponse = actor;
  formResponse = form;
  mutationStatuses = [];
  vi.stubGlobal(
    "fetch",
    async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      const request: RecordedRequest = {
        method: init.method ?? "GET",
        path: url.pathname + url.search,
        headers: { ...(init.headers as Record<string, string>) },
        body: init.body ? JSON.parse(String(init.body)) : undefined,
      };
      requests.push(request);
      const status =
        request.method === "POST" ? (mutationStatuses.shift() ?? 200) : 200;
      const body =
        status >= 400
          ? {
              error: {
                code: "synthetic_refusal",
                message: "Synthetic refusal",
              },
            }
          : url.pathname === "/api/v1/me"
            ? actorResponse
            : request.method === "GET" && url.pathname.endsWith("/forms")
              ? {
                  items: [form],
                  page: { limit: 100, hasMore: false, nextCursor: null },
                }
              : formResponse;
      return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    },
  );
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

const cases: (AccessorCase & { reads?: string[]; idempotent?: boolean })[] = [
  {
    name: "generateForm",
    call: () => generateForm(token, "mat-1"),
    method: "POST",
    path: "/api/v1/matters/mat-1/forms",
    body: {},
    reads: ["/api/v1/me"],
    idempotent: true,
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
    reads: ["/api/v1/me", "/api/v1/forms/form-1"],
    idempotent: true,
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
];
describe("draft accessors", () => {
  it.each(cases)(
    "$name sends $method $path with its required ownership reads",
    async (accessor) => {
      await accessor.call();
      expect(requests.map(({ method, path }) => [method, path])).toEqual([
        ...(accessor.reads ?? []).map((path) => ["GET", path]),
        [accessor.method, accessor.path],
      ]);
      for (const request of requests)
        expect(request.headers.Authorization).toBe("Bearer synthetic-token");
      const request = requests.at(-1)!;
      expect(request.body).toEqual(accessor.body);
      expect(request.headers["If-Match"]).toBe(
        accessor.ifMatch === undefined ? undefined : `"${accessor.ifMatch}"`,
      );
      if (accessor.idempotent)
        expect(request.headers["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
    },
  );
});

it("generateForm passes the chosen template after resolving the actor", async () => {
  await generateForm(token, "mat-1", { templateId: "tpl-1" });
  expect(requests.map((request) => request.path)).toEqual([
    "/api/v1/me",
    "/api/v1/matters/mat-1/forms",
  ]);
  expect(requests.at(-1)!.body).toEqual({ templateId: "tpl-1" });
});
it("listForms sends limit and cursor", async () => {
  await listForms(token, "mat-1", { limit: 3, cursor: "next" });
  expect(requests).toHaveLength(1);
  expect(requests[0]!.path).toBe(
    "/api/v1/matters/mat-1/forms?limit=3&cursor=next",
  );
});
it("does not create a draft without an authenticated actor", async () => {
  actorResponse = {};
  await expect(generateForm(token, "mat-1")).rejects.toThrow(
    "Authenticated actor and matter required",
  );
  expect(requests.map((request) => request.method)).toEqual(["GET"]);
});
it("does not write a field decision without the form's owning matter", async () => {
  formResponse = { ...form, matterId: null };
  await expect(
    recordFieldDecision(token, "form-1", DECISION, 2),
  ).rejects.toThrow("Authenticated actor and matter required");
  expect(requests.map((request) => request.method)).toEqual(["GET", "GET"]);
});

it.each(["generate", "decide"] as const)(
  "%s keeps ownership reads and mutation on one captured credential",
  async (operation) => {
    const getToken = vi
      .fn()
      .mockResolvedValueOnce("synthetic-first-token")
      .mockResolvedValue("synthetic-next-token");
    if (operation === "generate") await generateForm(getToken, "mat-1");
    else await recordFieldDecision(getToken, "form-1", DECISION, 2);
    expect(getToken).toHaveBeenCalledTimes(1);
    expect(
      requests.filter((request) => request.method === "POST"),
    ).toHaveLength(1);
    for (const request of requests)
      expect(request.headers.Authorization).toBe(
        "Bearer synthetic-first-token",
      );
  },
);
it.each(["generate", "decide"] as const)(
  "%s preserves ambiguous intent through a later refusal until success",
  async (operation) => {
    mutationStatuses = [503, 412, 200, 200];
    const invoke = (version: number) =>
      operation === "generate"
        ? generateForm(token, "mat-1")
        : recordFieldDecision(token, "form-1", DECISION, version);
    await expect(invoke(2)).rejects.toThrow();
    await expect(invoke(9)).rejects.toThrow();
    await invoke(9);
    await invoke(9);
    const writes = requests.filter((request) => request.method === "POST");
    expect(writes).toHaveLength(4);
    const keys = writes.map((request) => request.headers["Idempotency-Key"]);
    expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/);
    expect(keys.slice(0, 3)).toEqual([keys[0], keys[0], keys[0]]);
    expect(keys[3]).not.toBe(keys[0]);
    if (operation === "decide")
      expect(writes.map((request) => request.headers["If-Match"])).toEqual([
        '"2"',
        '"2"',
        '"2"',
        '"9"',
      ]);
  },
);
