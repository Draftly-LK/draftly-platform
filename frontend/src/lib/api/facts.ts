import { apiFetch, ifMatch, type TokenProvider } from "./client";
import type {
  ApiMatterFact,
  ApiFactHistory,
  ApiFactTypes,
  ApiMatterSubject,
  ApiMatterTransaction,
  ApiPageInfo,
  ApiFactEvidenceInput,
  ApiFactValue,
  TransactionRole,
} from "@/types/rta";
export type { ApiMatterFact } from "@/types/rta";
export interface PageParams {
  limit?: number;
  cursor?: string;
}
export interface ApiFactPage<T> {
  items: T[];
  page: ApiPageInfo;
}
export interface ManualFactBody {
  factTypeId: string;
  value: ApiFactValue;
  reason: string;
  transactionId?: string | null;
  subjectId?: string | null;
  evidence?: ApiFactEvidenceInput;
}
export interface FactDecisionBody {
  reason?: string;
  value?: ApiFactValue;
  expectedScopeToken?: string;
  resolveFactIds?: string[];
  evidence?: ApiFactEvidenceInput;
}
export interface FactAssociationBody {
  reason: string;
  transactionId: string | null;
  subjectId: string | null;
}
export interface TransactionBody {
  parcelSubjectIds: string[];
  partyRoles: { subjectId: string; role: TransactionRole }[];
}
export const TRANSACTION_ROLES: readonly TransactionRole[] = [
  "transferor",
  "transferee",
  "owner",
  "donor",
  "donee",
  "lessor",
  "lessee",
  "mortgagor",
  "mortgagee",
  "other",
];
function root(matterId: string) {
  return `/api/v1/matters/${encodeURIComponent(matterId)}`;
}
function query(params: PageParams) {
  const q = new URLSearchParams();
  if (params.limit !== undefined) q.set("limit", String(params.limit));
  if (params.cursor !== undefined) q.set("cursor", params.cursor);
  return q.size ? `?${q}` : "";
}
export function listMatterFacts(
  getToken: TokenProvider,
  matterId: string,
  params: PageParams = {},
): Promise<ApiFactPage<ApiMatterFact>> {
  return apiFetch(`${root(matterId)}/facts${query(params)}`, { getToken });
}
export function getMatterFact(
  getToken: TokenProvider,
  matterId: string,
  factId: string,
): Promise<ApiMatterFact> {
  return apiFetch(`${root(matterId)}/facts/${encodeURIComponent(factId)}`, {
    getToken,
  });
}
export function getFactHistory(
  getToken: TokenProvider,
  matterId: string,
  factId: string,
  params: PageParams = {},
): Promise<ApiFactHistory> {
  return apiFetch(
    `${root(matterId)}/facts/${encodeURIComponent(factId)}/history${query(params)}`,
    { getToken },
  );
}
export function addManualFact(
  getToken: TokenProvider,
  matterId: string,
  body: ManualFactBody,
  key: string,
): Promise<ApiMatterFact> {
  return apiFetch(`${root(matterId)}/facts`, {
    method: "POST",
    body,
    headers: { "Idempotency-Key": key },
    getToken,
  });
}
export function reviewMatterFact(
  getToken: TokenProvider,
  matterId: string,
  factId: string,
  action: "associate",
  body: FactAssociationBody,
  version: number,
  key: string,
): Promise<ApiMatterFact>;
export function reviewMatterFact(
  getToken: TokenProvider,
  matterId: string,
  factId: string,
  action: "accept" | "correct" | "reject",
  body: FactDecisionBody,
  version: number,
  key: string,
): Promise<ApiMatterFact>;
export function reviewMatterFact(
  getToken: TokenProvider,
  matterId: string,
  factId: string,
  action: "accept" | "correct" | "reject" | "associate",
  body: FactDecisionBody | FactAssociationBody,
  version: number,
  key: string,
): Promise<ApiMatterFact> {
  // Non-association commands serialize an allowlist: even null scope fields
  // are forbidden by the server. Keys come from the caller's stable intent.
  const d = body as FactDecisionBody;
  const payload =
    action === "associate"
      ? body
      : {
          reason: d.reason,
          value: d.value,
          expectedScopeToken: d.expectedScopeToken,
          resolveFactIds: d.resolveFactIds,
          evidence: d.evidence,
        };
  return apiFetch(
    `${root(matterId)}/facts/${encodeURIComponent(factId)}/${action}`,
    {
      method: "POST",
      body: payload,
      headers: { ...ifMatch(version), "Idempotency-Key": key },
      getToken,
    },
  );
}
export function listSubjects(
  getToken: TokenProvider,
  matterId: string,
  params: PageParams = {},
): Promise<ApiFactPage<ApiMatterSubject>> {
  return apiFetch(`${root(matterId)}/subjects${query(params)}`, { getToken });
}
export function listTransactions(
  getToken: TokenProvider,
  matterId: string,
  params: PageParams = {},
): Promise<ApiFactPage<ApiMatterTransaction>> {
  return apiFetch(`${root(matterId)}/transactions${query(params)}`, {
    getToken,
  });
}
export function createSubject(
  getToken: TokenProvider,
  matterId: string,
  kind: "party" | "parcel",
  key: string,
): Promise<ApiMatterSubject> {
  return apiFetch(`${root(matterId)}/subjects`, {
    method: "POST",
    body: { kind },
    headers: { "Idempotency-Key": key },
    getToken,
  });
}
export function saveTransaction(
  getToken: TokenProvider,
  matterId: string,
  body: TransactionBody,
  key: string,
  current?: ApiMatterTransaction,
): Promise<ApiMatterTransaction> {
  return apiFetch(
    `${root(matterId)}/transactions${current ? `/${encodeURIComponent(current.id)}/associations` : ""}`,
    {
      method: "POST",
      body,
      headers: {
        ...(current ? ifMatch(current.version) : {}),
        "Idempotency-Key": key,
      },
      getToken,
    },
  );
}
export function getFactTypes(getToken: TokenProvider): Promise<ApiFactTypes> {
  return apiFetch("/api/v1/rta/fact-types", { getToken });
}
