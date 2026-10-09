import { apiFetch, ifMatch, type TokenProvider } from "./client";
import type {
  ApiChecklistItemState,
  ApiReadiness,
  ApiRequirementLink,
} from "@/types/rta";
export type RequirementOperation =
  | "decisions"
  | "original-inspection"
  | "links";
function root(matterId: string) {
  return `/api/v1/matters/${encodeURIComponent(matterId)}`;
}
export function getReadiness(
  getToken: TokenProvider,
  matterId: string,
): Promise<ApiReadiness> {
  return apiFetch(`${root(matterId)}/readiness`, { getToken });
}
export function listRequirementLinks(
  getToken: TokenProvider,
  matterId: string,
  itemId: string,
): Promise<ApiRequirementLink[]> {
  return apiFetch(
    `${root(matterId)}/checklist-items/${encodeURIComponent(itemId)}/links`,
    { getToken },
  );
}
export function requirementCommand(
  getToken: TokenProvider,
  matterId: string,
  itemId: string,
  operation: RequirementOperation,
  body: Record<string, unknown>,
  version: number,
  key: string,
): Promise<ApiChecklistItemState | ApiRequirementLink> {
  return apiFetch(
    `${root(matterId)}/checklist-items/${encodeURIComponent(itemId)}/${operation}`,
    {
      getToken,
      method: "POST",
      body,
      headers: { ...ifMatch(version), "Idempotency-Key": key },
    },
  );
}
