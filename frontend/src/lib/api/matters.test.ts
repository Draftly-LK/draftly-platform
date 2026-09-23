import { describe, expect, it } from "vitest";
import { itSendsEach, token, recordFetches } from "@/test/fetch-recorder";
import {
  compileChecklist,
  confirmSubtype,
  createMatter,
  getChecklist,
  getMatter,
  listMatters,
  routeMatter,
  saveIntakeAnswer,
} from "./matters";

const recorder = recordFetches();
const SUBTYPE = { subtypeId: "lk.rta.instrument.transfer_sale" };

describe("matter accessors", () => {
  itSendsEach(recorder, [
    {
      name: "createMatter",
      call: () => createMatter(token, { reference: "SYN/0001" }),
      method: "POST",
      path: "/api/v1/matters",
      body: { reference: "SYN/0001" },
    },
    {
      name: "getMatter",
      call: () => getMatter(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1",
    },
    {
      name: "listMatters",
      call: () => listMatters(token),
      method: "GET",
      path: "/api/v1/matters",
    },
    {
      name: "saveIntakeAnswer",
      call: () =>
        saveIntakeAnswer(token, "mat-1", "Q10_MORTGAGE", { value: "YES" }),
      method: "PUT",
      path: "/api/v1/matters/mat-1/intake/Q10_MORTGAGE",
      body: { value: "YES" },
    },
    {
      name: "confirmSubtype",
      call: () => confirmSubtype(token, "mat-1", SUBTYPE, 3),
      method: "POST",
      path: "/api/v1/matters/mat-1/subtype",
      body: SUBTYPE,
      ifMatch: 3,
    },
    {
      name: "routeMatter",
      call: () => routeMatter(token, "mat-1", 4),
      method: "POST",
      path: "/api/v1/matters/mat-1/route",
      ifMatch: 4,
    },
    {
      name: "compileChecklist",
      call: () => compileChecklist(token, "mat-1", 5),
      method: "POST",
      path: "/api/v1/matters/mat-1/checklist/compile",
      ifMatch: 5,
    },
    {
      name: "getChecklist",
      call: () => getChecklist(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/checklist",
    },
  ]);
});

describe("listMatters query", () => {
  it("sends limit and cursor when given", async () => {
    await listMatters(token, { limit: 20, cursor: "c+1/2" });

    expect(recorder.only().path).toBe(
      "/api/v1/matters?limit=20&cursor=c%2B1%2F2",
    );
  });

  it("sends a limit of zero rather than dropping it", async () => {
    await listMatters(token, { limit: 0 });

    expect(recorder.only().path).toBe("/api/v1/matters?limit=0");
  });
});

it("encodes ids so one cannot reach another route", async () => {
  await saveIntakeAnswer(token, "../mat 1", "Q/10", { value: "YES" });

  expect(recorder.only().path).toBe(
    "/api/v1/matters/..%2Fmat%201/intake/Q%2F10",
  );
});

it("never sends a subtype on creation (§12.4)", async () => {
  await createMatter(token, {
    reference: "SYN/0001",
    legacyMatterType: "transfer",
  });

  expect(recorder.only().body).not.toHaveProperty("subtypeId");
});
