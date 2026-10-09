import { apiFetch, ifMatch, type TokenProvider } from "./client";
import type {
  CreateWorkTask,
  WorkChecklistRead,
  WorkTask,
  WorkTaskDecision,
  WorkTaskHistory,
} from "@/types/work-checklist";
function root(matterId: string) {
  return `/api/v1/matters/${encodeURIComponent(matterId)}`;
}
export function getWorkChecklist(
  getToken: TokenProvider,
  matterId: string,
): Promise<WorkChecklistRead> {
  return apiFetch(`${root(matterId)}/work-checklist`, { getToken });
}
export function createWorkTask(
  getToken: TokenProvider,
  matterId: string,
  body: CreateWorkTask,
  key: string,
): Promise<WorkTask> {
  return apiFetch(`${root(matterId)}/work-tasks`, {
    getToken,
    method: "POST",
    body,
    headers: { "Idempotency-Key": key },
  });
}
export function updateWorkTask(
  getToken: TokenProvider,
  matterId: string,
  taskId: string,
  body: Partial<CreateWorkTask>,
  version: number,
  key: string,
): Promise<WorkTask> {
  return apiFetch(
    `${root(matterId)}/work-tasks/${encodeURIComponent(taskId)}`,
    {
      getToken,
      method: "PATCH",
      body,
      headers: { ...ifMatch(version), "Idempotency-Key": key },
    },
  );
}
export function decideWorkTask(
  getToken: TokenProvider,
  matterId: string,
  taskId: string,
  body: WorkTaskDecision,
  version: number,
  key: string,
): Promise<WorkTask> {
  return apiFetch(
    `${root(matterId)}/work-tasks/${encodeURIComponent(taskId)}/decisions`,
    {
      getToken,
      method: "POST",
      body,
      headers: { ...ifMatch(version), "Idempotency-Key": key },
    },
  );
}
export function decideTaskSuggestion(
  getToken: TokenProvider,
  matterId: string,
  suggestionId: string,
  decision: "accept" | "dismiss",
  version: number,
  key: string,
): Promise<WorkTask> {
  return apiFetch(
    `${root(matterId)}/task-suggestions/${encodeURIComponent(suggestionId)}/decisions`,
    {
      getToken,
      method: "POST",
      body: { decision },
      headers: { ...ifMatch(version), "Idempotency-Key": key },
    },
  );
}
export function getWorkTaskHistory(
  getToken: TokenProvider,
  matterId: string,
  taskId: string,
  cursor?: string,
): Promise<WorkTaskHistory> {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return apiFetch(
    `${root(matterId)}/work-tasks/${encodeURIComponent(taskId)}/history${query}`,
    { getToken },
  );
}
