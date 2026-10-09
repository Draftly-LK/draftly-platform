import { describe, expect, it } from "vitest";
import { itSendsEach, token, recordFetches } from "@/test/fetch-recorder";
import {
  listCheckResults,
  listIssues,
  recordIssueDecision,
  runChecks,
} from "./checks";

const recorder = recordFetches();
const DECISION = {
  state: "RESOLVED",
  reason: "Synthetic reason",
  evidenceReferenceIds: ["ev-1"],
};

describe("check accessors", () => {
  itSendsEach(recorder, [
    {
      name: "runChecks",
      call: () => runChecks(token, "mat-1", { transactionId: "tx", subjectId: "subject", associationVersion: 2 }),
      method: "POST",
      path: "/api/v1/matters/mat-1/checks/run",
      body: { transactionId: "tx", subjectId: "subject", associationVersion: 2 },
    },
    {
      name: "listCheckResults",
      call: () => listCheckResults(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/checks",
    },
    {
      name: "listIssues",
      call: () => listIssues(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/issues",
    },
    {
      name: "recordIssueDecision",
      call: () => recordIssueDecision(token, "mat-1", "iss-1", DECISION, 4),
      method: "POST",
      path: "/api/v1/matters/mat-1/issues/iss-1/decisions",
      body: DECISION,
      ifMatch: 4,
    },
  ]);
});

describe("list queries", () => {
  it("listIssues sends its filters with the page", async () => {
    await listIssues(token, "mat-1", {
      severity: "BLOCKING",
      state: "OPEN",
      limit: 10,
      cursor: "c",
    });

    const query = new URLSearchParams(recorder.only().path.split("?")[1]);
    expect(Object.fromEntries(query)).toEqual({
      severity: "BLOCKING",
      state: "OPEN",
      limit: "10",
      cursor: "c",
    });
  });

  it("listIssues leaves out filters that are not set", async () => {
    await listIssues(token, "mat-1", { state: "OPEN" });

    expect(recorder.only().path).toBe(
      "/api/v1/matters/mat-1/issues?state=OPEN",
    );
  });

  it("listCheckResults sends limit and cursor", async () => {
    await listCheckResults(token, "mat-1", { limit: 2, cursor: "c" });

    expect(recorder.only().path).toBe(
      "/api/v1/matters/mat-1/checks?limit=2&cursor=c",
    );
  });

  it("runChecks passes the search currency window", async () => {
    await runChecks(token, "mat-1", { transactionId: "tx", subjectId: null, associationVersion: 2, searchCurrencyMaxAgeDays: 30 });

    expect(recorder.only().body).toEqual({ transactionId: "tx", subjectId: null, associationVersion: 2, searchCurrencyMaxAgeDays: 30 });
  });
});
