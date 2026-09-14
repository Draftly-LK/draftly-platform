/**
 * Matter agent API calls.
 *
 * Mirrors backend/src/modules/matter_agent/api/router.py. The transcript is
 * read from Neon and paginated with an opaque cursor; a turn is a job, so the
 * POST returns immediately and progress is polled or streamed.
 *
 * Every send carries an `Idempotency-Key`. A retried send therefore replays
 * the first job instead of asking the assistant the same question twice —
 * which is what makes the retry button in the composer safe.
 */

import {
  API_VERSION_PREFIX,
  apiBaseUrl,
  apiFetch,
  type TokenProvider,
} from "@/lib/api/client";

export interface ApiAgentSession {
  id: string;
  matterId: string;
  state: "active" | "closed";
  modelVersion: string;
  promptVersion: string;
  createdAt: string;
  updatedAt: string;
}

export interface ApiAgentMessage {
  id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  jobId: string | null;
  pendingActionId: string | null;
}

export interface ApiAgentMessagePage {
  items: ApiAgentMessage[];
  page: { nextCursor: string | null; hasMore: boolean; limit: number };
}

export interface ApiAgentJob {
  jobId: string;
  state: "queued" | "running" | "succeeded" | "failed" | "dead_letter";
  pollAfterMs: number;
  toolCallCount: number;
  failureClass: string | null;
}

export interface ApiPendingAction {
  id: string;
  actionKind: string;
  targetRef: string;
  targetVersion: number;
  state: "proposed" | "confirmed" | "rejected" | "expired";
  expiresAt: string;
  createdAt: string;
}

const AGENT_BASE = (matterId: string) =>
  `${API_VERSION_PREFIX}/matters/${matterId}/agent`;

export function getAgentSession(
  getToken: TokenProvider,
  matterId: string,
): Promise<ApiAgentSession> {
  return apiFetch<ApiAgentSession>(AGENT_BASE(matterId), {
    method: "GET",
    getToken,
  });
}

export function listAgentMessages(
  getToken: TokenProvider,
  matterId: string,
  params: { limit?: number; cursor?: string } = {},
): Promise<ApiAgentMessagePage> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor) query.set("cursor", params.cursor);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<ApiAgentMessagePage>(
    `${AGENT_BASE(matterId)}/messages${suffix}`,
    { method: "GET", getToken },
  );
}

export function sendAgentMessage(
  getToken: TokenProvider,
  matterId: string,
  content: string,
  idempotencyKey: string,
): Promise<ApiAgentJob> {
  return apiFetch<ApiAgentJob>(`${AGENT_BASE(matterId)}/messages`, {
    method: "POST",
    getToken,
    body: { content },
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function getAgentJob(
  getToken: TokenProvider,
  jobId: string,
): Promise<ApiAgentJob> {
  return apiFetch<ApiAgentJob>(`${API_VERSION_PREFIX}/agent-jobs/${jobId}`, {
    method: "GET",
    getToken,
  });
}

export function confirmAgentAction(
  getToken: TokenProvider,
  matterId: string,
  actionId: string,
): Promise<ApiPendingAction> {
  return apiFetch<ApiPendingAction>(
    `${AGENT_BASE(matterId)}/actions/${actionId}/confirm`,
    { method: "POST", getToken },
  );
}

export function rejectAgentAction(
  getToken: TokenProvider,
  matterId: string,
  actionId: string,
  reason?: string,
): Promise<ApiPendingAction> {
  return apiFetch<ApiPendingAction>(
    `${AGENT_BASE(matterId)}/actions/${actionId}/reject`,
    { method: "POST", getToken, body: { reason: reason ?? null } },
  );
}

/** A turn is finished when it can no longer change. */
export function isTerminalJobState(state: ApiAgentJob["state"]): boolean {
  return (
    state === "succeeded" || state === "failed" || state === "dead_letter"
  );
}

/**
 * A stable key for one logical send.
 *
 * Held across retries by the composer so that pressing "try again" replays the
 * original job rather than posting a second message.
 */
export function newIdempotencyKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `k-${Date.now()}-${Math.round(Math.random() * 1e9)}`;
}


/**
 * Stream turn progress over SSE, using `fetch` rather than `EventSource`.
 *
 * `EventSource` cannot send an `Authorization` header, and the alternative —
 * putting a bearer token in the query string — would leak it into proxy logs
 * and browser history. `fetch` streams the same `text/event-stream` body with
 * the header intact, so the transport stays authenticated.
 *
 * Returns `false` when the stream could not be used at all, which is the
 * caller's signal to fall back to polling. Polling is never wrong: the job row
 * is authoritative and the stream is presentation state.
 */
const LINE_SEPARATOR = "\n";
const FRAME_SEPARATOR = "\n\n";

export async function streamAgentJobEvents(
  getToken: TokenProvider,
  jobId: string,
  onEvent: (eventName: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<boolean> {
  const base = apiBaseUrl();
  if (base === null || typeof fetch !== "function") return false;

  const token = await getToken();
  if (!token) return false;

  let response: Response;
  try {
    response = await fetch(`${base}${API_VERSION_PREFIX}/agent-jobs/${jobId}/events`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
      signal,
    });
  } catch {
    return false;
  }
  if (!response.ok || !response.body) return false;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Frames are separated by a blank line; a partial frame stays buffered.
      let split = buffer.indexOf(FRAME_SEPARATOR);
      while (split !== -1) {
        emitFrame(buffer.slice(0, split), onEvent);
        buffer = buffer.slice(split + FRAME_SEPARATOR.length);
        split = buffer.indexOf(FRAME_SEPARATOR);
      }
    }
  } catch {
    // A dropped stream is not a failed turn; the caller polls to be sure.
    return false;
  } finally {
    reader.releaseLock();
  }
  return true;
}

function emitFrame(
  frame: string,
  onEvent: (eventName: string, data: unknown) => void,
): void {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of frame.split(LINE_SEPARATOR)) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;
  try {
    onEvent(eventName, JSON.parse(dataLines.join(LINE_SEPARATOR)));
  } catch {
    // A frame we cannot parse is reported without data rather than dropped:
    // progress is presentation state, and the job row settles the outcome.
    onEvent(eventName, null);
  }
}
