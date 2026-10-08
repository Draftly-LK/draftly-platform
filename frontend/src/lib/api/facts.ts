import { apiFetch, type TokenProvider } from "./client";

export interface ApiMatterFact {
  id: string;
  matterId: string;
  status:
    | "EXTRACTED_CANDIDATE"
    | "CORROBORATED"
    | "CONFLICTED"
    | "REVIEW_REQUIRED"
    | "LAWYER_CONFIRMED"
    | "LOCKED_FOR_FORM"
    | "REJECTED"
    | "SUPERSEDED";
}

interface ApiMatterFactList {
  items: ApiMatterFact[];
}

export function listMatterFacts(
  getToken: TokenProvider,
  matterId: string,
): Promise<ApiMatterFactList> {
  return apiFetch(`/api/v1/matters/${matterId}/facts`, { getToken });
}
