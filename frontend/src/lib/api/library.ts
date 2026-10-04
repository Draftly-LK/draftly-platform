import { apiFetch, type TokenProvider } from "./client";
import type { LegalSourceSummary, LegalSourceType } from "@/types";
import type { CaseDetail, CasePage, CaseSearch } from "@/types/case";

interface LegalSourceList {
  items: LegalSourceSummary[];
  total: number;
}

export interface CaseFilters {
  query?: string;
  collection?: "LKCA" | "LKSC";
  court?: string;
  year?: number;
  limit?: number;
  cursor?: string;
}

export function listCases(
  getToken: TokenProvider,
  filters: CaseFilters = {},
): Promise<CasePage> {
  const parameters = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") parameters.set(key, String(value));
  }
  const suffix = parameters.size ? `?${parameters}` : "";
  return apiFetch(`/api/v1/library/cases${suffix}`, { getToken });
}

export function getCase(
  getToken: TokenProvider,
  caseId: string,
): Promise<CaseDetail> {
  return apiFetch(`/api/v1/library/cases/${encodeURIComponent(caseId)}`, {
    getToken,
  });
}

export function searchCases(
  getToken: TokenProvider,
  query: string,
  idempotencyKey: string,
): Promise<CaseSearch> {
  return apiFetch("/api/v1/research/cases/search", {
    getToken,
    method: "POST",
    body: { query, limit: 8 },
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function listLegalSources(
  getToken: TokenProvider,
  type?: LegalSourceType,
  query?: string,
): Promise<LegalSourceList> {
  const parameters = new URLSearchParams();
  if (type) parameters.set("type", type);
  if (query) parameters.set("query", query);
  const suffix = parameters.size > 0 ? `?${parameters.toString()}` : "";
  return apiFetch(`/api/v1/library${suffix}`, { getToken });
}
