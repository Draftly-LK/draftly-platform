/**
 * Matter-module API calls.
 *
 * Mirrors backend/src/modules/matter/api/router.py and its request schemas.
 * Responses are camelCase because the Pydantic models use a `to_camel` alias
 * generator and FastAPI serialises response models by alias.
 *
 * Two contract rules shape the signatures here:
 *
 * - Creation never accepts a subtype. The exact instrument is a lawyer decision
 *   made after routing (`CreateMatterRequest`, §12.4), so it is confirmed by
 *   `confirmSubtype` and nothing else.
 * - Every mutating route after creation is a conditional request. The caller
 *   passes the `version` it last saw and it travels as `If-Match: "<version>"`;
 *   a missing header is 428 and a stale one is 412 (api-conventions §3).
 */

import { apiFetch, type TokenProvider } from "@/lib/api/client";
import type {
  ApiChecklistSnapshot,
  ApiIntakeAnswer,
  ApiRouting,
  ApiRtaMatter,
  ApiRtaMatterList,
} from "@/types/rta";

/** Mirrors `CreateMatterRequest`. `extra="forbid"` — no field outside this shape. */
export interface CreateMatterBody {
  reference: string;
  clientReference?: string;
  /** Language the prescribed instrument will be drawn in. */
  instrumentLanguage?: "en" | "si" | "ta";
  localAuthorityId?: string;
  /** Only set by the migration path for a record from the retired M2 vocabulary. */
  legacyMatterType?: "transfer" | "gift" | "lease" | "mortgage" | "other";
}

/** Mirrors `SaveAnswerRequest`. */
export interface SaveAnswerBody {
  /** Shape follows the question's `AnswerValueKind`; `UNKNOWN` is a real value. */
  value: unknown;
  /**
   * True only when the responsible lawyer is answering, not when a model
   * proposed the value. The server records provenance either way (§4.4).
   */
  lawyerConfirmed?: boolean;
  reason?: string;
  inferredFromFactIds?: string[];
}

/** Mirrors `ConfirmSubtypeRequest`. */
export interface ConfirmSubtypeBody {
  subtypeId: string;
  /** Required by the server for `CONTROLLED_OTHER`; rejected as 422 when blank. */
  declaredLegalBasis?: string;
}

export interface ListMattersParams {
  limit?: number;
  cursor?: string;
}

function ifMatch(version: number): Record<string, string> {
  return { "If-Match": `"${version}"` };
}

/** Create an intake draft. The exact instrument is chosen later, by a lawyer. */
export function createMatter(
  getToken: TokenProvider,
  body: CreateMatterBody,
): Promise<ApiRtaMatter> {
  return apiFetch<ApiRtaMatter>("/api/v1/matters", { method: "POST", body, getToken });
}

export function getMatter(getToken: TokenProvider, matterId: string): Promise<ApiRtaMatter> {
  return apiFetch<ApiRtaMatter>(`/api/v1/matters/${encodeURIComponent(matterId)}`, { getToken });
}

export function listMatters(
  getToken: TokenProvider,
  params: ListMattersParams = {},
): Promise<ApiRtaMatterList> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiRtaMatterList>(`/api/v1/matters${suffix}`, { getToken });
}

/**
 * Record an answer. The previous answer for that question is superseded, never
 * overwritten, so intake history stays part of the record (§4.4).
 */
export function saveIntakeAnswer(
  getToken: TokenProvider,
  matterId: string,
  questionId: string,
  body: SaveAnswerBody,
): Promise<ApiIntakeAnswer> {
  return apiFetch<ApiIntakeAnswer>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/intake/${encodeURIComponent(questionId)}`,
    { method: "PUT", body, getToken },
  );
}

/** Responsible-lawyer-only. Selecting a family is not selecting an instrument. */
export function confirmSubtype(
  getToken: TokenProvider,
  matterId: string,
  body: ConfirmSubtypeBody,
  version: number,
): Promise<ApiRtaMatter> {
  return apiFetch<ApiRtaMatter>(`/api/v1/matters/${encodeURIComponent(matterId)}/subtype`, {
    method: "POST",
    body,
    headers: ifMatch(version),
    getToken,
  });
}

/**
 * Evaluate regime, subtype, and automation scope from the answers so far.
 *
 * A 200 means the evaluation was recorded. It is not a statement that the
 * matter is legally in order (api-conventions §5).
 */
export function routeMatter(
  getToken: TokenProvider,
  matterId: string,
  version: number,
): Promise<ApiRouting> {
  return apiFetch<ApiRouting>(`/api/v1/matters/${encodeURIComponent(matterId)}/route`, {
    method: "POST",
    headers: ifMatch(version),
    getToken,
  });
}

/**
 * Compile a versioned checklist snapshot. The compiler is server-owned: there
 * is no client-side equivalent and a screen must never synthesise one (§5.1).
 */
export function compileChecklist(
  getToken: TokenProvider,
  matterId: string,
  version: number,
): Promise<ApiChecklistSnapshot> {
  return apiFetch<ApiChecklistSnapshot>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/checklist/compile`,
    { method: "POST", headers: ifMatch(version), getToken },
  );
}
