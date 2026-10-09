/**
 * Check and legal-issue API calls.
 *
 * Mirrors backend/src/modules/check/api/router.py and its request schemas.
 * A run is synchronous — pure comparisons over facts a lawyer already
 * confirmed, not the long-running kind of work api-conventions §6 defers to a
 * job. `run_checks` and `decide_issue` need no `If-Match`: the run route
 * creates fresh records rather than conditionally updating one, but decisions
 * on an existing issue still take the header (§7.3).
 */

import { apiFetch, ifMatch, type TokenProvider } from "@/lib/api/client";
import type {
  ApiCheckResultList,
  ApiCheckRun,
  ApiLegalIssue,
  ApiLegalIssueList,
} from "@/types/rta";

export interface RunChecksBody {
  transactionId: string;
  subjectId: string | null;
  associationVersion: number;
  searchCurrencyMaxAgeDays?: number;
}

/** Run the V0 checks, pinning the rule pack and the input fact versions. */
export function runChecks(
  getToken: TokenProvider,
  matterId: string,
  body: RunChecksBody,
): Promise<ApiCheckRun> {
  return apiFetch<ApiCheckRun>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/checks/run`,
    {
      method: "POST",
      body,
      getToken,
    },
  );
}

export interface ListParams {
  limit?: number;
  cursor?: string;
}

/** Every result of every run, newest first. Superseded runs stay readable. */
export function listCheckResults(
  getToken: TokenProvider,
  matterId: string,
  params: ListParams = {},
): Promise<ApiCheckResultList> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiCheckResultList>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/checks${suffix}`,
    { getToken },
  );
}

export interface ListIssuesParams extends ListParams {
  severity?: string;
  state?: string;
}

/**
 * Gates are returned beside the page so a filtered view cannot mislead: they
 * are always computed over every issue on the matter, never just the page.
 */
export function listIssues(
  getToken: TokenProvider,
  matterId: string,
  params: ListIssuesParams = {},
): Promise<ApiLegalIssueList> {
  const query = new URLSearchParams();
  if (params.severity !== undefined) query.set("severity", params.severity);
  if (params.state !== undefined) query.set("state", params.state);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiLegalIssueList>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/issues${suffix}`,
    { getToken },
  );
}

export interface IssueDecisionBody {
  /** One of the issue's own `permittedStates` — the server refuses anything else. */
  state: string;
  reason?: string;
  evidenceReferenceIds?: string[];
  assignedTo?: string;
}

/**
 * Record one disposition. A statutory blocker has no capability that reaches
 * `ACCEPTED_RISK`; the server refuses it regardless of what the caller holds.
 */
export function recordIssueDecision(
  getToken: TokenProvider,
  matterId: string,
  issueId: string,
  body: IssueDecisionBody,
  version: number,
): Promise<ApiLegalIssue> {
  return apiFetch<ApiLegalIssue>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/issues/${encodeURIComponent(issueId)}/decisions`,
    { method: "POST", body, headers: ifMatch(version), getToken },
  );
}

export async function listCompleteIssues(
  getToken: TokenProvider,
  matterId: string,
): Promise<ApiLegalIssueList> {
  const first = await listIssues(getToken, matterId, { limit: 100 });
  const items = [...first.items];
  let cursor = first.page.nextCursor;
  const seen = new Set<string>();
  while (cursor) {
    if (seen.has(cursor) || seen.size >= 100)
      throw new Error("Incomplete issue history");
    seen.add(cursor);
    const page = await listIssues(getToken, matterId, { limit: 100, cursor });
    items.push(...page.items);
    cursor = page.page.nextCursor;
  }
  return {
    ...first,
    items,
    page: { ...first.page, nextCursor: null, hasMore: false },
  };
}
