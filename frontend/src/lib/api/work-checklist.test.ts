import { expect, it } from "vitest";
import { recordFetches, token } from "@/test/fetch-recorder";
import {
  createWorkTask,
  decideWorkTask,
  decideTaskSuggestion,
  getWorkTaskHistory,
  getWorkChecklist,
} from "./work-checklist";
const recorder = recordFetches();
it("pins decisions to the displayed task version and preserves the retry key", async () => {
  await decideWorkTask(
    token,
    "synthetic / matter",
    "task/a",
    { decision: "complete", note: "Synthetic note" },
    3,
    "synthetic-key",
  );
  expect(recorder.only()).toMatchObject({
    method: "POST",
    path: "/api/v1/matters/synthetic%20%2F%20matter/work-tasks/task%2Fa/decisions",
    headers: { "If-Match": '"3"', "Idempotency-Key": "synthetic-key" },
    body: { decision: "complete", note: "Synthetic note" },
  });
});
it("creates custom tasks without asserting a governed completion", async () => {
  await createWorkTask(
    token,
    "synthetic",
    { title: "Synthetic record", reason: "Follow up", group: "documents" },
    "create-key",
  );
  expect(recorder.only()).toMatchObject({
    method: "POST",
    path: "/api/v1/matters/synthetic/work-tasks",
    headers: { "Idempotency-Key": "create-key" },
    body: {
      title: "Synthetic record",
      reason: "Follow up",
      group: "documents",
    },
  });
});
it("reads the backend-owned progress and uses bounded history pagination", async () => {
  await getWorkChecklist(token, "synthetic");
  expect(recorder.only().path).toBe("/api/v1/matters/synthetic/work-checklist");
  recorder.requests.length = 0;
  await getWorkTaskHistory(token, "synthetic", "task", "next+page");
  expect(recorder.only().path).toBe(
    "/api/v1/matters/synthetic/work-tasks/task/history?cursor=next%2Bpage",
  );
});
it("accepts suggestions only through a lawyer decision with source version", async () => {
  await decideTaskSuggestion(
    token,
    "synthetic",
    "suggestion",
    "accept",
    2,
    "accept-key",
  );
  expect(recorder.only()).toMatchObject({
    method: "POST",
    path: "/api/v1/matters/synthetic/task-suggestions/suggestion/decisions",
    headers: { "If-Match": '"2"', "Idempotency-Key": "accept-key" },
    body: { decision: "accept" },
  });
});
