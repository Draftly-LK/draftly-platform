import { apiFetch, type TokenProvider } from "./client";
import type { LegalSourceSummary, LegalSourceType } from "@/types";

interface LegalSourceList {
  items: LegalSourceSummary[];
  total: number;
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
