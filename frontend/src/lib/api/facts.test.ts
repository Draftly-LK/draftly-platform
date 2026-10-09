import { describe, expect, it } from "vitest";
import { token, recordFetches } from "@/test/fetch-recorder";
import {
  listMatterFacts,
  getMatterFact,
  getFactHistory,
  reviewMatterFact,
  addManualFact,
  listSubjects,
  listTransactions,
  getFactTypes,
  createSubject,
  saveTransaction,
} from "./facts";

const recorder = recordFetches();
describe("canonical fact commands", () => {
  it("reads signed pagination and scopes without any form", async () => {
    await listMatterFacts(token, "mat/1", { cursor: "c+2", limit: 50 });
    expect(recorder.only().path).toBe(
      "/api/v1/matters/mat%2F1/facts?limit=50&cursor=c%2B2",
    );
  });
  it("reads the current canonical value and lineage history", async () => {
    await getMatterFact(token, "mat", "fact/1");
    expect(recorder.only().path).toBe("/api/v1/matters/mat/facts/fact%2F1");
  });
  it("paginates history", async () => {
    await getFactHistory(token, "mat", "fact", {
      cursor: "signed",
      limit: 100,
    });
    expect(recorder.only().path).toBe(
      "/api/v1/matters/mat/facts/fact/history?limit=100&cursor=signed",
    );
  });
  it("accepts with server token/version and caller intent key, omitting scope fields", async () => {
    await reviewMatterFact(
      token,
      "mat",
      "successor",
      "accept",
      {
        expectedScopeToken: "opaque-server",
        resolveFactIds: ["peer"],
        reason: "Synthetic resolution",
      },
      7,
      "stable-attempt",
    );
    const call = recorder.only();
    expect(call.path).toBe("/api/v1/matters/mat/facts/successor/accept");
    expect(call.body).toEqual({
      expectedScopeToken: "opaque-server",
      resolveFactIds: ["peer"],
      reason: "Synthetic resolution",
    });
    expect(call.headers["If-Match"]).toBe('"7"');
    expect(call.headers["Idempotency-Key"]).toBe("stable-attempt");
  });
  it.each(["correct", "reject"] as const)(
    "%s strips scope properties even from an invalid runtime caller",
    async (action) => {
      await reviewMatterFact(
        token,
        "mat",
        "fact",
        action,
        {
          reason: "Synthetic reason",
          value: "SYN",
          subjectId: null,
          transactionId: "foreign",
        } as Parameters<typeof reviewMatterFact>[4],
        2,
        "attempt",
      );
      expect(recorder.only().body).toEqual({
        reason: "Synthetic reason",
        value: "SYN",
      });
    },
  );
  it("association alone sends destination scope", async () => {
    await reviewMatterFact(
      token,
      "mat",
      "fact",
      "associate",
      {
        reason: "Synthetic assignment",
        subjectId: "party-2",
        transactionId: "tx-2",
      },
      2,
      "associate-intent",
    );
    expect(recorder.only().body).toEqual({
      reason: "Synthetic assignment",
      subjectId: "party-2",
      transactionId: "tx-2",
    });
  });
  it("manual information is a separate command", async () => {
    await addManualFact(
      token,
      "mat",
      {
        factTypeId: "rta.party.holder_name_en",
        value: "SYNTHETIC",
        reason: "Synthetic manual input",
      },
      "manual-intent",
    );
    expect(recorder.only().headers["Idempotency-Key"]).toBe("manual-intent");
  });
  it.each([
    ["subjects", listSubjects],
    ["transactions", listTransactions],
  ] as const)("paginates %s", async (route, read) => {
    await read(token, "mat", { cursor: "signed", limit: 100 });
    expect(recorder.only().path).toBe(
      `/api/v1/matters/mat/${route}?limit=100&cursor=signed`,
    );
  });
  it("reads governed fact types", async () => {
    await getFactTypes(token);
    expect(recorder.only().path).toBe("/api/v1/rta/fact-types");
  });
  it("creates structural subjects without identity metadata", async () => {
    await createSubject(token, "mat", "party", "key");
    expect(recorder.only().body).toEqual({ kind: "party" });
  });
  it("records deliberate transaction roles", async () => {
    await saveTransaction(
      token,
      "mat",
      {
        partyRoles: [{ subjectId: "party", role: "owner" }],
        parcelSubjectIds: [],
      },
      "key",
    );
    expect(recorder.only().path).toBe("/api/v1/matters/mat/transactions");
  });
});
