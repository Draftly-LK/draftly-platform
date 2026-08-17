/**
 * Auth-module API calls.
 *
 * Mirrors backend/src/modules/auth/api/router.py. Responses are camelCase:
 * `UserRead` uses a `to_camel` alias generator and FastAPI serialises response
 * models by alias.
 */

import { apiFetch, type TokenProvider } from "@/lib/api/client";

/** Mirrors `UserRead` in backend/src/modules/auth/api/schemas.py. */
export interface ApiUser {
  id: string;
  displayName: string;
  /** "reviewer" | "approver" | "maintainer" | "administrator" | "pending" */
  role: string;
  notaryRegistration: string | null;
  jurisdiction: string | null;
  qualifications: string | null;
  professionalTitles: string | null;
  addressLine1: string | null;
  addressLine2: string | null;
  phone: string | null;
}

/** Mirrors `AccountStatusRead`. */
export interface ApiAccountStatus {
  status: "pending" | "active" | "suspended";
  message: string;
}

/**
 * The exact set of fields `PATCH /me` accepts. `UpdateProfileRequest` sets
 * `extra="forbid"`, so anything outside this shape is rejected with 422
 * before it reaches the service.
 */
export type ProfileUpdate = Partial<{
  displayName: string;
  notaryRegistration: string;
  jurisdiction: string;
  qualifications: string;
  professionalTitles: string;
  addressLine1: string;
  addressLine2: string;
  phone: string;
}>;

/**
 * Link the signed-in Clerk identity to a Draftly user.
 *
 * Must be called before any other authenticated route: a brand-new Clerk
 * subject has no UserIdentity row, so `get_request_context` rejects it with
 * `account_pending` until provisioning has run. Idempotent — an already-linked
 * identity returns the existing user.
 */
export function provisionMe(getToken: TokenProvider): Promise<ApiUser> {
  return apiFetch<ApiUser>("/api/v1/me/provision", { method: "POST", getToken });
}

export function getMe(getToken: TokenProvider): Promise<ApiUser> {
  return apiFetch<ApiUser>("/api/v1/me", { getToken });
}

export function getAccountStatus(getToken: TokenProvider): Promise<ApiAccountStatus> {
  return apiFetch<ApiAccountStatus>("/api/v1/account-status", { getToken });
}

export function updateMe(getToken: TokenProvider, changes: ProfileUpdate): Promise<ApiUser> {
  return apiFetch<ApiUser>("/api/v1/me", { method: "PATCH", body: changes, getToken });
}

/**
 * True when the user still owes us the professional details collected at
 * onboarding. Registration is never blocked on this — the plan provisions
 * every first login as ACTIVE/APPROVER (auth-service.md §Admission) — so this
 * only decides whether to route them to the onboarding screen.
 */
export function needsOnboarding(user: ApiUser): boolean {
  return !user.notaryRegistration || !user.jurisdiction;
}
